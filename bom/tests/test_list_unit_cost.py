"""Products list: prefetched BoM costs match bom_unit_cost with fewer queries."""

from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from djmoney.money import Money

from bom.helpers import (
    create_a_fake_seller_part,
    create_some_fake_manufacturers,
    create_some_fake_part_classes,
    create_some_fake_sellers,
    create_user_and_organization,
)
from bom.list_queries import (
    LIST_PAGE_SELECT_RELATED,
    UnpaginatedPartRevList,
    attach_list_unit_costs,
    prepare_part_revs_for_list_page,
)
from bom.models import ManufacturerPart, Part, PartRevision, Subpart


class ListUnitCostPrefetchTests(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        self.part_class = create_some_fake_part_classes(self.organization)[0]
        self.seller = create_some_fake_sellers(self.organization)[0]
        self.manufacturer = create_some_fake_manufacturers(self.organization)[0]
        self.currency = self.organization.currency
        pt = self.organization.product_types.get(code="no_loi")
        pt.overhead = Money(20, self.currency)
        pt.save()
        self.organization.invalidate_product_type_cache()

    def _make_part(self, number, material, seller_cost=None):
        part = Part.objects.create(
            organization=self.organization,
            number_class=self.part_class,
            number_item=number,
        )
        mp = ManufacturerPart.objects.create(
            part=part,
            manufacturer=self.manufacturer,
            manufacturer_part_number=number,
        )
        part.primary_manufacturer_part = mp
        part.save()
        rev = PartRevision.objects.create(
            part=part,
            revision="1",
            description=number,
            material=material,
        )
        if seller_cost is not None:
            create_a_fake_seller_part(
                self.seller,
                mp,
                1,
                1,
                Money(seller_cost, self.currency),
                1,
                Money(0, self.currency),
            )
        return part, rev

    def _add_child(self, parent_rev, child_rev, qty):
        subpart = Subpart.objects.create(part_revision=child_rev, count=qty)
        parent_rev.assembly.subparts.add(subpart)

    def _prepare(self, revs):
        qs = PartRevision.objects.filter(
            pk__in=[rev.pk for rev in revs]
        ).select_related(*LIST_PAGE_SELECT_RELATED)
        return prepare_part_revs_for_list_page(UnpaginatedPartRevList(list(qs)))

    def test_product_list_unit_cost_matches_bom_plus_overhead(self):
        _raw, raw_rev = self._make_part("RAW1", "no_bom", seller_cost=10)
        _prod, prod_rev = self._make_part("PRD1", "no_loi")
        self._add_child(prod_rev, raw_rev, 2)

        page = self._prepare([prod_rev])
        attached = {pr.pk: pr for pr in page}[prod_rev.pk]
        fresh = PartRevision.objects.get(pk=prod_rev.pk)

        self.assertEqual(attached.list_unit_cost, Money(30, self.currency))
        self.assertEqual(attached.list_unit_cost, fresh.bom_unit_cost)

    def test_nested_product_list_unit_cost_matches_bom_unit_cost(self):
        _raw_child, raw_child_rev = self._make_part("RAWC", "no_bom", seller_cost=100)
        _child, child_rev = self._make_part("CHLD", "no_loi")
        self._add_child(child_rev, raw_child_rev, 1)

        _raw_parent, raw_parent_rev = self._make_part("RAWP", "no_bom", seller_cost=5)
        _parent, parent_rev = self._make_part("PRNT", "no_loi")
        self._add_child(parent_rev, child_rev, 1)
        self._add_child(parent_rev, raw_parent_rev, 1)

        page = self._prepare([parent_rev, child_rev])
        by_pk = {pr.pk: pr for pr in page}
        fresh_parent = PartRevision.objects.get(pk=parent_rev.pk)
        fresh_child = PartRevision.objects.get(pk=child_rev.pk)

        self.assertEqual(by_pk[parent_rev.pk].list_unit_cost, fresh_parent.bom_unit_cost)
        self.assertEqual(by_pk[child_rev.pk].list_unit_cost, fresh_child.bom_unit_cost)
        self.assertEqual(
            by_pk[parent_rev.pk].list_unit_cost.amount, Decimal("82.5")
        )

    def test_raw_material_uses_landed_seller_cost(self):
        _raw, raw_rev = self._make_part("RAWX", "no_bom", seller_cost=44)
        page = self._prepare([raw_rev])
        attached = list(page)[0]
        seller = attached.part.optimal_seller()

        self.assertFalse(attached.is_product)
        self.assertEqual(attached.list_unit_cost, seller.landed_unit_cost)
        self.assertEqual(attached.list_unit_cost, Money(44, self.currency))

    def test_attached_list_unit_cost_does_not_walk_bom_again(self):
        _raw, raw_rev = self._make_part("RAW2", "no_bom", seller_cost=7)
        _prod, prod_rev = self._make_part("PRD2", "no_loi")
        self._add_child(prod_rev, raw_rev, 1)

        page = self._prepare([prod_rev, raw_rev])
        with patch.object(
            PartRevision,
            "indented",
            side_effect=AssertionError("list must use attached cost"),
        ):
            costs = [pr.list_unit_cost for pr in page]
        self.assertEqual(len(costs), 2)
        self.assertIsNotNone(costs[0] or costs[1])

    def test_prefetch_uses_fewer_queries_than_per_row_bom_walk(self):
        products = []
        for i in range(5):
            _raw, raw_rev = self._make_part(f"R{i}", "no_bom", seller_cost=3 + i)
            _mid_raw, mid_raw_rev = self._make_part(
                f"M{i}", "no_bom", seller_cost=2 + i
            )
            _mid, mid_rev = self._make_part(f"MID{i}", "no_loi")
            self._add_child(mid_rev, mid_raw_rev, 1)
            _prod, prod_rev = self._make_part(f"P{i}", "no_loi")
            self._add_child(prod_rev, mid_rev, 1)
            self._add_child(prod_rev, raw_rev, 2)
            products.append(prod_rev)

        pks = [pr.pk for pr in products]

        with CaptureQueriesContext(connection) as per_row:
            for pk in pks:
                PartRevision.objects.select_related(
                    *LIST_PAGE_SELECT_RELATED
                ).get(pk=pk).bom_unit_cost

        qs = PartRevision.objects.filter(pk__in=pks).select_related(
            *LIST_PAGE_SELECT_RELATED
        )
        with CaptureQueriesContext(connection) as prefetched:
            page = prepare_part_revs_for_list_page(UnpaginatedPartRevList(list(qs)))
            costs = [pr.list_unit_cost for pr in page]

        self.assertEqual(len(costs), 5)
        self.assertLess(len(prefetched), len(per_row))
        # Shared BoM depth → query waves, not one walk per product row.
        self.assertLess(len(prefetched), len(per_row) // 2)

    def test_attach_list_unit_costs_alone_prefetches_graph(self):
        _raw, raw_rev = self._make_part("RAW3", "no_bom", seller_cost=9)
        _prod, prod_rev = self._make_part("PRD3", "no_loi")
        self._add_child(prod_rev, raw_rev, 3)

        qs = list(
            PartRevision.objects.filter(pk=prod_rev.pk).select_related(
                *LIST_PAGE_SELECT_RELATED
            )
        )
        # Seller prefetch required for nested optimal_seller during rollup.
        page = prepare_part_revs_for_list_page(
            UnpaginatedPartRevList(qs), attach_bom_costs=False
        )
        attach_list_unit_costs(page)
        fresh = PartRevision.objects.get(pk=prod_rev.pk)
        self.assertEqual(list(page)[0].list_unit_cost, fresh.bom_unit_cost)

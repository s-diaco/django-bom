"""Products list: prefetched BoM costs match bom_unit_cost with fewer queries."""

from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from djmoney.money import Money

from bom.exchange import RATE_KIND_MARKET, set_org_per_unit_rate
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
    prefetch_bom_graphs,
    prepare_part_revs_for_list_page,
)
from bom.models import ManufacturerPart, Organization, Part, PartRevision, Subpart


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
        # Child as its own list row keeps child overhead; parent rollup does not.
        self.assertEqual(by_pk[child_rev.pk].list_unit_cost, Money(120, self.currency))
        self.assertEqual(
            by_pk[parent_rev.pk].list_unit_cost.amount, Decimal("72.5")
        )

    def test_raw_material_uses_landed_seller_cost(self):
        _raw, raw_rev = self._make_part("RAWX", "no_bom", seller_cost=44)
        page = self._prepare([raw_rev])
        attached = list(page)[0]
        seller = attached.part.optimal_seller()

        self.assertFalse(attached.is_product)
        self.assertEqual(attached.list_unit_cost, seller.landed_unit_cost)
        self.assertEqual(attached.list_unit_cost, Money(44, self.currency))

    def test_product_list_unit_cost_flags_incomplete_when_materials_lack_price(self):
        """Incomplete BoM rollup: keep calculated cost and flag for UI warning."""
        _raw, raw_rev = self._make_part("RAW0", "no_bom")  # no seller / price
        _prod, prod_rev = self._make_part("PRD0", "no_loi")
        self._add_child(prod_rev, raw_rev, 2)

        page = self._prepare([prod_rev])
        attached = {pr.pk: pr for pr in page}[prod_rev.pk]
        bom = PartRevision.objects.get(pk=prod_rev.pk).indented()

        self.assertGreater(bom.missing_item_costs, 0)
        self.assertTrue(attached.bom_cost_incomplete)
        # Still expose the calculated rollup; UI warns that prices are incomplete.
        self.assertEqual(attached.list_unit_cost, bom.bom_unit_cost)

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

    def test_shared_graph_price_walks_use_no_sql_after_preparation(self):
        """Repeated roots/branches and empty leaves all need instance caches."""
        _raw, raw = self._make_part("SHRAW", "no_bom", seller_cost=7)
        _empty, empty = self._make_part("EMPTY", "no_loi")
        _shared, shared = self._make_part("SHARED", "with_loi")
        self._add_child(shared, raw, 2)
        self._add_child(shared, empty, 1)
        roots = [shared, empty]
        for number, quantity in [("LEFT", 1), ("RIGHT", 3)]:
            _part, root = self._make_part(number, "no_loi")
            self._add_child(root, shared, quantity)
            self._add_child(root, empty, 2)
            roots.append(root)
        # The same assembly also appears at a different BFS depth.
        self._add_child(roots[-1], roots[-2], 1)
        baseline = {rev.pk: PartRevision.objects.get(pk=rev.pk).indented() for rev in roots}
        original_indented = PartRevision.indented

        def query_free_indented(rev, *args, **kwargs):
            with self.assertNumQueries(0):
                return original_indented(rev, *args, **kwargs)

        # Check the FIRST pricing walk too, not just a warmed second walk.
        with patch.object(PartRevision, "indented", query_free_indented):
            page = self._prepare(roots)
        with self.assertNumQueries(0):
            for rev in page:
                bom = rev.indented()
                expected = baseline[rev.pk]
                self.assertEqual(bom.bom_unit_cost, expected.bom_unit_cost)
                self.assertEqual(bom.missing_item_costs, expected.missing_item_costs)
                self.assertEqual(len(bom.parts), len(expected.parts))

    def test_graph_prefetch_covers_distinct_instances_and_empty_assemblies(self):
        _part, root = self._make_part("DUPROOT", "no_loi")
        _raw, raw = self._make_part("DUPRAW", "no_bom", seller_cost=3)
        self._add_child(root, raw, 1)
        # select_related creates distinct assembly instances for the same PK.
        instances = [
            PartRevision.objects.select_related("assembly").get(pk=root.pk)
            for _ in range(2)
        ]
        self.assertIsNot(instances[0].assembly, instances[1].assembly)
        prefetch_bom_graphs(instances)
        with self.assertNumQueries(0):
            for rev in instances:
                children = rev._bom_walk_subparts()
                self.assertEqual(len(children), 1)
                self.assertEqual(children[0].part_revision._bom_walk_subparts(), [])

    def test_graph_prefetch_reuses_uncached_duplicate_root_assembly_fks(self):
        _part, root = self._make_part("DUPFK", "no_loi")
        _raw, raw = self._make_part("DUPFKRAW", "no_bom", seller_cost=3)
        self._add_child(root, raw, 1)

        def load_roots(count):
            return [PartRevision.objects.get(pk=root.pk) for _ in range(count)]

        single = load_roots(1)
        duplicates = load_roots(5)
        with CaptureQueriesContext(connection) as single_queries:
            prefetch_bom_graphs(single)
        with CaptureQueriesContext(connection) as duplicate_queries:
            prefetch_bom_graphs(duplicates)
        self.assertEqual(len(single_queries), len(duplicate_queries))
        with self.assertNumQueries(0):
            for rev in duplicates:
                children = rev._bom_walk_subparts()
                self.assertEqual(len(children), 1)
                self.assertEqual(children[0].part_revision._bom_walk_subparts(), [])

    def test_query_count_does_not_grow_with_shared_graph_occurrences(self):
        _raw, raw = self._make_part("SCALE_RAW", "no_bom", seller_cost=4)
        _mid, mid = self._make_part("SCALE_MID", "no_loi")
        self._add_child(mid, raw, 1)
        roots = []
        for i in range(5):
            _part, root = self._make_part(f"SCALE{i}", "no_loi")
            self._add_child(root, mid, i + 1)
            roots.append(root)
        with CaptureQueriesContext(connection) as single:
            self._prepare(roots[:1])
        with CaptureQueriesContext(connection) as multiple:
            self._prepare(roots)
        self.assertEqual(len(single), len(multiple))

    def test_shared_seller_relations_still_select_by_extended_quantity(self):
        raw_part, raw = self._make_part("QRAW", "no_bom", seller_cost=10)
        bulk = create_a_fake_seller_part(
            self.seller, raw_part.primary_manufacturer_part, 500, 1,
            Money(2, self.currency), 1, Money(0, self.currency),
        )
        _mid, mid = self._make_part("QMID", "with_loi")
        self._add_child(mid, raw, 1)
        roots = []
        for number, quantity in [("QLOW", 1), ("QHIGH", 10)]:
            _part, root = self._make_part(number, "no_loi")
            self._add_child(root, mid, quantity)
            roots.append(root)
        # Also retain the do_not_load occurrence and compare its rollup.
        unloaded = Subpart.objects.create(part_revision=raw, count=4, do_not_load=True)
        roots[0].assembly.subparts.add(unloaded)
        expected = {rev.pk: PartRevision.objects.get(pk=rev.pk).indented() for rev in roots}
        page = self._prepare(roots)
        with self.assertNumQueries(0):
            for rev in page:
                actual = rev.indented()
                self.assertEqual(actual.bom_unit_cost, expected[rev.pk].bom_unit_cost)
                self.assertEqual(actual.missing_item_costs, expected[rev.pk].missing_item_costs)
                child = rev._bom_walk_subparts()[0].part_revision
                leaf = child._bom_walk_subparts()[0].part_revision.part
                self.assertNotEqual(leaf.optimal_seller(100).pk, bulk.pk)
                self.assertEqual(leaf.optimal_seller(1000).pk, bulk.pk)
                # Revisit a lower quantity after the same instance chose bulk.
                self.assertNotEqual(leaf.optimal_seller(100).pk, bulk.pk)

    def test_type_maps_are_scoped_by_organization_and_preparation_call(self):
        _part, first = self._make_part("ORG1", "no_loi")
        other_org = Organization.objects.create(name="Other", owner=self.user)
        other_type = other_org.product_types.get(code="no_loi")
        other_type.overhead = Money(77, other_org.currency)
        other_type.save()
        other_part = Part.objects.create(organization=other_org, number_item="ORG2")
        second = PartRevision.objects.create(part=other_part, material="no_loi")
        page = self._prepare([first, second])
        by_pk = {rev.pk: rev for rev in page}
        self.assertEqual(by_pk[first.pk].type_overhead, Money(20, self.currency))
        self.assertEqual(by_pk[second.pk].type_overhead, Money(77, other_org.currency))
        other_type.overhead = Money(88, other_org.currency)
        other_type.save()
        fresh_page = self._prepare([second])
        self.assertEqual(list(fresh_page)[0].type_overhead, Money(88, other_org.currency))

    def test_product_types_loaded_once_per_organization_not_per_row(self):
        revs = [self._make_part(f"TYPE{i}", "no_bom", seller_cost=1)[1] for i in range(4)]
        with CaptureQueriesContext(connection) as queries:
            self._prepare(revs)
        type_queries = [q for q in queries if '"bom_producttype"' in q["sql"]]
        # Preserve default-type initialization: one existence check and one load.
        self.assertEqual(len(type_queries), 2)

    def test_materials_search_survives_foreign_sellerpart_missing_customs_rate(self):
        """Regression: dual FX must not 500 materials search for non-org quotes.

        Pre-fix: USD sellerpart with duty% and only a market rate set raised
        MissingExchangeRate while attach_list_unit_costs computed landed cost.
        """
        self.organization.currency = "IRR"
        self.organization.save()
        set_org_per_unit_rate("USD", "IRR", Decimal("42000"), kind=RATE_KIND_MARKET)

        part, rev = self._make_part("8601", "no_bom")
        mp = part.primary_manufacturer_part
        sp = create_a_fake_seller_part(
            self.seller,
            mp,
            1,
            1,
            Money(12, "USD"),
            1,
            Money(0, "USD"),
        )
        sp.shipping = Money(1, "USD")
        sp.customs_duty_percent = Decimal("10")
        sp.save()

        page = self._prepare([rev])
        attached = list(page)[0]
        self.assertIsNone(attached.list_unit_cost)

        self.client.login(username="kasper", password="ghostpassword")
        response = self.client.get(
            reverse("bom:materials"),
            {"q": "860", "action": ""},
        )
        self.assertEqual(response.status_code, 200)

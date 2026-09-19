from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from bom.helpers import (
    create_a_fake_seller_part,
    create_some_fake_manufacturers,
    create_some_fake_part_classes,
    create_some_fake_sellers,
    create_user_and_organization,
)
from bom.models import ManufacturerPart, Part, PartRevision, ProductType, Subpart


class ProductTypeOverheadTest(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        self.part_class = create_some_fake_part_classes(self.organization)[0]
        self.seller = create_some_fake_sellers(self.organization)[0]
        self.manufacturer = create_some_fake_manufacturers(self.organization)[0]
        self.currency = self.organization.currency
        self._set_overhead("no_loi", 20)
        self._set_overhead("with_loi", 15)

    def _set_overhead(self, code, amount):
        pt = self.organization.product_types.get(code=code)
        pt.overhead = Money(amount, self.currency)
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

    def test_product_cost_is_materials_plus_type_overhead(self):
        _raw, raw_rev = self._make_part("RAW1", "no_bom", seller_cost=10)
        _prod, prod_rev = self._make_part("PRD1", "no_loi", seller_cost=999)
        self._add_child(prod_rev, raw_rev, 2)

        cost = prod_rev.bom_unit_cost_at_quantity(1)
        self.assertEqual(cost, Money(30, self.currency))  # 10 + 20 overhead

    def test_nested_product_overhead_rolls_into_parent(self):
        _raw_child, raw_child_rev = self._make_part("RAWC", "no_bom", seller_cost=100)
        _child, child_rev = self._make_part("CHLD", "no_loi")
        self._add_child(child_rev, raw_child_rev, 1)
        self.assertEqual(child_rev.bom_unit_cost_at_quantity(1), Money(120, self.currency))

        _raw_parent, raw_parent_rev = self._make_part("RAWP", "no_bom", seller_cost=5)
        _parent, parent_rev = self._make_part("PRNT", "no_loi")
        self._add_child(parent_rev, child_rev, 1)
        self._add_child(parent_rev, raw_parent_rev, 1)

        # child unit 120 + raw 5 = 125 over qty 2 → 62.5, plus parent overhead 20
        cost = parent_rev.bom_unit_cost_at_quantity(1)
        self.assertEqual(cost.amount, Decimal("82.5"))

    def test_new_product_type_overhead(self):
        ProductType.objects.create(
            organization=self.organization,
            code="glaze",
            name="Glaze",
            has_bom=True,
            apply_loi=False,
            overhead=Money(7, self.currency),
            sort_order=10,
        )
        self.organization.invalidate_product_type_cache()

        _raw, raw_rev = self._make_part("RAWG", "no_bom", seller_cost=3)
        _prod, prod_rev = self._make_part("GLZ1", "glaze")
        self._add_child(prod_rev, raw_rev, 1)

        self.assertTrue(prod_rev.is_product)
        self.assertEqual(prod_rev.bom_unit_cost_at_quantity(1), Money(10, self.currency))

    def test_raw_material_ignores_type_overhead(self):
        _raw, raw_rev = self._make_part("RAWX", "no_bom", seller_cost=44)
        self.assertFalse(raw_rev.is_product)
        self.assertEqual(raw_rev.bom_unit_cost_at_quantity(1), Money(44, self.currency))

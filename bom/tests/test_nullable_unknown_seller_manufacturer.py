from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from bom.constants import DEFAULT_MANUFACTURER_NAME, DEFAULT_SELLER_NAME
from bom.helpers import create_some_fake_part_classes, create_user_and_organization
from bom.models import (
    Manufacturer,
    ManufacturerPart,
    Part,
    Seller,
    SellerPart,
)


class NullableUnknownSellerManufacturerTest(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        pc1, _pc2, _pc3 = create_some_fake_part_classes(self.organization)
        self.part = Part(
            organization=self.organization,
            number_class=pc1,
            number_item="1001",
        )
        self.part.save()

    def test_ensure_default_manufacturer_part_uses_null_manufacturer(self):
        mp = self.part.ensure_default_manufacturer_part()
        self.assertIsNone(mp.manufacturer_id)
        self.assertEqual(mp.manufacturer_part_number, self.part.number_item)
        self.part.refresh_from_db()
        self.assertEqual(self.part.primary_manufacturer_part_id, mp.id)
        self.assertFalse(
            Manufacturer.objects.filter(
                organization=self.organization,
                name__iexact=DEFAULT_MANUFACTURER_NAME,
            ).exists()
        )

    def test_seller_part_allows_null_seller_with_price(self):
        mp = self.part.ensure_default_manufacturer_part()
        sp = SellerPart.objects.create(
            manufacturer_part=mp,
            seller=None,
            unit_cost=Money(42, self.organization.currency),
            nre_cost=Money(0, self.organization.currency),
        )
        self.assertIsNone(sp.seller_id)
        self.assertEqual(sp.unit_cost.amount, Decimal("42"))
        self.assertEqual(self.part.optimal_seller().id, sp.id)
        self.assertFalse(
            Seller.objects.filter(
                organization=self.organization,
                name__iexact=DEFAULT_SELLER_NAME,
            ).exists()
        )

    def test_organization_seller_parts_includes_null_seller(self):
        mp = self.part.ensure_default_manufacturer_part()
        SellerPart.objects.create(
            manufacturer_part=mp,
            seller=None,
            unit_cost=Money(5, self.organization.currency),
            nre_cost=Money(0, self.organization.currency),
        )
        self.assertEqual(self.organization.seller_parts().count(), 1)

    def test_org_currency_change_retargets_null_seller_parts(self):
        mp = self.part.ensure_default_manufacturer_part()
        sp = SellerPart.objects.create(
            manufacturer_part=mp,
            seller=None,
            unit_cost=Money(10, "USD"),
            nre_cost=Money(0, "USD"),
            shipping=Money(0, "USD"),
        )
        self.organization.currency = "IRR"
        self.organization.save()
        sp.refresh_from_db()
        self.assertEqual(str(sp.unit_cost.currency), "IRR")
        self.assertEqual(str(sp.nre_cost.currency), "IRR")
        self.assertEqual(str(sp.shipping.currency), "IRR")

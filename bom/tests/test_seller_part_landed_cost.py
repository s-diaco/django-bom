from decimal import Decimal

from django.test import SimpleTestCase
from djmoney.money import Money

from bom.models import SellerPart


class SellerPartLandedUnitCostTest(SimpleTestCase):
    def test_landed_unit_cost_adds_shipping_and_duty_percent(self):
        seller_part = SellerPart(
            unit_cost=Money(100, "USD"),
            shipping=Money(10, "USD"),
            customs_duty_percent=Decimal("20"),
        )
        # 100 * 1.20 + 10 = 130
        self.assertEqual(seller_part.landed_unit_cost, Money(130, "USD"))

    def test_landed_unit_cost_defaults_to_unit_cost(self):
        seller_part = SellerPart(
            unit_cost=Money(50, "USD"),
            shipping=Money(0, "USD"),
            customs_duty_percent=Decimal("0"),
        )
        self.assertEqual(seller_part.landed_unit_cost, Money(50, "USD"))

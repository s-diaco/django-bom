from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from djmoney.money import Money

from bom.exchange import convert_to_org_currency, set_org_per_unit_rate
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

    def test_landed_unit_cost_coerces_mismatched_shipping_currency(self):
        # Post-0058: shipping defaulted to USD while unit_cost is org currency.
        seller_part = SellerPart(
            unit_cost=Money(50, "IRR"),
            shipping=Money(0, "USD"),
            customs_duty_percent=Decimal("0"),
        )
        self.assertEqual(seller_part.landed_unit_cost, Money(50, "IRR"))


class SellerPartLandedUnitCostFXTest(TestCase):
    def test_landed_unit_cost_uses_manual_org_fx_table(self):
        set_org_per_unit_rate("USD", "IRR", Decimal("42000"))
        # Don't subclass SellerPart (registers multi-table inheritance).
        probe = SimpleNamespace(
            unit_cost=Money(100, "USD"),
            shipping=Money(10, "USD"),
            customs_duty_percent=Decimal("20"),
            manufacturer_part=SimpleNamespace(
                part=SimpleNamespace(
                    organization=SimpleNamespace(currency="IRR")
                )
            ),
        )
        # (100 * 1.20 + 10) * 42000 = 5_460_000 IRR
        self.assertEqual(
            SellerPart.landed_unit_cost.fget(probe),
            Money(5460000, "IRR"),
        )

    def test_convert_to_org_currency(self):
        set_org_per_unit_rate("EUR", "IRR", Decimal("45000"))
        self.assertEqual(
            convert_to_org_currency(Money(2, "EUR"), "IRR"),
            Money(90000, "IRR"),
        )

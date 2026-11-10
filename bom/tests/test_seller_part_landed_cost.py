from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from djmoney.money import Money

from bom.exchange import (
    RATE_KIND_CUSTOMS,
    RATE_KIND_MARKET,
    convert_to_org_currency,
    set_org_per_unit_rate,
)
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
    def test_landed_unit_cost_uses_market_for_price_shipping_customs_for_duty(self):
        set_org_per_unit_rate(
            "USD", "IRR", Decimal("42000"), kind=RATE_KIND_MARKET
        )
        set_org_per_unit_rate(
            "USD", "IRR", Decimal("28000"), kind=RATE_KIND_CUSTOMS
        )
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
        # price: 100 * 42000 = 4_200_000
        # duty:  20 * 28000 = 560_000
        # ship:  10 * 42000 = 420_000
        # total = 5_180_000 IRR
        self.assertEqual(
            SellerPart.landed_unit_cost.fget(probe),
            Money(5180000, "IRR"),
        )

    def test_landed_unit_cost_zero_duty_skips_customs_rate(self):
        set_org_per_unit_rate(
            "USD", "IRR", Decimal("42000"), kind=RATE_KIND_MARKET
        )
        # No customs rate set — must still work when duty is 0.
        probe = SimpleNamespace(
            unit_cost=Money(100, "USD"),
            shipping=Money(10, "USD"),
            customs_duty_percent=Decimal("0"),
            manufacturer_part=SimpleNamespace(
                part=SimpleNamespace(
                    organization=SimpleNamespace(currency="IRR")
                )
            ),
        )
        self.assertEqual(
            SellerPart.landed_unit_cost.fget(probe),
            Money(4620000, "IRR"),
        )

    def test_landed_unit_cost_missing_customs_rate_returns_none(self):
        """Duty > 0 with only market rate set must not raise (materials 500)."""
        set_org_per_unit_rate(
            "USD", "IRR", Decimal("42000"), kind=RATE_KIND_MARKET
        )
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
        self.assertIsNone(SellerPart.landed_unit_cost.fget(probe))

    def test_landed_unit_cost_missing_market_rate_returns_none(self):
        probe = SimpleNamespace(
            unit_cost=Money(100, "USD"),
            shipping=Money(0, "USD"),
            customs_duty_percent=Decimal("0"),
            manufacturer_part=SimpleNamespace(
                part=SimpleNamespace(
                    organization=SimpleNamespace(currency="IRR")
                )
            ),
        )
        self.assertIsNone(SellerPart.landed_unit_cost.fget(probe))

    def test_convert_to_org_currency_defaults_to_market(self):
        set_org_per_unit_rate(
            "EUR", "IRR", Decimal("45000"), kind=RATE_KIND_MARKET
        )
        set_org_per_unit_rate(
            "EUR", "IRR", Decimal("30000"), kind=RATE_KIND_CUSTOMS
        )
        self.assertEqual(
            convert_to_org_currency(Money(2, "EUR"), "IRR"),
            Money(90000, "IRR"),
        )
        self.assertEqual(
            convert_to_org_currency(
                Money(2, "EUR"), "IRR", kind=RATE_KIND_CUSTOMS
            ),
            Money(60000, "IRR"),
        )

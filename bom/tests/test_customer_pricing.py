from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import translation
from djmoney.money import Money

from bom.forms import _resolve_customer_for_organization

from bom.helpers import (
    create_a_fake_customer,
    create_a_fake_customer_price,
    create_a_fake_seller_part,
    create_some_fake_parts,
    create_some_fake_sellers,
    create_user_and_organization,
)
from bom.models import Customer, CustomerPrice, Organization, User
from bom.utils import (
    apply_profit,
    customer_price_adjusted_base,
    customer_price_profit_tiers,
    implied_profit_percent,
)


@override_settings(BOM_CONFIG=settings.BOM_CONFIG_DEFAULT)
class TestCustomerPricingHelpers(TransactionTestCase):
    def test_apply_profit_markup_and_rounding(self):
        price = apply_profit(Decimal("100"), Decimal("20"), currency="USD")
        self.assertEqual(price, Money(120, "USD"))

        # Half-up to whole units (UNIT_COST_DECIMAL_PLACES = 0)
        price = apply_profit(Decimal("100"), Decimal("12.5"), currency="IRR")
        self.assertEqual(price, Money(113, "IRR"))

        price = apply_profit(Money(10, "USD"), Decimal("0"))
        self.assertEqual(price, Money(10, "USD"))

    def test_implied_profit_percent(self):
        self.assertEqual(
            implied_profit_percent(Decimal("100"), Decimal("120")),
            Decimal("20.00"),
        )
        self.assertIsNone(implied_profit_percent(Decimal("0"), Decimal("10")))
        self.assertIsNone(implied_profit_percent(None, Decimal("10")))

    def test_customer_price_profit_tiers_use_seven_percent_base_markup(self):
        tiers = customer_price_profit_tiers(
            Decimal("100"), currency="USD"
        )
        adjusted = customer_price_adjusted_base(Decimal("100"), currency="USD")
        self.assertEqual(adjusted, Money(107, "USD"))
        tier_20 = next(t for t in tiers if t["profit_percent"] == Decimal("20"))
        self.assertEqual(
            tier_20["price"],
            apply_profit(adjusted, Decimal("20"), currency="USD"),
        )

    def test_format_datetime_helper(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from django.utils import timezone

        from bom.constants import CALENDAR_GREGORIAN, CALENDAR_JALALI
        from bom.datetime_format import format_datetime

        self.assertEqual(format_datetime(None), "-")

        tehran = ZoneInfo("Asia/Tehran")
        dt = datetime(2026, 8, 23, 12, 30, tzinfo=tehran)
        with timezone.override("Asia/Tehran"):
            self.assertEqual(
                format_datetime(dt, calendar=CALENDAR_JALALI),
                "۱۴۰۵/۶/۱, ۱۲:۳۰",
            )
            self.assertEqual(
                format_datetime(dt, calendar=CALENDAR_GREGORIAN),
                "2026/8/23, 12:30",
            )


@override_settings(BOM_CONFIG=settings.BOM_CONFIG_DEFAULT)
class TestCustomerPricing(TransactionTestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.organization = create_user_and_organization()
        self.profile = self.user.bom_profile(organization=self.organization)
        self.profile.role = "A"
        self.profile.save()
        self.client.login(username="kasper", password="ghostpassword")
        translation.activate("en-US")
        self.parts = create_some_fake_parts(self.organization)
        self.part = self.parts[0]
        # Ensure a known non-zero unit cost for pricing tests.
        from bom.models import SellerPart

        SellerPart.objects.filter(manufacturer_part__part=self.part).delete()
        sellers = create_some_fake_sellers(self.organization)
        mp = self.part.manufacturer_parts().first()
        create_a_fake_seller_part(
            sellers[0],
            mp,
            1,
            1,
            Money(100, self.organization.currency),
            5,
            Money(0, self.organization.currency),
        )
        part_revision = self.part.latest()
        part_revision.material = "no_bom"
        part_revision.save()
        self.customer = create_a_fake_customer(
            self.organization, name="Buyer One"
        )

    def _tier_price(self, base_cost, profit_percent):
        adjusted = customer_price_adjusted_base(
            base_cost, currency=self.organization.currency
        )
        return apply_profit(
            adjusted, profit_percent, currency=self.organization.currency
        )

    def _confirm_payload(self, profit_percent, price_amount, reference_price=None, note=""):
        reference = (
            price_amount if reference_price is None else reference_price
        )
        return {
            "action": "confirm",
            "part": self.part.id,
            "profit_percent": str(profit_percent),
            "price": str(price_amount),
            "reference_price": str(reference),
            "note": note,
        }

    def test_customer_price_create_derived(self):
        part_revision = self.part.latest()
        base_cost = part_revision.bom_unit_cost_at_quantity(1)
        self.assertIsNotNone(base_cost)
        tier_price = self._tier_price(base_cost, Decimal("20"))

        response = self.client.post(
            reverse(
                "bom:customer-price-create", kwargs={"customer_id": self.customer.id}
            ),
            self._confirm_payload(
                Decimal("20"), tier_price.amount, note="auto"
            ),
        )
        self.assertEqual(response.status_code, 302)
        row = CustomerPrice.objects.get(customer=self.customer, part=self.part)
        self.assertEqual(row.quantity, 1)
        self.assertFalse(row.is_manual_price)
        self.assertEqual(row.profit_percent, Decimal("20.00"))
        self.assertEqual(row.price, tier_price)
        self.assertEqual(row.base_cost, base_cost)

    def test_customer_price_create_manual_back_computes_percent(self):
        part_revision = self.part.latest()
        base_cost = part_revision.bom_unit_cost_at_quantity(1)
        tier_price = self._tier_price(base_cost, Decimal("20"))
        manual_price = tier_price.amount + 1

        response = self.client.post(
            reverse(
                "bom:customer-price-create", kwargs={"customer_id": self.customer.id}
            ),
            self._confirm_payload(
                Decimal("20"),
                manual_price,
                reference_price=tier_price.amount,
                note="manual",
            ),
        )
        if response.status_code != 302:
            form = response.context.get("confirm_form")
            self.fail(
                f"Expected redirect, got {response.status_code}: "
                f"{getattr(form, 'errors', None)}"
            )
        row = CustomerPrice.objects.get(customer=self.customer, part=self.part)
        self.assertEqual(row.quantity, 1)
        self.assertTrue(row.is_manual_price)
        self.assertEqual(
            row.profit_percent,
            implied_profit_percent(base_cost, manual_price),
        )

    def test_latest_prices_returns_newest_per_part(self):
        older = create_a_fake_customer_price(
            self.customer, self.part, profit_percent=Decimal("10")
        )
        newer = create_a_fake_customer_price(
            self.customer, self.part, profit_percent=Decimal("30")
        )
        latest = list(self.customer.latest_prices())
        self.assertEqual(len(latest), 1)
        self.assertEqual(latest[0].id, newer.id)
        self.assertEqual(self.part.latest_customer_price(self.customer).id, newer.id)
        self.assertNotEqual(older.id, newer.id)

    def test_bom_unit_cost_varies_with_quantity_via_seller_selection(self):
        from bom.models import SellerPart

        sellers = create_some_fake_sellers(self.organization)
        mp = self.part.manufacturer_parts().first()
        SellerPart.objects.filter(manufacturer_part__part=self.part).delete()
        create_a_fake_seller_part(
            sellers[0],
            mp,
            1,
            1,
            Money(100, self.organization.currency),
            5,
            Money(0, self.organization.currency),
        )
        create_a_fake_seller_part(
            sellers[1],
            mp,
            5000,
            1,
            Money(40, self.organization.currency),
            5,
            Money(0, self.organization.currency),
        )
        part_revision = self.part.latest()
        part_revision.material = "no_bom"
        part_revision.save()

        unit_cost = part_revision.bom_unit_cost_at_quantity(1)
        high_qty_cost = part_revision.bom_unit_cost_at_quantity(10000)
        self.assertIsNotNone(unit_cost)
        self.assertIsNotNone(high_qty_cost)
        self.assertNotEqual(unit_cost.amount, high_qty_cost.amount)

    def test_cross_org_isolation(self):
        other_user = User.objects.create_user(
            "other", "other@example.com", "otherpassword"
        )
        other_org = Organization.objects.create(
            name="Other Org",
            subscription="P",
            owner=other_user,
        )
        other_customer = create_a_fake_customer(other_org, name="Other Buyer")

        response = self.client.get(
            reverse("bom:customer-info", kwargs={"customer_id": other_customer.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("bom:customers"))

    def test_viewer_cannot_delete_customer(self):
        self.profile.role = "V"
        self.profile.save()
        response = self.client.get(
            reverse("bom:customer-delete", kwargs={"customer_id": self.customer.id}),
            HTTP_REFERER=reverse("bom:customers"),
        )
        self.assertIn(response.status_code, (302, 307))
        self.assertTrue(Customer.objects.filter(pk=self.customer.id).exists())

    def test_admin_can_delete_customer(self):
        response = self.client.get(
            reverse("bom:customer-delete", kwargs={"customer_id": self.customer.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Customer.objects.filter(pk=self.customer.id).exists())

    def test_customers_list_and_create(self):
        response = self.client.get(reverse("bom:customers"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.customer.name)

        response = self.client.post(
            reverse("bom:customer-create"),
            {
                "name": "New Buyer",
                "code": "NB",
                "contact_name": "",
                "email": "",
                "phone": "",
                "address": "",
                "tax_id": "",
                "notes": "",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Customer.objects.filter(
                organization=self.organization, name="New Buyer"
            ).exists()
        )

    def test_export_prices_columns(self):
        create_a_fake_customer_price(
            self.customer, self.part, profit_percent=Decimal("20")
        )
        response = self.client.get(
            reverse(
                "bom:customer-export-prices", kwargs={"customer_id": self.customer.id}
            )
            + "?format=csv"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        body = response.content.decode("utf-8")
        self.assertIn("کد متریال", body)
        self.assertIn("قیمت", body)
        self.assertNotIn("تعداد", body)
        self.assertIn(self.part.full_part_number(), body)

    def test_part_info_customers_tab_context(self):
        create_a_fake_customer_price(self.customer, self.part)
        response = self.client.get(
            reverse("bom:part-info", kwargs={"part_id": self.part.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.customer.name)
        self.assertIn("customer_prices", response.context)
        self.assertContains(
            response,
            reverse(
                "bom:part-customer-price-create", kwargs={"part_id": self.part.id}
            ),
        )

    def test_part_customer_price_create(self):
        response = self.client.get(
            reverse(
                "bom:part-customer-price-create", kwargs={"part_id": self.part.id}
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.customer.name)
        self.assertContains(response, 'id="id_customer"')
        self.assertNotContains(response, '<select')

        response = self.client.post(
            reverse(
                "bom:part-customer-price-create", kwargs={"part_id": self.part.id}
            ),
            {
                "action": "confirm",
                "part": self.part.id,
                "customer": self.customer.id,
                "profit_percent": "15",
                "price": str(
                    self._tier_price(
                        self.part.latest().bom_unit_cost_at_quantity(1),
                        Decimal("15"),
                    ).amount
                ),
                "reference_price": str(
                    self._tier_price(
                        self.part.latest().bom_unit_cost_at_quantity(1),
                        Decimal("15"),
                    ).amount
                ),
                "note": "from part",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("bom:part-info", kwargs={"part_id": self.part.id}) + "#customers",
        )
        row = CustomerPrice.objects.get(customer=self.customer, part=self.part)
        self.assertEqual(row.quantity, 1)
        self.assertEqual(row.profit_percent, Decimal("15.00"))
        self.assertEqual(row.note, "from part")

    def test_part_customer_price_create_preview(self):
        part_revision = self.part.latest()
        base_cost = part_revision.bom_unit_cost_at_quantity(1)
        expected_price = self._tier_price(base_cost, Decimal("20"))

        response = self.client.post(
            reverse(
                "bom:part-customer-price-create", kwargs={"part_id": self.part.id}
            ),
            {
                "action": "preview",
                "customer": self.customer.name,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(base_cost.amount))
        self.assertContains(response, str(expected_price.amount))
        self.assertContains(response, "Confirm price")
        self.assertContains(response, "Prices by profit %")
        self.assertFalse(CustomerPrice.objects.filter(customer=self.customer).exists())

        response = self.client.post(
            reverse(
                "bom:part-customer-price-create", kwargs={"part_id": self.part.id}
            ),
            {
                "action": "preview",
                "customer": str(self.customer.id),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm price")

    def test_resolve_customer_for_organization(self):
        resolved = _resolve_customer_for_organization(
            self.organization, str(self.customer.pk)
        )
        self.assertEqual(resolved, self.customer)

        resolved = _resolve_customer_for_organization(
            self.organization, self.customer.name
        )
        self.assertEqual(resolved, self.customer)

        with self.assertRaises(ValidationError):
            _resolve_customer_for_organization(self.organization, "Unknown Buyer")

        inactive = create_a_fake_customer(self.organization, name="Inactive Buyer")
        inactive.is_active = False
        inactive.save()
        with self.assertRaises(ValidationError):
            _resolve_customer_for_organization(self.organization, inactive.name)

    def test_viewer_cannot_create_part_customer_price(self):
        self.profile.role = "V"
        self.profile.save()
        response = self.client.get(
            reverse(
                "bom:part-customer-price-create", kwargs={"part_id": self.part.id}
            ),
            HTTP_REFERER=reverse("bom:part-info", kwargs={"part_id": self.part.id}),
        )
        self.assertIn(response.status_code, (302, 307))
        self.assertFalse(CustomerPrice.objects.exists())

    def test_viewer_cannot_access_price_create(self):
        self.profile.role = "V"
        self.profile.save()
        response = self.client.get(
            reverse(
                "bom:customer-price-create", kwargs={"customer_id": self.customer.id}
            ),
            HTTP_REFERER=reverse("bom:customer-info", kwargs={"customer_id": self.customer.id}),
        )
        self.assertIn(response.status_code, (302, 307))
        response = self.client.post(
            reverse(
                "bom:customer-price-create", kwargs={"customer_id": self.customer.id}
            ),
            self._confirm_payload(Decimal("20"), Decimal("100"), note=""),
            HTTP_REFERER=reverse("bom:customer-info", kwargs={"customer_id": self.customer.id}),
        )
        self.assertIn(response.status_code, (302, 307))
        self.assertFalse(CustomerPrice.objects.exists())

    def test_latest_prices_for_other_customers(self):
        other_customer = create_a_fake_customer(
            self.organization, name="Buyer Two"
        )
        create_a_fake_customer_price(
            other_customer, self.part, profit_percent=Decimal("10")
        )
        create_a_fake_customer_price(
            other_customer, self.part, profit_percent=Decimal("30")
        )
        create_a_fake_customer_price(
            self.customer, self.part, profit_percent=Decimal("25")
        )

        peer_prices = list(
            self.part.latest_prices_for_other_customers(
                self.customer, self.organization
            )
        )
        self.assertEqual(len(peer_prices), 1)
        self.assertEqual(peer_prices[0].customer_id, other_customer.id)
        self.assertEqual(peer_prices[0].profit_percent, Decimal("30.00"))

    def test_customer_price_create_preview(self):
        other_customer = create_a_fake_customer(
            self.organization, name="Peer Buyer"
        )
        create_a_fake_customer_price(other_customer, self.part)

        part_revision = self.part.latest()
        base_cost = part_revision.bom_unit_cost_at_quantity(1)
        expected_price = self._tier_price(base_cost, Decimal("20"))

        response = self.client.post(
            reverse(
                "bom:customer-price-create", kwargs={"customer_id": self.customer.id}
            ),
            {
                "action": "preview",
                "part": self.part.full_part_number(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(base_cost.amount))
        self.assertContains(response, str(expected_price.amount))
        self.assertContains(response, "Peer Buyer")
        self.assertContains(response, "Confirm price")
        self.assertContains(response, "Prices by profit %")
        self.assertContains(response, "17.5")
        self.assertContains(response, str(self._tier_price(base_cost, Decimal("30")).amount))
        self.assertContains(response, "Adjusted base (BoM + 7%)")
        self.assertFalse(CustomerPrice.objects.filter(customer=self.customer).exists())

    def test_customer_price_create_confirm_from_peer_price(self):
        peer_customer = create_a_fake_customer(
            self.organization, name="Peer Buyer"
        )
        peer_row = create_a_fake_customer_price(peer_customer, self.part)

        response = self.client.post(
            reverse(
                "bom:customer-price-create", kwargs={"customer_id": self.customer.id}
            ),
            self._confirm_payload(
                peer_row.profit_percent,
                peer_row.price.amount,
                note="peer",
            ),
        )
        self.assertEqual(response.status_code, 302)
        row = CustomerPrice.objects.get(customer=self.customer, part=self.part)
        self.assertEqual(row.note, "peer")
        self.assertEqual(row.price, peer_row.price)
        self.assertFalse(row.is_manual_price)

    def test_customer_price_create_confirm(self):
        part_revision = self.part.latest()
        base_cost = part_revision.bom_unit_cost_at_quantity(1)
        tier_price = self._tier_price(base_cost, Decimal("20"))

        response = self.client.post(
            reverse(
                "bom:customer-price-create", kwargs={"customer_id": self.customer.id}
            ),
            self._confirm_payload(
                Decimal("20"), tier_price.amount, note="confirmed"
            ),
        )
        self.assertEqual(response.status_code, 302)
        row = CustomerPrice.objects.get(customer=self.customer, part=self.part)
        self.assertEqual(row.note, "confirmed")
        self.assertEqual(row.base_cost, base_cost)
        self.assertEqual(row.price, tier_price)

    def test_preview_shows_bom_overview(self):
        part_revision = self.part.latest()
        part_revision.material = "with_loi"
        part_revision.save()

        response = self.client.post(
            reverse(
                "bom:customer-price-create", kwargs={"customer_id": self.customer.id}
            ),
            {
                "action": "preview",
                "part": self.part.full_part_number(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BoM Overview")
        self.assertContains(response, "indented-bom-overview")
        self.assertNotContains(response, 'id="overview-print-button"')
        self.assertContains(response, 'id="price-review-print-button"')

    def test_get_with_part_id_shows_preview(self):
        response = self.client.get(
            reverse(
                "bom:customer-price-create", kwargs={"customer_id": self.customer.id}
            )
            + f"?part_id={self.part.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["show_preview"])
        self.assertContains(response, self.part.full_part_number())

    def test_price_history_shows_jalali_created_at(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from django.utils import timezone

        from bom.constants import CALENDAR_JALALI
        from bom.datetime_format import format_datetime

        row = create_a_fake_customer_price(self.customer, self.part)
        tehran = ZoneInfo("Asia/Tehran")
        row.created_at = datetime(2026, 8, 23, 12, 30, tzinfo=tehran)
        row.save(update_fields=["created_at"])
        self.profile.calendar = CALENDAR_JALALI
        self.profile.save(update_fields=["calendar"])

        translation.activate("fa-IR")
        with timezone.override("Asia/Tehran"):
            expected = format_datetime(row.created_at, calendar=CALENDAR_JALALI)
            response = self.client.get(
                reverse("bom:customer-info", kwargs={"customer_id": self.customer.id})
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, expected)
        # Gregorian localized fa_IR form (e.g. "۲۴ اوت ۲۰۲۶، ساعت ۱۲:۳۰")
        self.assertNotContains(response, "اوت")
        self.assertNotContains(response, "Aug. 23, 2026")
        self.assertNotContains(response, "2026-08-23")

    def test_price_history_respects_gregorian_calendar_preference(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from django.utils import timezone

        from bom.constants import CALENDAR_GREGORIAN, CALENDAR_JALALI
        from bom.datetime_format import format_datetime

        row = create_a_fake_customer_price(self.customer, self.part)
        tehran = ZoneInfo("Asia/Tehran")
        row.created_at = datetime(2026, 8, 23, 12, 30, tzinfo=tehran)
        row.save(update_fields=["created_at"])
        self.profile.calendar = CALENDAR_GREGORIAN
        self.profile.save(update_fields=["calendar"])

        with timezone.override("Asia/Tehran"):
            expected = format_datetime(row.created_at, calendar=CALENDAR_GREGORIAN)
            response = self.client.get(
                reverse("bom:customer-info", kwargs={"customer_id": self.customer.id})
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, expected)
        self.assertNotContains(
            response, format_datetime(row.created_at, calendar=CALENDAR_JALALI)
        )

    def test_settings_saves_calendar_preference(self):
        from bom.constants import CALENDAR_GREGORIAN

        response = self.client.post(
            reverse("bom:settings", kwargs={"tab_anchor": "user"}),
            {
                "submit-edit-user": "",
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "email": self.user.email,
                "calendar": CALENDAR_GREGORIAN,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.calendar, CALENDAR_GREGORIAN)

    def test_part_info_version_status_uses_user_datetime(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from django.utils import timezone

        from bom.constants import CALENDAR_JALALI
        from bom.datetime_format import format_datetime

        part_revision = self.part.latest()
        tehran = ZoneInfo("Asia/Tehran")
        part_revision.timestamp = datetime(2026, 8, 23, 12, 30, tzinfo=tehran)
        part_revision.save(update_fields=["timestamp"])
        self.profile.calendar = CALENDAR_JALALI
        self.profile.save(update_fields=["calendar"])

        with timezone.override("Asia/Tehran"):
            expected = format_datetime(
                part_revision.timestamp, calendar=CALENDAR_JALALI
            )
            response = self.client.get(
                reverse("bom:part-info", kwargs={"part_id": self.part.id})
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, expected)
        self.assertNotContains(response, "specs-revision-timestamp")

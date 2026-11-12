from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import translation
from django.utils.translation import gettext

from bom.forms import (
    AddSubpartForm,
    GroupedDecimalField,
    HomeJumpForm,
    OrganizationExchangeRatesForm,
    PartFormSemiIntelligent,
    PartInfoForm,
    PartRevisionForm,
    SellerPartForm,
    SingleExchangeRateForm,
    SubpartForm,
)
from bom.helpers import (
    create_a_fake_organization,
    create_some_fake_manufacturers,
    create_some_fake_part_classes,
    create_some_fake_parts,
)
from bom.models import Part, Seller
from bom.utils import currency_label, normalize_grouped_number
from decimal import Decimal
from djmoney.money import Money

TEST_FILES_DIR = "bom/test_files"


@override_settings(BOM_CONFIG=settings.BOM_CONFIG_DEFAULT)
class TestForms(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            "kasper", "kasper@McFadden.com", "ghostpassword"
        )
        self.organization = create_a_fake_organization(self.user)
        self.profile = self.user.bom_profile(organization=self.organization)
        translation.activate("en-US")

    def test_part_info_form(self):
        form_data = {"quantity": 10}
        form = PartInfoForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_part_info_form_blank(self):
        form = PartInfoForm({})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors,
            {
                "quantity": ["This field is required."],
            },
        )

    def test_part_form(self):
        (pc1, pc2, pc3) = create_some_fake_part_classes(self.organization)
        form_data = {
            "number_class": str(pc1),
            "description": "ASSY, ATLAS WRISTBAND 10",
            "revision": "AA",
        }

        form = PartFormSemiIntelligent(data=form_data, organization=self.organization)
        self.assertTrue(form.is_valid())

        (m1, m2, m3) = create_some_fake_manufacturers(self.organization)

        form_data = {
            "number_class": str(pc2),
            "description": "ASSY, ATLAS WRISTBAND 5",
            "revision": "1",
        }

        form = PartFormSemiIntelligent(data=form_data, organization=self.organization)
        self.assertTrue(form.is_valid())

        new_part, created = Part.objects.get_or_create(
            number_class=form.cleaned_data["number_class"],
            number_item=form.cleaned_data["number_item"],
            number_variation=form.cleaned_data["number_variation"],
            organization=self.organization,
        )

        self.assertTrue(created)
        self.assertEqual(new_part.number_class.id, pc2.id)

    def test_part_form_blank(self):
        (pc1, pc2, pc3) = create_some_fake_part_classes(self.organization)

        form = PartFormSemiIntelligent(data={}, organization=self.organization)

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors,
            {
                "number_class": ["This field is required."],
            },
        )

    def test_add_subpart_form(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        form_data = {
            "subpart_part_number": p1.full_part_number(),
            "count": 10,
            "reference": "",
            "do_not_load": False,
        }
        form = AddSubpartForm(
            organization=self.organization, data=form_data, part_id=p2.id
        )
        self.assertTrue(form.is_valid())

    def test_subpart_form_edit_ui_quantity_hides_reference_fields(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        parent_rev = p2.latest()
        subpart = parent_rev.assembly.subparts.first()
        self.assertIsNotNone(subpart)
        original_part_revision_id = subpart.part_revision_id
        original_reference = subpart.reference
        original_dnl = subpart.do_not_load

        form = SubpartForm(
            instance=subpart,
            organization=self.organization,
            part_id=subpart.part_revision.part.id,
            edit_subpart_ui=True,
        )
        self.assertEqual(form.fields["count"].label, "Quantity")
        self.assertEqual(list(form.fields.keys()), ["count"])
        self.assertNotIn("part_revision", form.fields)
        self.assertNotIn("reference", form.fields)
        self.assertNotIn("do_not_load", form.fields)
        self.assertNotIn("material", form.fields)

        translation.activate("fa-IR")
        if gettext("Quantity") == "مقدار":
            form_fa = SubpartForm(
                instance=subpart,
                organization=self.organization,
                part_id=subpart.part_revision.part.id,
                edit_subpart_ui=True,
            )
            self.assertEqual(form_fa.fields["count"].label, "مقدار")
        translation.activate("en-US")

        form_data = {"count": 7}
        post_form = SubpartForm(
            form_data,
            instance=subpart,
            organization=self.organization,
            part_id=subpart.part_revision.part.id,
            edit_subpart_ui=True,
        )
        self.assertTrue(post_form.is_valid())
        saved = post_form.save()
        self.assertEqual(saved.count, 7)
        self.assertEqual(saved.part_revision_id, original_part_revision_id)
        self.assertEqual(saved.reference, original_reference)
        self.assertEqual(saved.do_not_load, original_dnl)

    def test_add_subpart_form_blank(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        form = AddSubpartForm({}, organization=self.organization, part_id=p1.id)
        self.assertFalse(form.is_valid())
        self.assertTrue("subpart_part_number" in str(form.errors))
        self.assertTrue("This field is required." in str(form.errors))

    def test_add_subpart_form_render_query_budget(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        p2_rev = p2.latest()
        p2_rev.material = "with_loi"
        p2_rev.description = "Known subpart description"
        p2_rev.save()
        with CaptureQueriesContext(connection) as ctx:
            form = AddSubpartForm(organization=self.organization, part_id=p1.id)
            html = str(form["subpart_part_number"])
        self.assertLessEqual(len(ctx), 5)
        self.assertIn(p2.full_part_number(), html)
        self.assertIn(p2_rev.description, html)
        self.assertNotIn("with_loi", html)

    def test_home_jump_form_autocomplete_labels(self):
        (p1, p2, _p3, _p4) = create_some_fake_parts(organization=self.organization)
        rev = p1.latest()
        rev.material = "with_loi"
        rev.description = "Known home jump description"
        rev.save()
        form = HomeJumpForm(organization=self.organization)
        html = str(form["q"])
        self.assertIn(p1.full_part_number(), html)
        self.assertIn(p2.full_part_number(), html)
        self.assertIn("Known home jump description", html)
        self.assertNotIn("with_loi", html)
        self.assertIn("form.submit()", html)
        self.assertIn('name="q"', html)

    def test_add_sellerpart_form(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        form = SellerPartForm()
        self.assertFalse(form.is_valid())

        seller = Seller.objects.filter(organization=self.organization)[0]

        form_data = {
            "seller": seller.id,
            "seller_part_number": "123-45678",
            "minimum_order_quantity": 1000,
            "minimum_pack_quantity": 100,
            "currency": self.organization.currency,
            "unit_cost": 12332,
            "lead_time_days": 14,
            "nre_cost": 1000,
            "ncnr": True,
        }

        filled_form = SellerPartForm(form_data, organization=self.organization)
        self.assertTrue(filled_form.is_valid())

        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        sp = p1.optimal_seller()
        sp.unit_cost = 10
        sp.nre_cost = 22
        sp.save()

        filled_form = SellerPartForm(instance=sp, organization=self.organization)
        self.assertFalse("$10.0" in filled_form.as_ul())
        self.assertFalse("$22.0" in filled_form.as_ul())

    def test_currency_label_translated(self):
        translation.activate("en-US")
        self.assertEqual(currency_label("USD"), "USD")
        self.assertEqual(currency_label("IRR"), "IRR")

        form = SellerPartForm(organization=self.organization)
        self.assertIn(("USD", "USD"), form.fields["currency"].choices)

        translation.activate("fa-IR")
        self.assertEqual(currency_label("USD"), "دلار")
        self.assertEqual(currency_label("IRR"), "ریال")
        self.assertEqual(currency_label("XYZ"), "XYZ")

        form = SellerPartForm(organization=self.organization)
        labels = dict(form.fields["currency"].choices)
        self.assertEqual(labels.get("USD"), "دلار")
        self.assertEqual(labels.get("IRR"), "ریال")

    def test_money_amount_filter_omits_currency(self):
        from bom.templatetags.bom_i18n import money_amount

        self.assertEqual(money_amount(Money(98000, "IRR")), "98,000")
        self.assertEqual(money_amount(Money(4310, "USD")), "4,310")
        self.assertEqual(money_amount(Money(Decimal("12.5"), "USD")), "12.5")
        self.assertEqual(money_amount(Money(Decimal("1.23"), "USD")), "1.23")
        self.assertEqual(money_amount(None), "")

    def test_product_type_labels_translated(self):
        translation.activate("en-US")
        form = PartRevisionForm(organization=self.organization)
        labels = dict(form.fields["material"].choices)
        self.assertEqual(labels.get("with_loi"), "Frit")
        self.assertEqual(labels.get("no_loi"), "Compound")
        self.assertEqual(labels.get("no_bom"), "Raw Material")
        self.assertEqual(labels.get("ink"), "Ink")
        self.assertEqual(labels.get("powder"), "Powder")

        translation.activate("fa-IR")
        # .mo is gitignored; skip Persian checks when compilemessages was not run.
        if gettext("Frit") == "فریت":
            form = PartRevisionForm(organization=self.organization)
            labels = dict(form.fields["material"].choices)
            self.assertEqual(labels.get("with_loi"), "فریت")
            self.assertEqual(labels.get("no_loi"), "کامپوند")
            self.assertEqual(labels.get("no_bom"), "مواد اولیه")
            self.assertEqual(labels.get("ink"), "جوهر")
            self.assertEqual(labels.get("powder"), "پودر")
            self.assertEqual(gettext("Compound"), "کامپوند")
            self.assertEqual(gettext("Ink"), "جوهر")
            self.assertEqual(gettext("Powder"), "پودر")

        from bom.models import ProductType

        ProductType.objects.create(
            organization=self.organization,
            code="ceramic",
            name="Ceramic paste",
            has_bom=True,
            sort_order=99,
        )
        form = PartRevisionForm(organization=self.organization)
        labels = dict(form.fields["material"].choices)
        self.assertEqual(labels.get("ceramic"), "Ceramic paste")

    def test_normalize_grouped_number(self):
        self.assertEqual(normalize_grouped_number("1,234,567"), "1234567")
        self.assertEqual(normalize_grouped_number("1٬234٬567"), "1234567")
        self.assertEqual(normalize_grouped_number("12 345"), "12345")
        self.assertEqual(normalize_grouped_number("12.5"), "12.5")
        self.assertEqual(normalize_grouped_number("1,234.56"), "1234.56")
        self.assertEqual(normalize_grouped_number("۱۲٫۵"), "12.5")
        self.assertEqual(normalize_grouped_number(Decimal("10")), Decimal("10"))

    def test_seller_part_form_accepts_grouped_unit_cost(self):
        create_some_fake_parts(organization=self.organization)
        seller = Seller.objects.filter(organization=self.organization)[0]
        form = SellerPartForm(
            {
                "seller": seller.id,
                "seller_part_number": "GRP-1",
                "currency": self.organization.currency,
                "unit_cost": "1,234,567",
                "shipping": "10,000",
                "customs_duty_percent": "0",
            },
            organization=self.organization,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["unit_cost"], Decimal("1234567"))
        self.assertEqual(form.cleaned_data["shipping"], Decimal("10000"))
        self.assertIn("bom-price-input", form.fields["unit_cost"].widget.attrs.get("class", ""))

    def test_seller_part_form_accepts_and_saves_decimals(self):
        from bom.models import SellerPart
        from bom.templatetags.bom_i18n import money_amount

        parts = create_some_fake_parts(organization=self.organization)
        mp = parts[0].primary_manufacturer_part
        seller = Seller.objects.filter(organization=self.organization)[0]
        form = SellerPartForm(
            {
                "seller": seller.id,
                "seller_part_number": "DEC-1",
                "currency": self.organization.currency,
                "unit_cost": "12.34",
                "shipping": "1.25",
                "customs_duty_percent": "7.5",
            },
            organization=self.organization,
            manufacturer_part=mp,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["unit_cost"], Decimal("12.34"))
        self.assertEqual(form.cleaned_data["shipping"], Decimal("1.25"))
        self.assertEqual(form.cleaned_data["customs_duty_percent"], Decimal("7.5"))
        sp = form.save()
        sp.refresh_from_db()
        self.assertEqual(sp.unit_cost.amount, Decimal("12.34"))
        self.assertEqual(sp.shipping.amount, Decimal("1.25"))
        self.assertEqual(sp.customs_duty_percent, Decimal("7.50"))
        self.assertEqual(str(sp.unit_cost.currency), self.organization.currency)
        self.assertEqual(str(sp.shipping.currency), self.organization.currency)
        self.assertEqual(money_amount(sp.unit_cost), "12.34")
        self.assertEqual(money_amount(sp.shipping), "1.25")

        # More than 2 decimal places is rejected.
        too_precise = SellerPartForm(
            {
                "seller": seller.id,
                "seller_part_number": "DEC-2",
                "currency": self.organization.currency,
                "unit_cost": "12.345",
                "shipping": "1.259",
                "customs_duty_percent": "7.555",
            },
            organization=self.organization,
            manufacturer_part=mp,
        )
        self.assertFalse(too_precise.is_valid())
        self.assertIn("unit_cost", too_precise.errors)
        self.assertIn("shipping", too_precise.errors)
        self.assertIn("customs_duty_percent", too_precise.errors)

        # Round-trip edit form shows the stored decimals.
        edit = SellerPartForm(instance=sp, organization=self.organization)
        self.assertEqual(edit.initial["unit_cost"], Decimal("12.34"))
        self.assertEqual(edit.initial["shipping"], Decimal("1.25"))
        self.assertEqual(edit.initial["customs_duty_percent"], Decimal("7.50"))
        self.assertEqual(SellerPart.objects.filter(pk=sp.pk).count(), 1)

    def test_seller_part_edit_form_formats_two_decimal_places(self):
        """Edit widgets must show 2dp even when Money amount scale is 4."""
        from bom.constants import UNIT_COST_DECIMAL_PLACES
        from bom.models import SellerPart

        self.assertEqual(UNIT_COST_DECIMAL_PLACES, 2)
        parts = create_some_fake_parts(organization=self.organization)
        mp = parts[0].primary_manufacturer_part
        seller = Seller.objects.filter(organization=self.organization)[0]
        sp = SellerPart.objects.create(
            manufacturer_part=mp,
            seller=seller,
            seller_part_number="DP-4",
            unit_cost=Money(Decimal("12.34"), self.organization.currency),
            shipping=Money(Decimal("1.25"), self.organization.currency),
            customs_duty_percent=Decimal("7.50"),
            nre_cost=Money(Decimal("0"), self.organization.currency),
        )
        # Simulate a numeric(19,4) read: amount keeps 4 fractional digits.
        sp.unit_cost = Money(Decimal("12.3400"), self.organization.currency)
        sp.shipping = Money(Decimal("1.2500"), self.organization.currency)
        self.assertEqual(sp.unit_cost.amount, Decimal("12.3400"))
        self.assertEqual(sp.shipping.amount, Decimal("1.2500"))

        edit = SellerPartForm(instance=sp, organization=self.organization)
        self.assertEqual(edit.initial["unit_cost"], Decimal("12.34"))
        self.assertEqual(edit.initial["shipping"], Decimal("1.25"))
        unit_html = str(edit["unit_cost"])
        shipping_html = str(edit["shipping"])
        self.assertIn('value="12.34"', unit_html)
        self.assertIn('value="1.25"', shipping_html)
        self.assertNotIn("12.3400", unit_html)
        self.assertNotIn("1.2500", shipping_html)

        field = GroupedDecimalField(
            max_digits=19, decimal_places=UNIT_COST_DECIMAL_PLACES
        )
        self.assertEqual(field.prepare_value(Decimal("9.8765")), "9.88")
        self.assertEqual(field.prepare_value(Decimal("10.0000")), "10.00")

    def test_grouped_decimal_field_to_python(self):
        field = GroupedDecimalField()
        self.assertEqual(field.clean("1,234,567"), Decimal("1234567"))
        self.assertEqual(field.clean("9٬876"), Decimal("9876"))
        self.assertEqual(field.clean("1,234.56"), Decimal("1234.56"))
        self.assertEqual(field.clean("12.5"), Decimal("12.5"))

    def test_exchange_rate_forms_accept_grouped_rates(self):
        self.organization.currency = "IRR"
        self.organization.save()

        org_form = OrganizationExchangeRatesForm(
            {
                "rate_USD": "42,000",
                "customs_rate_USD": "28,000",
                "rate_EUR": "45,000",
                "customs_rate_EUR": "30,000",
            },
            organization=self.organization,
        )
        self.assertTrue(org_form.is_valid(), org_form.errors)
        self.assertEqual(org_form.cleaned_data["rate_USD"], Decimal("42000"))
        self.assertEqual(
            org_form.cleaned_data["customs_rate_USD"], Decimal("28000")
        )
        self.assertEqual(org_form.cleaned_data["rate_EUR"], Decimal("45000"))
        self.assertIn(
            "bom-price-input",
            org_form.fields["rate_USD"].widget.attrs.get("class", ""),
        )
        self.assertEqual(len(org_form.currency_pairs), 6)
        self.assertEqual(org_form.currency_pairs[0]["code"], "USD")

        single = SingleExchangeRateForm(
            {
                "currency": "USD",
                "rate": "42,000",
                "customs_rate": "28,000",
            },
            organization=self.organization,
        )
        self.assertTrue(single.is_valid(), single.errors)
        self.assertEqual(single.cleaned_data["rate"], Decimal("42000"))
        self.assertEqual(single.cleaned_data["customs_rate"], Decimal("28000"))
        self.assertIn(
            "bom-price-input",
            single.fields["rate"].widget.attrs.get("class", ""),
        )

    def test_exchange_rate_forms_reject_decimals(self):
        self.organization.currency = "IRR"
        self.organization.save()

        org_form = OrganizationExchangeRatesForm(
            {
                "rate_USD": "42,000.5",
                "customs_rate_USD": "28,000",
                "rate_EUR": "45,000",
                "customs_rate_EUR": "30,000",
            },
            organization=self.organization,
        )
        self.assertFalse(org_form.is_valid())
        self.assertIn("rate_USD", org_form.errors)

        org_customs = OrganizationExchangeRatesForm(
            {
                "rate_USD": "42,000",
                "customs_rate_USD": "28,000.5",
            },
            organization=self.organization,
        )
        self.assertFalse(org_customs.is_valid())
        self.assertIn("customs_rate_USD", org_customs.errors)

        single = SingleExchangeRateForm(
            {"currency": "USD", "rate": "12.34"},
            organization=self.organization,
        )
        self.assertFalse(single.is_valid())
        self.assertIn("rate", single.errors)

    def test_exchange_rate_forms_persist_dual_rates(self):
        from bom.exchange import (
            RATE_KIND_CUSTOMS,
            RATE_KIND_MARKET,
            get_org_per_unit_rate,
        )

        self.organization.currency = "IRR"
        self.organization.save()

        org_form = OrganizationExchangeRatesForm(
            {
                "rate_USD": "42,000",
                "customs_rate_USD": "28,000",
            },
            organization=self.organization,
        )
        self.assertTrue(org_form.is_valid(), org_form.errors)
        org_form.save()
        self.assertEqual(
            get_org_per_unit_rate("USD", "IRR", kind=RATE_KIND_MARKET),
            Decimal("42000"),
        )
        self.assertEqual(
            get_org_per_unit_rate("USD", "IRR", kind=RATE_KIND_CUSTOMS),
            Decimal("28000"),
        )

        single = SingleExchangeRateForm(
            {
                "currency": "EUR",
                "rate": "45,000",
                "customs_rate": "30,000",
            },
            organization=self.organization,
        )
        self.assertTrue(single.is_valid(), single.errors)
        single.save()
        self.assertEqual(
            get_org_per_unit_rate("EUR", "IRR", kind=RATE_KIND_MARKET),
            Decimal("45000"),
        )
        self.assertEqual(
            get_org_per_unit_rate("EUR", "IRR", kind=RATE_KIND_CUSTOMS),
            Decimal("30000"),
        )

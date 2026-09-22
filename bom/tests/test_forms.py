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
    OrganizationExchangeRatesForm,
    PartFormSemiIntelligent,
    PartInfoForm,
    PartRevisionForm,
    SellerPartForm,
    SingleExchangeRateForm,
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

    def test_add_subpart_form_blank(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        form = AddSubpartForm({}, organization=self.organization, part_id=p1.id)
        self.assertFalse(form.is_valid())
        self.assertTrue("subpart_part_number" in str(form.errors))
        self.assertTrue("This field is required." in str(form.errors))

    def test_add_subpart_form_render_query_budget(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        with CaptureQueriesContext(connection) as ctx:
            form = AddSubpartForm(organization=self.organization, part_id=p1.id)
            html = str(form["subpart_part_number"])
        self.assertLessEqual(len(ctx), 5)
        self.assertIn(p2.full_part_number(), html)

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

    def test_product_type_labels_translated(self):
        translation.activate("en-US")
        form = PartRevisionForm(organization=self.organization)
        labels = dict(form.fields["material"].choices)
        self.assertEqual(labels.get("with_loi"), "With loss (LOI) (Frit)")
        self.assertEqual(
            labels.get("no_loi"), "Without loss (LOI) (compound, ink, …)"
        )
        self.assertEqual(labels.get("no_bom"), "Raw materials")

        translation.activate("fa-IR")
        form = PartRevisionForm(organization=self.organization)
        labels = dict(form.fields["material"].choices)
        self.assertEqual(labels.get("with_loi"), "با لحاظ کردن پرت (فریت)")
        self.assertEqual(
            labels.get("no_loi"), "بدون احتساب پرت (کامپوند، جوهر یا …)"
        )
        self.assertEqual(labels.get("no_bom"), "مواد اولیه")
        self.assertEqual(gettext("Compound"), "کامپوند")
        self.assertEqual(gettext("Frit"), "فریت")
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

    def test_grouped_decimal_field_to_python(self):
        field = GroupedDecimalField()
        self.assertEqual(field.clean("1,234,567"), Decimal("1234567"))
        self.assertEqual(field.clean("9٬876"), Decimal("9876"))

    def test_exchange_rate_forms_accept_grouped_rates(self):
        self.organization.currency = "IRR"
        self.organization.save()

        org_form = OrganizationExchangeRatesForm(
            {"rate_USD": "42,000", "rate_EUR": "45,000"},
            organization=self.organization,
        )
        self.assertTrue(org_form.is_valid(), org_form.errors)
        self.assertEqual(org_form.cleaned_data["rate_USD"], Decimal("42000"))
        self.assertEqual(org_form.cleaned_data["rate_EUR"], Decimal("45000"))
        self.assertIn(
            "bom-price-input",
            org_form.fields["rate_USD"].widget.attrs.get("class", ""),
        )

        single = SingleExchangeRateForm(
            {"currency": "USD", "rate": "42,000"},
            organization=self.organization,
        )
        self.assertTrue(single.is_valid(), single.errors)
        self.assertEqual(single.cleaned_data["rate"], Decimal("42000"))
        self.assertIn(
            "bom-price-input",
            single.fields["rate"].widget.attrs.get("class", ""),
        )

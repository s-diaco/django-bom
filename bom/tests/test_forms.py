from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import translation

from bom.forms import (
    AddSubpartForm,
    PartFormSemiIntelligent,
    PartInfoForm,
    SellerPartForm,
)
from bom.helpers import (
    create_a_fake_organization,
    create_some_fake_manufacturers,
    create_some_fake_part_classes,
    create_some_fake_parts,
)
from bom.models import Part, Seller

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

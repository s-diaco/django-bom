"""Compose BOM TransactionTestCase suites from domain mixins."""

from re import finditer
from django.conf import settings
from django.test import Client, override_settings
from django.urls import reverse
from bom import constants
from bom.helpers import (
    create_a_fake_assembly,
    create_a_fake_part_revision,
    create_some_fake_part_classes,
    create_some_fake_parts,
    create_user_and_organization,
)
from bom.models import Part

from bom.tests.bom_case.base import TEST_FILES_DIR, TestBOMBase
from bom.tests.bom_case.home import HomeTestsMixin
from bom.tests.bom_case.part_info import PartInfoTestsMixin
from bom.tests.bom_case.parts import PartsTestsMixin
from bom.tests.bom_case.revisions import RevisionsTestsMixin
from bom.tests.bom_case.sellers import SellersTestsMixin
from bom.tests.bom_case.upload_bom import UploadBomTestsMixin
from bom.tests.bom_case.upload_parts import UploadPartsTestsMixin


@override_settings(BOM_CONFIG=settings.BOM_CONFIG_DEFAULT)
class TestBOM(
    HomeTestsMixin,
    PartInfoTestsMixin,
    UploadBomTestsMixin,
    PartsTestsMixin,
    UploadPartsTestsMixin,
    SellersTestsMixin,
    RevisionsTestsMixin,
    TestBOMBase,
):
    pass


@override_settings(BOM_CONFIG=settings.BOM_CONFIG_DEFAULT)
class TestBOMIntelligent(TestBOM):
    def setUp(self):
        self.client = Client()
        self.user, self.organization = create_user_and_organization()
        self.profile = self.user.bom_profile(organization=self.organization)
        self.organization.number_scheme = constants.NUMBER_SCHEME_INTELLIGENT
        self.organization.save()
        self.client.login(username="kasper", password="ghostpassword")

    def test_create_part(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        new_part_mpn = "STM32F401-NEW-PART"
        new_part_form_data = {
            "manufacturer_part_number": new_part_mpn,
            "manufacturer": p1.primary_manufacturer_part.manufacturer.id,
            "number_item": "ABC1",
            "configuration": "W",
            "description": "IC, MCU 32 Bit",
            "revision": "A",
            "attribute": "",
            "value": "",
        }

        response = self.client.post(reverse("bom:create-part"), new_part_form_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue("/part/" in response.url)

        try:
            created_part_id = response.url[6:-1]
            created_part = Part.objects.get(id=created_part_id)
        except IndexError:
            self.assertFalse(True, "Part maybe not created? Url looks like: {}".format(response.url))

        self.assertEqual(created_part.latest().description, "IC, MCU 32 Bit")
        self.assertEqual(
            created_part.manufacturer_parts().first().manufacturer_part_number,
            new_part_mpn,
        )

        new_part_form_data = {
            "manufacturer_part_number": "STM32F401",
            "manufacturer": p1.primary_manufacturer_part.manufacturer.id,
            "number_item": "9999",
            "description": "IC, MCU 32 Bit",
            "revision": "A",
        }

        response = self.client.post(reverse("bom:create-part"), new_part_form_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue("/part/" in response.url)

        new_part_form_data = {
            "manufacturer_part_number": "",
            "manufacturer": "",
            "number_item": "5432",
            "description": "IC, MCU 32 Bit",
            "revision": "A",
        }

        response = self.client.post(reverse("bom:create-part"), new_part_form_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue("/part/" in response.url)

        new_part_form_data = {
            "manufacturer_part_number": "",
            "manufacturer": "",
            "number_item": "1234A",
            "description": "IC, MCU 32 Bit",
            "revision": "A",
        }

        response = self.client.post(reverse("bom:create-part"), new_part_form_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue("/part/" in response.url)

        new_part_form_data = {
            "manufacturer_part_number": "",
            "manufacturer": "",
            "number_item": "1235",
            "description": "IC, MCU 32 Bit",
            "revision": "A",
        }

        response = self.client.post(reverse("bom:create-part"), new_part_form_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue("/part/" in response.url)

        # fail nicely
        new_part_form_data = {
            "manufacturer_part_number": "ABC123",
            "manufacturer": "",
            "number_item": p1.number_item,
            "description": "IC, MCU 32 Bit",
            "revision": "A",
        }

        response = self.client.post(reverse("bom:create-part"), new_part_form_data)
        self.assertEqual(response.status_code, 200)

        # Make sure only one part shows up
        response = self.client.post(reverse("bom:home"))
        self.assertEqual(response.status_code, 200)
        decoded_content = response.content.decode("utf-8")
        main_content = decoded_content[
            decoded_content.find("<main>") + len("<main>") : decoded_content.rfind("</main>")
        ]
        occurances = [m.start() for m in finditer(p1.full_part_number(), main_content)]
        self.assertEqual(len(occurances), 1)

    def test_create_part_no_manufacturer_part(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        # new_part_mpn = "STM32F401-NEW-PART"
        new_part_form_data = {
            "manufacturer_part_number": "",
            "manufacturer": "",
            "number_item": "2000",
            "configuration": "W",
            "description": "IC, MCU 32 Bit",
            "revision": "A",
            "attribute": "",
            "value": "",
        }

        # response = self.client.post(reverse("bom:create-part"), new_part_form_data)
        self.client.post(reverse("bom:create-part"), new_part_form_data)
        part = Part.objects.get(number_item="2000")
        self.assertEqual(len(part.manufacturer_parts()), 0)

    def test_part_edit(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        response = self.client.get(reverse("bom:part-edit", kwargs={"part_id": p1.id}))
        self.assertEqual(response.status_code, 200)

        edit_part_form_data = {
            "number_item": "HEYA",
        }

        response = self.client.post(reverse("bom:part-edit", kwargs={"part_id": p1.id}), edit_part_form_data)
        self.assertEqual(response.status_code, 302)

    def test_part_upload_bom(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        p5, _ = Part.objects.get_or_create(number_item="500-5555-00", organization=self.organization)
        assy = create_a_fake_assembly()
        # pr5 = create_a_fake_part_revision(part=p5, assembly=assy)
        create_a_fake_part_revision(part=p5, assembly=assy)

        p6, _ = Part.objects.get_or_create(number_item="200-3333-00", organization=self.organization)
        assy = create_a_fake_assembly()
        # pr6 = create_a_fake_part_revision(part=p5, assembly=assy)
        create_a_fake_part_revision(part=p5, assembly=assy)

        with open(f"{TEST_FILES_DIR}/test_bom.csv") as test_csv:
            response = self.client.post(
                reverse("bom:part-upload-bom", kwargs={"part_id": p2.id}),
                {"file": test_csv},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)

        messages = list(response.context.get("messages"))
        for msg in messages:
            self.assertNotEqual(
                msg.tags, "error"
            )  # Error loading 200-3333-00 via CSV because already in parent's BoM and has empty ref designators

        subparts = p2.latest().assembly.subparts.all()

        self.assertEqual(subparts[0].part_revision.part.full_part_number(), "3333")
        self.assertEqual(subparts[0].count, 4)
        self.assertEqual(subparts[1].part_revision.part.full_part_number(), "500-5555-00")
        self.assertEqual(subparts[1].reference, "U3, IC2, IC3")
        self.assertEqual(subparts[1].count, 3)
        self.assertEqual(subparts[1].do_not_load, False)
        self.assertEqual(subparts[2].part_revision.part.full_part_number(), "500-5555-00")
        self.assertEqual(subparts[2].reference, "R1, R2")
        self.assertEqual(subparts[2].count, 2)
        self.assertEqual(subparts[2].do_not_load, True)

    def test_upload_parts(self):
        create_some_fake_part_classes(self.organization)

        # part_count = Part.objects.all().count()
        # Should pass
        with open(f"{TEST_FILES_DIR}/test_new_parts_5_intelligent.csv") as test_csv:
            response = self.client.post(reverse("bom:upload-parts"), {"file": test_csv})
        self.assertEqual(response.status_code, 302)
        new_part_count = Part.objects.all().count()
        self.assertEqual(new_part_count, 4)

        # Part should be skipped because it already exists
        with open(f"{TEST_FILES_DIR}/test_new_parts_5_intelligent.csv") as test_csv:
            response = self.client.post(reverse("bom:upload-parts"), {"file": test_csv})
        self.assertEqual(response.status_code, 302)
        found_error = False
        for m in response.wsgi_request._messages:
            if "تعریف شده است" in str(m):
                found_error = True
        self.assertTrue(found_error)

        # Only one part should exist
        self.assertEqual(Part.objects.filter(number_item="C0402X5R10V001").count(), 1)

        # Uploading this BoM should work, and multiple parts should not be created
        p = Part.objects.first()
        with open(f"{TEST_FILES_DIR}/test_bom_5_intelligent.csv") as test_csv:
            response = self.client.post(
                reverse("bom:part-upload-bom", kwargs={"part_id": p.id}),
                {"file": test_csv},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)

        messages = list(response.context.get("messages"))
        for msg in messages:
            self.assertTrue("This should not happen." not in msg.message, msg=msg.message)

    def test_upload_part_with_sellers(self):
        # Should pass
        initial_parts_count = Part.objects.all().count()
        with open("bom/test_files/test_new_parts_sellers_intelligent.csv") as test_csv:
            response = self.client.post(reverse("bom:upload-parts"), {"file": test_csv})
        self.assertEqual(response.status_code, 302)

        parts_count = Part.objects.all().count()
        self.assertEqual(parts_count - initial_parts_count, 42)

    def test_upload_part_classes_parts_and_boms(self):
        # TODO: Make this more robust
        self.organization.number_item_len = 5
        self.organization.save()

        with open(f"{TEST_FILES_DIR}/test_new_parts_5_intelligent.csv") as test_csv:
            response = self.client.post(reverse("bom:upload-parts"), {"file": test_csv}, follow=True)
        messages = list(response.context.get("messages"))
        for msg in messages:
            self.assertEqual(msg.tags, "info")

        self.assertEqual(response.status_code, 200)
        new_part_count = Part.objects.all().count()
        self.assertEqual(new_part_count, 4)

        pcba = Part.objects.get(number_item="DYSON-123")

        with open(f"{TEST_FILES_DIR}/test_bom_5_intelligent.csv") as test_csv:
            response = self.client.post(
                reverse("bom:part-upload-bom", kwargs={"part_id": pcba.id}),
                {"file": test_csv},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)

        messages = list(response.context.get("messages"))

        for msg in messages:
            self.assertNotEqual(msg.tags, "error")
            self.assertEqual(msg.tags, "info")

        subparts = pcba.latest().assembly.subparts.all().order_by("id")
        self.assertEqual(subparts[0].reference, "C1, C2, C3")
        self.assertEqual(subparts[1].reference, "C4, C5")
        self.assertEqual(subparts[2].reference, "")

        pt1, pt2, pt3, pt4 = create_some_fake_parts(self.organization)
        with open(f"{TEST_FILES_DIR}/test_bom_5_intelligent_no_reference.csv") as test_csv:
            response = self.client.post(
                reverse("bom:part-upload-bom", kwargs={"part_id": pt1.id}),
                {"file": test_csv},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        subparts = pt1.latest().assembly.subparts.all().order_by("id")
        self.assertNotEqual(subparts[0].count, 0)
        self.assertNotEqual(subparts[1].count, 0)
        self.assertNotEqual(subparts[2].count, 0)


@override_settings(BOM_CONFIG=settings.BOM_CONFIG_DEFAULT)
class TestBOMNoVariation(TestBOM):
    def setUp(self):
        self.client = Client()
        self.user, self.organization = create_user_and_organization()
        self.profile = self.user.bom_profile(organization=self.organization)
        self.organization.number_variation_len = 0
        self.organization.save()
        self.client.login(username="kasper", password="ghostpassword")

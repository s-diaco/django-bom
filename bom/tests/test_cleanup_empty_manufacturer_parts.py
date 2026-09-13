from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.conf import settings
from django.urls import reverse
from io import StringIO

from bom import constants
from bom.helpers import (
    create_a_fake_seller_part,
    create_some_fake_parts,
    create_some_fake_sellers,
    create_user_and_organization,
)
from bom.models import Manufacturer, ManufacturerPart, Organization, Part, SellerPart


@override_settings(BOM_CONFIG=settings.BOM_CONFIG_DEFAULT)
class CleanupEmptyManufacturerPartsTests(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        (self.p1, self.p2, self.p3, self.p4) = create_some_fake_parts(
            organization=self.organization
        )
        self.real_mp = self.p1.primary_manufacturer_part
        self.blank_mfg_a = Manufacturer.objects.create(
            name="", organization=self.organization
        )
        self.blank_mfg_b = Manufacturer.objects.create(
            name="  ", organization=self.organization
        )
        self.empty_primary = ManufacturerPart.objects.create(
            part=self.p1,
            manufacturer=self.blank_mfg_a,
            manufacturer_part_number="",
        )
        self.empty_extra = ManufacturerPart.objects.create(
            part=self.p1,
            manufacturer=self.blank_mfg_b,
            manufacturer_part_number="",
        )
        self.p1.primary_manufacturer_part = self.empty_primary
        self.p1.save(update_fields=["primary_manufacturer_part"])

    def test_dry_run_does_not_delete(self):
        out = StringIO()
        call_command("cleanup_empty_manufacturer_parts", stdout=out)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.primary_manufacturer_part_id, self.empty_primary.id)
        self.assertTrue(ManufacturerPart.objects.filter(pk=self.empty_primary.id).exists())
        self.assertIn("DRY RUN", out.getvalue())
        self.assertIn("deletable: 2", out.getvalue())

    def test_execute_deletes_empties_and_repoints_primary(self):
        out = StringIO()
        call_command("cleanup_empty_manufacturer_parts", execute=True, stdout=out)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.primary_manufacturer_part_id, self.real_mp.id)
        self.assertFalse(ManufacturerPart.objects.filter(pk=self.empty_primary.id).exists())
        self.assertFalse(ManufacturerPart.objects.filter(pk=self.empty_extra.id).exists())
        self.assertTrue(ManufacturerPart.objects.filter(pk=self.real_mp.id).exists())
        self.assertFalse(Manufacturer.objects.filter(pk=self.blank_mfg_a.id).exists())
        self.assertFalse(Manufacturer.objects.filter(pk=self.blank_mfg_b.id).exists())
        self.assertIn("Deleted 2 manufacturer parts", out.getvalue())

    def test_skips_empty_manufacturer_part_with_seller_part(self):
        seller = create_some_fake_sellers(self.organization)[0]
        create_a_fake_seller_part(
            seller,
            self.empty_extra,
            moq=1,
            mpq=1,
            unit_cost=1,
            lead_time_days=1,
            nre_cost=0,
        )
        call_command("cleanup_empty_manufacturer_parts", execute=True, stdout=StringIO())
        self.assertTrue(ManufacturerPart.objects.filter(pk=self.empty_extra.id).exists())
        self.assertTrue(SellerPart.objects.filter(manufacturer_part=self.empty_extra).exists())
        self.assertFalse(ManufacturerPart.objects.filter(pk=self.empty_primary.id).exists())

    def test_clears_primary_when_no_keeper(self):
        part = self.p4
        blank_mfg = Manufacturer.objects.create(name="", organization=self.organization)
        empty_only = ManufacturerPart.objects.create(
            part=part, manufacturer=blank_mfg, manufacturer_part_number=""
        )
        part.primary_manufacturer_part = empty_only
        part.save(update_fields=["primary_manufacturer_part"])
        call_command("cleanup_empty_manufacturer_parts", execute=True, stdout=StringIO())
        part.refresh_from_db()
        self.assertIsNone(part.primary_manufacturer_part_id)
        self.assertFalse(ManufacturerPart.objects.filter(pk=empty_only.id).exists())

    def test_keeps_placeholder_manufacturer(self):
        placeholder = Manufacturer.objects.create(
            name="انتخاب نشده (پیش فرض)", organization=self.organization
        )
        mp = ManufacturerPart.objects.create(
            part=self.p2,
            manufacturer=placeholder,
            manufacturer_part_number=self.p2.number_item,
        )
        call_command("cleanup_empty_manufacturer_parts", execute=True, stdout=StringIO())
        self.assertTrue(Manufacturer.objects.filter(pk=placeholder.id).exists())
        self.assertTrue(ManufacturerPart.objects.filter(pk=mp.id).exists())

    def test_organization_id_limits_scope(self):
        other = Organization.objects.create(
            name="Other Org",
            subscription=constants.SUBSCRIPTION_TYPE_PRO,
            owner=self.user,
            number_scheme=constants.NUMBER_SCHEME_INTELLIGENT,
        )
        other_part = Part(organization=other, number_item="9999")
        other_part.save()
        other_mfg = Manufacturer.objects.create(name="", organization=other)
        other_empty = ManufacturerPart.objects.create(
            part=other_part, manufacturer=other_mfg, manufacturer_part_number=""
        )
        call_command(
            "cleanup_empty_manufacturer_parts",
            execute=True,
            organization_id=self.organization.id,
            stdout=StringIO(),
        )
        self.assertTrue(ManufacturerPart.objects.filter(pk=other_empty.id).exists())
        self.assertFalse(ManufacturerPart.objects.filter(pk=self.empty_primary.id).exists())

    def test_unknown_organization_id_errors(self):
        with self.assertRaises(CommandError):
            call_command(
                "cleanup_empty_manufacturer_parts",
                organization_id=999999,
                stdout=StringIO(),
            )


@override_settings(BOM_CONFIG=settings.BOM_CONFIG_DEFAULT)
class BomCsvImportSkipsEmptyManufacturerPartsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.organization = create_user_and_organization()
        self.user.bom_profile(organization=self.organization)
        self.client.login(username="kasper", password="ghostpassword")
        (self.p1, self.p2, self.p3, self.p4) = create_some_fake_parts(
            organization=self.organization
        )

    def test_upload_without_manufacturer_does_not_create_empty_mp(self):
        real_mp_id = self.p1.primary_manufacturer_part_id
        before = ManufacturerPart.objects.filter(part=self.p1).count()
        blank_before = Manufacturer.objects.filter(
            organization=self.organization, name=""
        ).count()
        pn = self.p1.full_part_number()
        csv_bytes = f"part_number,quantity,level\n{pn},1,1\n".encode()
        uploaded = SimpleUploadedFile("empty_mfg.csv", csv_bytes, content_type="text/csv")
        response = self.client.post(
            reverse("bom:part-upload-bom", kwargs={"part_id": self.p2.id}),
            {"file": uploaded},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.primary_manufacturer_part_id, real_mp_id)
        self.assertEqual(ManufacturerPart.objects.filter(part=self.p1).count(), before)
        self.assertEqual(
            Manufacturer.objects.filter(organization=self.organization, name="").count(),
            blank_before,
        )
        self.assertTrue(
            self.p2.latest().assembly.subparts.filter(part_revision__part=self.p1).exists()
        )

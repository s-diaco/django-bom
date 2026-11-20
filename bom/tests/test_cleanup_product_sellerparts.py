"""Tests for cleanup_product_sellerparts command and product SellerPart gates."""

from io import StringIO

from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from djmoney.money import Money

from bom.helpers import (
    create_a_fake_seller_part,
    create_some_fake_manufacturers,
    create_some_fake_part_classes,
    create_some_fake_sellers,
    create_user_and_organization,
)
from bom.management.commands.cleanup_product_sellerparts import (
    product_sellerparts_queryset,
)
from bom.models import ManufacturerPart, Part, PartRevision, SellerPart


class CleanupProductSellerPartsCommandTests(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        self.part_class = create_some_fake_part_classes(self.organization)[0]
        self.seller = create_some_fake_sellers(self.organization)[0]
        self.manufacturer = create_some_fake_manufacturers(self.organization)[0]
        self.currency = self.organization.currency

    def _make_part(self, number, material, with_seller=True):
        part = Part.objects.create(
            organization=self.organization,
            number_class=self.part_class,
            number_item=number,
        )
        mp = ManufacturerPart.objects.create(
            part=part,
            manufacturer=self.manufacturer,
            manufacturer_part_number=number,
        )
        part.primary_manufacturer_part = mp
        part.save()
        PartRevision.objects.create(
            part=part,
            revision="1",
            description=number,
            material=material,
        )
        seller_part = None
        if with_seller:
            seller_part = create_a_fake_seller_part(
                self.seller,
                mp,
                1,
                1,
                Money(10, self.currency),
                1,
                Money(0, self.currency),
            )
        return part, mp, seller_part

    def test_dry_run_does_not_delete(self):
        _prod, _mp, prod_sp = self._make_part("PROD1", "no_loi")
        _raw, _rmp, raw_sp = self._make_part("RAW1", "no_bom")

        out = StringIO()
        call_command("cleanup_product_sellerparts", stdout=out)
        output = out.getvalue()

        self.assertIn("Product SellerParts found: 1", output)
        self.assertIn("Dry-run", output)
        self.assertTrue(SellerPart.objects.filter(pk=prod_sp.pk).exists())
        self.assertTrue(SellerPart.objects.filter(pk=raw_sp.pk).exists())
        self.assertEqual(ManufacturerPart.objects.count(), 2)

    def test_execute_deletes_product_sellerparts_only(self):
        _prod, prod_mp, prod_sp = self._make_part("PROD2", "with_loi")
        _raw, raw_mp, raw_sp = self._make_part("RAW2", "no_bom")

        out = StringIO()
        call_command("cleanup_product_sellerparts", "--execute", stdout=out)
        output = out.getvalue()

        self.assertIn("Deleted product SellerParts: 1", output)
        self.assertFalse(SellerPart.objects.filter(pk=prod_sp.pk).exists())
        self.assertTrue(SellerPart.objects.filter(pk=raw_sp.pk).exists())
        # ManufacturerParts untouched.
        self.assertTrue(ManufacturerPart.objects.filter(pk=prod_mp.pk).exists())
        self.assertTrue(ManufacturerPart.objects.filter(pk=raw_mp.pk).exists())
        self.assertEqual(product_sellerparts_queryset().count(), 0)


class ProductSellerPartCreateBlockedTests(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        self.part_class = create_some_fake_part_classes(self.organization)[0]
        self.seller = create_some_fake_sellers(self.organization)[0]
        self.manufacturer = create_some_fake_manufacturers(self.organization)[0]
        self.currency = self.organization.currency
        self.client = Client()
        self.client.login(username="kasper", password="ghostpassword")

    def _make_part(self, number, material):
        part = Part.objects.create(
            organization=self.organization,
            number_class=self.part_class,
            number_item=number,
        )
        mp = ManufacturerPart.objects.create(
            part=part,
            manufacturer=self.manufacturer,
            manufacturer_part_number=number,
        )
        part.primary_manufacturer_part = mp
        part.save()
        PartRevision.objects.create(
            part=part,
            revision="1",
            description=number,
            material=material,
        )
        return part, mp

    def test_add_sellerpart_blocked_for_product(self):
        part, mp = self._make_part("BLK1", "no_loi")
        url = reverse(
            "bom:manufacturer-part-add-sellerpart",
            kwargs={"manufacturer_part_id": mp.id},
        )
        response = self.client.post(
            url,
            {
                "name": "Should Not Create",
                "seller_part_number": "BLOCK-1",
                "currency": self.currency,
                "unit_cost": "10",
                "shipping": "0",
                "customs_duty_percent": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(mp.sellerpart_set.count(), 0)
        self.assertIn(f"/part/{part.id}", response.url)

    def test_add_sellerpart_for_part_blocked_for_product(self):
        part, mp = self._make_part("BLK2", "no_loi")
        response = self.client.get(
            reverse("bom:part-add-sellerpart", kwargs={"part_id": part.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(mp.sellerpart_set.count(), 0)
        self.assertNotIn("add-sellerpart", response.url)

    def test_sellerpart_edit_blocked_for_product(self):
        part, mp = self._make_part("BLK3", "no_loi")
        sp = create_a_fake_seller_part(
            self.seller,
            mp,
            1,
            1,
            Money(10, self.currency),
            1,
            Money(0, self.currency),
        )
        response = self.client.get(
            reverse("bom:sellerpart-edit", kwargs={"sellerpart_id": sp.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/part/{part.id}", response.url)

    def test_add_sellerpart_allowed_for_raw_material(self):
        _part, mp = self._make_part("RAWX", "no_bom")
        url = reverse(
            "bom:manufacturer-part-add-sellerpart",
            kwargs={"manufacturer_part_id": mp.id},
        )
        response = self.client.post(
            url,
            {
                "name": "Raw Seller",
                "seller_part_number": "RAW-OK",
                "currency": self.currency,
                "unit_cost": "5",
                "shipping": "0",
                "customs_duty_percent": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(mp.sellerpart_set.count(), 1)
        self.assertEqual(mp.sellerpart_set.get().seller.name, "Raw Seller")

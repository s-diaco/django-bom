"""materials/?product=0 is the complement of product=1 (LI-134)."""

from django.test import Client, TestCase
from django.urls import reverse

from bom.helpers import (
    create_some_fake_manufacturers,
    create_some_fake_part_classes,
    create_user_and_organization,
)
from bom.models import ManufacturerPart, Part, PartRevision


class MaterialsProductFilterTests(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        self.organization.ensure_default_product_types()
        self.part_class = create_some_fake_part_classes(self.organization)[0]
        self.manufacturer = create_some_fake_manufacturers(self.organization)[0]
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
            configuration="W",
        )
        return part

    def _numbers(self, response):
        return {pr.part.full_part_number() for pr in response.context["part_revs"]}

    def test_product_0_is_complement_of_product_1(self):
        product = self._make_part("PRD1", "no_loi")
        raw = self._make_part("RAW1", "no_bom")
        blank = self._make_part("BLK1", "")
        null_mat = self._make_part("NUL1", None)
        orphan = self._make_part("ORP1", "legacy_orphan_code")

        products = self.client.get(reverse("bom:materials"), {"product": "1"})
        self.assertEqual(products.status_code, 200)
        product_numbers = self._numbers(products)
        self.assertEqual(product_numbers, {product.full_part_number()})

        raws = self.client.get(reverse("bom:materials"), {"product": "0"})
        self.assertEqual(raws.status_code, 200)
        raw_numbers = self._numbers(raws)
        self.assertEqual(
            raw_numbers,
            {
                raw.full_part_number(),
                blank.full_part_number(),
                null_mat.full_part_number(),
                orphan.full_part_number(),
            },
        )
        self.assertNotIn(product.full_part_number(), raw_numbers)

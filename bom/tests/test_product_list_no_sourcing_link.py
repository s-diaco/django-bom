"""Products list must not link to the Seller/sourcing tab (LI-116 follow-up)."""

from django.test import Client, TestCase
from django.urls import reverse

from bom.helpers import (
    create_some_fake_manufacturers,
    create_some_fake_part_classes,
    create_some_fake_sellers,
    create_user_and_organization,
)
from bom.models import ManufacturerPart, Part, PartRevision


class ProductListNoSourcingLinkTests(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        self.part_class = create_some_fake_part_classes(self.organization)[0]
        self.manufacturer = create_some_fake_manufacturers(self.organization)[0]
        create_some_fake_sellers(self.organization)
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

    def test_products_list_omits_sourcing_and_sellerpart_links(self):
        product = self._make_part("PRD1", "no_loi")
        response = self.client.get(reverse("bom:materials"), {"product": "1"})
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn(product.full_part_number(), html)
        self.assertNotIn("tab_anchor=sourcing", html)
        self.assertNotIn("sellerpart-edit", html)
        # Product actions still include BoM / where-used.
        self.assertIn("tab_anchor=bom", html)
        self.assertIn("tab_anchor=used", html)

    def test_raw_materials_list_keeps_sourcing_link_when_no_seller(self):
        raw = self._make_part("RAW1", "no_bom")
        response = self.client.get(reverse("bom:materials"), {"product": "0"})
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn(raw.full_part_number(), html)
        self.assertIn(
            f"/part/{raw.id}/?tab_anchor=sourcing",
            html.replace("&amp;", "&"),
        )

"""BOM tests: sellers."""

from django.urls import reverse
from bom.helpers import (
    create_some_fake_parts,
)
from bom.models import Manufacturer, ManufacturerPart


class SellersTestsMixin:
    def test_add_sellerpart(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        response = self.client.get(
            reverse(
                "bom:manufacturer-part-add-sellerpart",
                kwargs={"manufacturer_part_id": p1.primary_manufacturer_part.id},
            )
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse(
                "bom:manufacturer-part-add-sellerpart",
                kwargs={"manufacturer_part_id": p1.primary_manufacturer_part.id},
            )
        )
        self.assertEqual(response.status_code, 302)

        new_sellerpart_form_data = {
            "seller": p1.optimal_seller().seller.id,
            "seller_part_number": p1.optimal_seller().seller_part_number,
            "minimum_order_quantity": 1000,
            "minimum_pack_quantity": 500,
            "currency": self.organization.currency,
            "unit_cost": "123",
            "lead_time_days": 25,
            "nre_cost": 2000,
            "ncnr": False,
        }

        response = self.client.post(
            reverse(
                "bom:manufacturer-part-add-sellerpart",
                kwargs={"manufacturer_part_id": p1.primary_manufacturer_part.id},
            ),
            new_sellerpart_form_data,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue("/part/" in response.url)

    def test_add_sellerpart_allows_custom_seller_for_product(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        rev = p1.latest()
        rev.material = "no_loi"
        rev.save()
        mp_id = p1.primary_manufacturer_part.id
        url = reverse(
            "bom:manufacturer-part-add-sellerpart",
            kwargs={"manufacturer_part_id": mp_id},
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "readonly")

        response = self.client.post(
            url,
            {
                "name": "Tampered Seller",
                "seller_part_number": "ORG-LOCK-1",
                "currency": self.organization.currency,
                "unit_cost": "10",
                "shipping": "0",
                "customs_duty_percent": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        seller_part = p1.primary_manufacturer_part.sellerpart_set.latest("id")
        self.assertEqual(seller_part.seller.name, "Tampered Seller")

    def test_add_sellerpart_allows_custom_seller_for_raw_material(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        rev = p1.latest()
        rev.material = "no_bom"
        rev.save()
        url = reverse(
            "bom:manufacturer-part-add-sellerpart",
            kwargs={"manufacturer_part_id": p1.primary_manufacturer_part.id},
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "readonly")

        response = self.client.post(
            url,
            {
                "name": "Custom Raw Seller",
                "seller_part_number": "RAW-1",
                "currency": self.organization.currency,
                "unit_cost": "5",
                "shipping": "0",
                "customs_duty_percent": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        seller_part = p1.primary_manufacturer_part.sellerpart_set.latest("id")
        self.assertEqual(seller_part.seller.name, "Custom Raw Seller")

    def test_sellerpart_edit(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        edit_sellerpart_form_data = {
            "new_seller": "indabom",
            "seller_part_number": "123-45678",
            "minimum_order_quantity": 100,
            "minimum_pack_quantity": 200,
            "currency": self.organization.currency,
            "unit_cost": "12",
            "lead_time_days": 5,
            "nre_cost": 1000,
            "ncnr": True,
        }

        response = self.client.post(
            reverse("bom:sellerpart-edit", kwargs={"sellerpart_id": p1.optimal_seller().id}),
            edit_sellerpart_form_data,
        )
        self.assertEqual(response.status_code, 302)

    def test_sellerpart_delete(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        response = self.client.post(
            reverse(
                "bom:sellerpart-delete",
                kwargs={"sellerpart_id": p1.optimal_seller().id},
            )
        )

        self.assertEqual(response.status_code, 302)

    def test_add_manufacturer_part(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        # Test GET
        response = self.client.get(reverse("bom:part-add-manufacturer-part", kwargs={"part_id": p1.id}))

        # Test POSTs
        mfg_form_data = {
            "name": p1.primary_manufacturer_part.manufacturer.name,
            "manufacturer_part_number": p1.primary_manufacturer_part.manufacturer_part_number,
            "part": p2.id,
        }
        response = self.client.post(
            reverse("bom:part-add-manufacturer-part", kwargs={"part_id": p1.id}),
            mfg_form_data,
        )
        self.assertEqual(response.status_code, 302)

        mfg_form_data = {
            "name": "A new mfg name",
            "manufacturer_part_number": "a new pn",
            "part": p2.id,
        }
        response = self.client.post(
            reverse("bom:part-add-manufacturer-part", kwargs={"part_id": p1.id}),
            mfg_form_data,
        )
        self.assertEqual(response.status_code, 302)

    def test_manufacturers(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        response = self.client.post(reverse("bom:manufacturers"))
        self.assertEqual(response.status_code, 200)

    def test_manufacturer_info(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        response = self.client.post(
            reverse(
                "bom:manufacturer-info",
                kwargs={"manufacturer_id": p1.primary_manufacturer_part.manufacturer.id},
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_manufacturer_edit(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        response = self.client.post(
            reverse(
                "bom:manufacturer-edit",
                kwargs={"manufacturer_id": p1.primary_manufacturer_part.manufacturer.id},
            )
        )
        self.assertEqual(response.status_code, 302)

    def test_manufacturer_delete(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        manufacturer_id = p1.primary_manufacturer_part.manufacturer.id
        response = self.client.post(
            reverse(
                "bom:manufacturer-delete",
                kwargs={"manufacturer_id": manufacturer_id},
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Manufacturer.objects.filter(id=manufacturer_id).exists())

    def test_sellers(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        response = self.client.post(reverse("bom:sellers"))
        self.assertEqual(response.status_code, 200)

    def test_seller_info(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        response = self.client.post(
            reverse(
                "bom:seller-info",
                kwargs={"seller_id": p2.primary_manufacturer_part.optimal_seller().seller_id},
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_seller_edit(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        response = self.client.post(
            reverse(
                "bom:seller-edit",
                kwargs={"seller_id": p2.primary_manufacturer_part.optimal_seller().seller_id},
            ),
            {"name": "Mousah"},
        )
        self.assertEqual(response.status_code, 302)

    def test_seller_delete(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        response = self.client.post(
            reverse(
                "bom:seller-delete",
                kwargs={"seller_id": p2.primary_manufacturer_part.optimal_seller().seller_id},
            )
        )
        self.assertEqual(response.status_code, 302)

    def test_manufacturer_part_edit(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        response = self.client.post(
            reverse(
                "bom:manufacturer-part-edit",
                kwargs={"manufacturer_part_id": p1.primary_manufacturer_part.id},
            )
        )
        self.assertEqual(response.status_code, 200)

        data = {
            "manufacturer_part_number": "ABC123",
            "manufacturer": p1.primary_manufacturer_part.manufacturer.id,
            "name": "",
        }

        response = self.client.post(
            reverse(
                "bom:manufacturer-part-edit",
                kwargs={"manufacturer_part_id": p1.primary_manufacturer_part.id},
            ),
            data,
        )
        self.assertEqual(response.status_code, 302)

        data = {
            "manufacturer_part_number": "ABC123",
            "manufacturer": p1.primary_manufacturer_part.manufacturer.id,
            "name": "A new manufacturer",
        }

        old_id = p1.primary_manufacturer_part.manufacturer.id
        response = self.client.post(
            reverse(
                "bom:manufacturer-part-edit",
                kwargs={"manufacturer_part_id": p1.primary_manufacturer_part.id},
            ),
            data,
        )
        self.assertEqual(response.status_code, 302)
        p1.refresh_from_db()
        self.assertNotEqual(p1.primary_manufacturer_part.manufacturer.id, old_id)

        data = {
            "manufacturer_part_number": "ABC123",
            "manufacturer": "",
            "name": "",
        }

        response = self.client.post(
            reverse(
                "bom:manufacturer-part-edit",
                kwargs={"manufacturer_part_id": p1.primary_manufacturer_part.id},
            ),
            data,
        )
        self.assertEqual(response.status_code, 200)  # 200 means it failed validation

    def test_manufacturer_part_delete(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        manufacturer_part_id = p1.primary_manufacturer_part.id
        response = self.client.post(
            reverse(
                "bom:manufacturer-part-delete",
                kwargs={"manufacturer_part_id": manufacturer_part_id},
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(ManufacturerPart.objects.filter(id=manufacturer_part_id).exists())

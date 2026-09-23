"""BOM tests: parts."""

from re import finditer
from django.urls import reverse
from bom import constants
from bom.helpers import (
    create_a_fake_subpart,
    create_some_fake_parts,
)
from bom.models import Part, PartClass, Subpart


class PartsTestsMixin:
    def test_create_edit_part_class(self):
        part_class_code = 978
        part_class_form_data = {
            "submit-part-class-create": "",
            "code": part_class_code,
            "name": "test part name",
            "comment": "this test part class description!",
        }

        response = self.client.post(reverse("bom:settings"), part_class_form_data)
        self.assertEqual(response.status_code, 200)

        part_classes = PartClass.objects.filter(code=part_class_code)
        self.assertEqual(part_classes.count(), 1)
        part_class = part_classes[0]

        # Test edit
        part_class_form_data["name"] = "edited test part name"

        response = self.client.post(
            reverse("bom:part-class-edit", kwargs={"part_class_id": part_class.id}),
            part_class_form_data,
        )
        self.assertEqual(response.status_code, 302)

        part_class = PartClass.objects.get(id=part_class.id)
        self.assertEqual(part_class.name, part_class_form_data["name"])

    def test_create_part(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        new_part_mpn = "STM32F401-NEW-PART"
        new_part_form_data = {
            "manufacturer_part_number": new_part_mpn,
            "manufacturer": p1.primary_manufacturer_part.manufacturer.id,
            "number_class": str(p1.number_class),
            "number_item": "",
            "number_variation": "",
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
            "number_class": str(p1.number_class),
            "number_item": "9999",
            "description": "IC, MCU 32 Bit",
            "revision": "A",
        }

        if self.organization.number_variation_len > 0:
            new_part_form_data["number_variation"] = "01"

        response = self.client.post(reverse("bom:create-part"), new_part_form_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue("/part/" in response.url)

        new_part_form_data = {
            "manufacturer_part_number": "",
            "manufacturer": "",
            "number_class": str(p1.number_class),
            "number_item": "",
            "number_variation": "",
            "description": "IC, MCU 32 Bit",
            "revision": "A",
        }

        response = self.client.post(reverse("bom:create-part"), new_part_form_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue("/part/" in response.url)

        new_part_form_data = {
            "manufacturer_part_number": "",
            "manufacturer": "",
            "number_class": str(p1.number_class),
            "number_item": "1234",
            "description": "IC, MCU 32 Bit",
            "revision": "A",
        }

        if self.organization.number_variation_len > 0:
            new_part_form_data["number_variation"] = "AZ"

        response = self.client.post(reverse("bom:create-part"), new_part_form_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue("/part/" in response.url)

        new_part_form_data = {
            "manufacturer_part_number": "",
            "manufacturer": "",
            "number_class": str(p1.number_class),
            "number_item": "1235",
            "number_variation": "",
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
            "number_class": str(p1.number_class),
            "number_item": "",
            "number_variation": "",
            "description": "IC, MCU 32 Bit",
            "revision": "A",
        }

        response = self.client.post(reverse("bom:create-part"), new_part_form_data)
        self.assertEqual(response.status_code, 200)

        # Make sure only one part shows up
        response = self.client.get(reverse("bom:home"))
        self.assertEqual(response.status_code, 200)
        decoded_content = response.content.decode("utf-8")
        main_content = decoded_content[
            decoded_content.find("<main>") + len("<main>") : decoded_content.rfind("</main>")
        ]

        occurances = [m.start() for m in finditer(p1.full_part_number(), main_content)]
        self.assertEqual(len(occurances), 1)

    def test_create_part_variation(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        if self.organization.number_scheme == constants.NUMBER_SCHEME_INTELLIGENT:
            # Intelligent numbering has no variations; duplicate number_item must fail.
            data = {
                "manufacturer_part_number": "STM32F401-NEW-PART",
                "manufacturer": p1.primary_manufacturer_part.manufacturer.id,
                "number_item": "UNIQUE-VAR-TEST",
                "configuration": "W",
                "description": "IC, MCU 32 Bit",
                "revision": "A",
                "attribute": "",
                "value": "",
            }
            response = self.client.post(reverse("bom:create-part"), data)
            self.assertEqual(response.status_code, 302)
            self.assertTrue("/part/" in response.url)
            response = self.client.post(reverse("bom:create-part"), data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue("error" in str(response.content))
            self._assert_part_number_already_in_use(response)
            return

        new_part_mpn = "STM32F401-NEW-PART"
        new_part_form_data = {
            "manufacturer_part_number": new_part_mpn,
            "manufacturer": p1.primary_manufacturer_part.manufacturer.id,
            "number_class": (p1.number_class),
            "number_item": "2000",
            "configuration": "W",
            "description": "IC, MCU 32 Bit",
            "revision": "A",
            "attribute": "",
            "value": "",
        }

        if self.organization.number_variation_len > 0:
            new_part_form_data["number_variation"] = "01"
            response = self.client.post(reverse("bom:create-part"), new_part_form_data)
            new_part_form_data["number_variation"] = "02"
            response = self.client.post(reverse("bom:create-part"), new_part_form_data)
            # Part should be created because the variation is different
            self.assertEqual(response.status_code, 302)
            self.assertTrue("/part/" in response.url)

            response = self.client.post(reverse("bom:create-part"), new_part_form_data)
            # Same variation again must fail
            self.assertEqual(response.status_code, 200)
            self.assertTrue("error" in str(response.content))
            self._assert_part_number_already_in_use(response)
        else:
            # Without variations, the second identical create must fail
            response = self.client.post(reverse("bom:create-part"), new_part_form_data)
            self.assertEqual(response.status_code, 302)
            self.assertTrue("/part/" in response.url)
            response = self.client.post(reverse("bom:create-part"), new_part_form_data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue("error" in str(response.content))
            self._assert_part_number_already_in_use(response)

    def test_create_part_no_manufacturer_part(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        # new_part_mpn = "STM32F401-NEW-PART"
        new_part_form_data = {
            "manufacturer_part_number": "",
            "manufacturer": "",
            "number_class": str(p1.number_class),
            "number_item": "2000",
            "configuration": "W",
            "description": "IC, MCU 32 Bit",
            "revision": "A",
            "attribute": "",
            "value": "",
        }

        number_variation = None
        if self.organization.number_variation_len > 0:
            number_variation = "01"
            new_part_form_data["number_variation"] = number_variation

        # response = self.client.post(reverse("bom:create-part"), new_part_form_data)
        self.client.post(reverse("bom:create-part"), new_part_form_data)
        part = Part.objects.get(
            number_class=p1.number_class.id,
            number_item="2000",
            number_variation=number_variation,
        )
        self.assertEqual(len(part.manufacturer_parts()), 0)

    def test_part_edit(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        response = self.client.get(reverse("bom:part-edit", kwargs={"part_id": p1.id}))
        self.assertEqual(response.status_code, 200)

        edit_part_form_data = {
            "number_class": str(p1.number_class),
            "number_item": "",
            "number_variation": "",
        }

        response = self.client.post(reverse("bom:part-edit", kwargs={"part_id": p1.id}), edit_part_form_data)
        self.assertEqual(response.status_code, 302)

    def test_part_delete(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        response = self.client.post(reverse("bom:part-delete", kwargs={"part_id": p1.id}))
        self.assertEqual(response.status_code, 302)

    def test_add_subpart(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        # Submit with no form data
        response = self.client.post(
            reverse(
                "bom:part-add-subpart",
                kwargs={
                    "part_id": p1.id,
                    "part_revision_id": p1.latest().id,
                },
            )
        )
        self.assertEqual(response.status_code, 302)

        # Test adding two of the same subparts that also have assemblies. Make sure quantity gets incremented, and not 2 parts that are the same added
        form_data = {
            "subpart_part_number": p2.full_part_number(),
            "count": 3,
            "reference": "",
            "do_not_load": False,
        }
        response = self.client.post(
            reverse(
                "bom:part-add-subpart",
                kwargs={
                    "part_id": p3.id,
                    "part_revision_id": p3.latest().id,
                },
            ),
            form_data,
        )
        self.assertEqual(response.status_code, 302)

        # Below - make sure quantity gets incremented, not that there are > 1 parts
        repeat_part_revision = p2.latest()
        parts_p2 = 0
        qty_p2 = 0
        indented_bom = p3.latest().indented()
        for _, p in indented_bom.parts.items():
            if p.part_revision == repeat_part_revision:
                parts_p2 += 1
                qty_p2 = p.quantity
        self.assertEqual(1, parts_p2)
        self.assertEqual(7, qty_p2)

        # Test adding a third, but make it DNL
        form_data = {
            "subpart_part_number": p2.full_part_number(),
            "count": 3,
            "reference": "",
            "do_not_load": True,
        }
        response = self.client.post(
            reverse(
                "bom:part-add-subpart",
                kwargs={
                    "part_id": p3.id,
                    "part_revision_id": p3.latest().id,
                },
            ),
            form_data,
        )
        self.assertEqual(response.status_code, 302)

        # Below - make sure quantity gets incremented, not that there are > 1 parts
        repeat_part_revision = p2.latest()
        parts_p2 = 0
        qty_p2_load = 0
        qty_p2_do_not_load = 0
        indented_bom = p3.latest().indented()
        for _, p in indented_bom.parts.items():
            if p.part_revision == repeat_part_revision:
                parts_p2 += 1
            if p.part_revision == repeat_part_revision and p.do_not_load:
                qty_p2_do_not_load += p.quantity
            elif p.part_revision == repeat_part_revision:
                qty_p2_load += p.quantity

        self.assertEqual(2, parts_p2)
        self.assertEqual(3, qty_p2_do_not_load)
        self.assertEqual(7, qty_p2_load)

    def test_add_subpart_infinite_recursion(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        # Test preventing infinite recursion
        form_data = {
            "subpart_part_number": p3.full_part_number(),
            "count": 3,
            "reference": "",
            "do_not_load": False,
        }
        response = self.client.post(
            reverse(
                "bom:part-add-subpart",
                kwargs={
                    "part_id": p3.id,
                    "part_revision_id": p3.latest().id,
                },
            ),
            form_data,
        )
        self.assertEqual(response.status_code, 302)
        found_error = False
        rejected_add = False
        for m in response.wsgi_request._messages:
            if "Added" in str(m):
                found_error = True
            if "Infinite recursion!" in str(m):
                rejected_add = True
        self.assertFalse(found_error)
        self.assertTrue(rejected_add)

        # Test preventing infinite recursion - Check that a subpart doesnt exist in a parent's parent assy / deep recursion
        # p3 has p2 in its assy, dont let p2 add p3 to it
        form_data = {
            "subpart_part_number": p3.full_part_number(),
            "count": 3,
            "reference": "",
            "do_not_load": False,
        }
        response = self.client.post(
            reverse(
                "bom:part-add-subpart",
                kwargs={
                    "part_id": p2.id,
                    "part_revision_id": p2.latest().id,
                },
            ),
            form_data,
        )
        self.assertEqual(response.status_code, 302)
        found_error = False
        rejected_add = False
        for m in response.wsgi_request._messages:
            if "Added" in str(m):
                found_error = True
            if "Infinite recursion!" in str(m):
                rejected_add = True
        self.assertFalse(found_error)
        self.assertTrue(rejected_add)

    def test_remove_subpart(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        s1 = create_a_fake_subpart(p1.latest(), count=10)

        response = self.client.post(
            reverse(
                "bom:part-remove-subpart",
                kwargs={
                    "part_id": p1.id,
                    "subpart_id": s1.id,
                    "part_revision_id": p1.latest().id,
                },
            )
        )
        self.assertEqual(response.status_code, 302)

    def test_remove_all_subparts(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        part = p3
        part_revision = part.latest()

        subparts = part_revision.assembly.subparts.all()
        subpart_ids = list(subparts.values_list("id", flat=True))

        response = self.client.post(
            reverse(
                "bom:part-remove-all-subparts",
                kwargs={"part_id": part.id, "part_revision_id": part_revision.id},
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(0, len(part_revision.assembly.subparts.all()))

        subparts = Subpart.objects.filter(id__in=subpart_ids)
        self.assertEqual(0, len(subparts))

    def test_create_part_non_raw_defaults_seller_from_org_and_code(self):
        from bom.models import Seller, SellerPart

        (p1, _p2, _p3, _p4) = create_some_fake_parts(organization=self.organization)
        self.organization.ensure_default_product_types()
        raw_codes = self.organization.product_type_codes(has_bom=False)
        product_code = next(
            code
            for code in self.organization.product_type_codes(has_bom=True)
            if code not in raw_codes
        )

        number_item = "8877"
        data = {
            "manufacturer_part_number": "",
            "manufacturer": "",
            "number_class": str(p1.number_class),
            "number_item": number_item,
            "configuration": "W",
            "description": "Non-raw product part",
            "revision": "A",
            "attribute": "",
            "value": "",
            "material": product_code,
            "tolerance": "12",
            "unit_cost": "5",
            "currency": self.organization.currency,
            # Intentionally omit seller / seller_part_number — server fills defaults.
        }
        if self.organization.number_variation_len > 0:
            data["number_variation"] = "01"
        if self.organization.number_scheme == constants.NUMBER_SCHEME_INTELLIGENT:
            data.pop("number_class", None)
            data.pop("number_variation", None)

        response = self.client.post(reverse("bom:create-part"), data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue("/part/" in response.url)

        created_part = Part.objects.get(id=response.url.strip("/").split("/")[-1])
        self.assertEqual(created_part.number_item, number_item)
        self.assertEqual(created_part.latest().material, product_code)

        seller = Seller.objects.get(
            organization=self.organization, name=self.organization.name
        )
        seller_part = SellerPart.objects.get(
            manufacturer_part__part=created_part,
            seller_part_number=number_item,
        )
        self.assertEqual(seller_part.seller_id, seller.id)

    def test_create_part_page_marks_raw_material_toggles(self):
        self.organization.ensure_default_product_types()
        response = self.client.get(reverse("bom:create-part"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("data-create-part-toggles", html)
        self.assertIn('id="create-part-loi-row"', html)
        self.assertIn('id="create-part-seller-identity"', html)
        for code in self.organization.product_type_codes(has_bom=False):
            self.assertIn(code, html)
        self.assertNotIn("Part Revision", html)

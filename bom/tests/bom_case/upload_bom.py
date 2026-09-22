"""BOM tests: upload bom."""

import csv
import re
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from parameterized import parameterized
from bom import constants
from bom.helpers import (
    create_a_fake_assembly,
    create_a_fake_part_revision,
    create_some_fake_parts,
)
from bom.models import ManufacturerPart, Part
from bom.utils import convert_arabic_to_english
from bom.tests.bom_case.base import TEST_FILES_DIR


class UploadBomTestsMixin:
    def test_part_upload_bom(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        test_file = "test_bom.csv" if self.organization.number_variation_len > 0 else "test_bom_6_no_variations.csv"
        with open(f"{TEST_FILES_DIR}/{test_file}") as test_csv:
            response = self.client.post(
                reverse("bom:part-upload-bom", kwargs={"part_id": p2.id}),
                {"file": test_csv},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)

        messages = list(response.context.get("messages"))
        for msg in messages:
            self.assertNotEqual(msg.tags, "error")

        subparts = p2.latest().assembly.subparts.all()

        expected_pn = "200-3333-00" if self.organization.number_variation_len > 0 else "200-3333"
        self.assertEqual(subparts[0].part_revision.part.full_part_number(), expected_pn)
        self.assertEqual(subparts[0].count, 104)  # append 4, 99, 1

        expected_pn = "500-5555-00" if self.organization.number_variation_len > 0 else "500-5555"
        self.assertEqual(subparts[1].part_revision.part.full_part_number(), expected_pn)
        self.assertEqual(subparts[1].reference, "U3, IC2, IC3")
        self.assertEqual(subparts[1].count, 3)
        self.assertEqual(subparts[1].do_not_load, False)

        self.assertEqual(subparts[2].part_revision.part.full_part_number(), expected_pn)
        self.assertEqual(subparts[2].reference, "R1, R2")
        self.assertEqual(subparts[2].count, 2)
        self.assertEqual(subparts[2].do_not_load, True)

        with open(f"{TEST_FILES_DIR}/test_bom_2.csv") as test_csv:
            response = self.client.post(
                reverse("bom:part-upload-bom", kwargs={"part_id": p1.id}),
                {"file": test_csv},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)

        messages = list(response.context.get("messages"))
        for idx, msg in enumerate(messages):
            self.assertTrue(
                "Row 5 - manufacturer_part_number: Uploading of this subpart skipped. No part found for manufacturer part number."
                in str(msg.message)
            )
            self.assertTrue(
                "Row 6 - manufacturer_part_number: Uploading of this subpart skipped. No part found for manufacturer part number."
                in str(msg.message)
            )

        p1.refresh_from_db()
        bom = p1.latest().indented()
        self.assertEqual(len(bom.parts), 3)

    def test_part_upload_bom_no_duplicate_manufacturer_parts(self):
        """CSV BOM import should reuse existing ManufacturerPart records, not create duplicates."""
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        # p1 already has a ManufacturerPart with manufacturer_part_number="STM32F401CEU6"
        # and manufacturer="STMicroelectronics" (created by create_some_fake_parts)
        initial_mp_count = ManufacturerPart.objects.filter(
            part=p1,
            manufacturer_part_number="STM32F401CEU6",
        ).count()
        self.assertEqual(initial_mp_count, 1)

        test_file = (
            "test_bom_existing_mfr_part.csv"
            if self.organization.number_variation_len > 0
            else "test_bom_existing_mfr_part_no_variations.csv"
        )

        # Upload a CSV that references the same part with the same manufacturer part number
        with open(f"{TEST_FILES_DIR}/{test_file}") as test_csv:
            response = self.client.post(
                reverse("bom:part-upload-bom", kwargs={"part_id": p2.id}),
                {"file": test_csv},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)

        messages = list(response.context.get("messages"))
        for msg in messages:
            self.assertNotEqual(msg.tags, "error")

        # Verify no duplicate ManufacturerPart was created
        final_mp_count = ManufacturerPart.objects.filter(
            part=p1,
            manufacturer_part_number="STM32F401CEU6",
        ).count()
        self.assertEqual(
            final_mp_count,
            initial_mp_count,
            "CSV import should reuse existing ManufacturerPart, not create a duplicate.",
        )

    def test_upload_bom(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        # Test OK page visit
        response = self.client.get(reverse("bom:upload-bom"))
        self.assertEqual(response.status_code, 200)

        # Test OK upload
        test_file = (
            "test_full_bom.csv" if self.organization.number_variation_len > 0 else "test_full_bom_no_variations.csv"
        )
        with open(f"{TEST_FILES_DIR}/{test_file}") as test_csv:
            response = self.client.post(reverse("bom:upload-bom"), {"file": test_csv}, follow=True)
        self.assertEqual(response.status_code, 200)

        with open(f"{TEST_FILES_DIR}/{test_file}") as test_csv:
            reader = csv.DictReader(test_csv)
            test_list = list(reader)

        messages = list(response.context.get("messages"))
        for msg in messages:
            self.assertEqual(msg.tags, "info")
            self.assertNotEqual(msg.tags, "error")

        parent_part_number = "100-0001-02" if self.organization.number_variation_len > 0 else "100-0001"
        parent_part = Part.from_part_number(parent_part_number, organization=self.organization)
        bom = parent_part.indented()
        bom_list = list(bom.parts.values())
        self.assertEqual(len(bom.parts), len(test_list))

        # Check that we successfully updated an existing part (only tested for semi-intelligent scheme for now)
        if self.organization.number_scheme == constants.NUMBER_SCHEME_SEMI_INTELLIGENT:
            p2.refresh_from_db()
            p2_rev = p2.latest()
            p2_mp = p2.primary_manufacturer_part
            self.assertEqual(p2_rev.revision, "88")  # previously 1
            self.assertEqual(p2_rev.description, "123")  # previously 'Brown dog'
            self.assertEqual(p2_mp.manufacturer.name, "a new manufacturer name")  # previously None
            self.assertEqual(p2_mp.manufacturer_part_number, "a new mpn")  # previously 'GRM1555C1H100JA01D'

        # Check that parts get uploaded correctly
        for idx, item in enumerate(test_list):
            assertion_message = (
                f"Index: {idx}, CSV PN: {item['part_number']}, BoM PN: {bom_list[idx].part.full_part_number()}"
            )
            self.assertEqual(int(float(item["level"])), bom_list[idx].indent_level, assertion_message)
            self.assertEqual(
                item["part_number"],
                bom_list[idx].part.full_part_number(),
                assertion_message,
            )
            self.assertEqual(
                item["revision"],
                bom_list[idx].part_revision.revision,
                assertion_message,
            )
            primary_mp = bom_list[idx].part.primary_manufacturer_part
            manufacturer_name = (
                primary_mp.manufacturer.name if primary_mp is not None and primary_mp.manufacturer is not None else ""
            )
            manufacturer_part_number = primary_mp.manufacturer_part_number if primary_mp is not None else ""
            self.assertEqual(
                item["manufacturer_name"] or "",
                manufacturer_name,
                assertion_message,
            )
            self.assertEqual(
                item["manufacturer_part_number"] or "",
                manufacturer_part_number,
                assertion_message,
            )
            if bom_list[idx].indent_level > 0:
                self.assertEqual(
                    float(item["quantity"]),
                    bom_list[idx].subpart.count,
                    assertion_message,
                )

        # Test OK upload with parent part number
        test_file = (
            "test_full_bom.csv" if self.organization.number_variation_len > 0 else "test_full_bom_no_variations.csv"
        )
        p4_rev = create_a_fake_part_revision(p4, create_a_fake_assembly())
        with open(f"{TEST_FILES_DIR}/{test_file}") as test_csv:
            response = self.client.post(
                reverse("bom:upload-bom"),
                {"file": test_csv, "parent_part_number": p4.full_part_number()},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)

        messages = list(response.context.get("messages"))
        for msg in messages:
            self.assertEqual(msg.tags, "info", msg.message)
            self.assertNotEqual(msg.tags, "error", msg.message)

        p4.refresh_from_db()
        p4_rev.refresh_from_db()
        self.assertEqual(len(p4_rev.indented().parts), 36)

        # Test errors get thrown
        test_file = (
            "test_full_bom_with_errors.csv"
            if self.organization.number_variation_len > 0
            else "test_full_bom_no_variations_with_errors.csv"
        )
        with open(f"{TEST_FILES_DIR}/{test_file}") as test_csv:
            response = self.client.post(
                reverse("bom:upload-bom"),
                {"file": test_csv, "parent_part_number": p3.full_part_number()},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)

        messages = list(response.context.get("messages"))

        for idx, msg in enumerate(messages):
            if self.organization.number_scheme == constants.NUMBER_SCHEME_SEMI_INTELLIGENT:
                self.assertTrue(
                    "Row 38 - part_number: Uploading of this subpart skipped. Couldn&#x27;t parse part number."
                    in str(msg.message)
                )
                self.assertTrue("Row 34 - code: " in str(msg.message))
                self.assertTrue(
                    "Row 33 - part_number: Uploading of this subpart skipped. Couldn&#x27;t parse part number."
                    in str(msg.message)
                )
                self.assertTrue(
                    "Row 35 - part_number: Uploading of this subpart skipped. Couldn&#x27;t parse part number."
                    in str(msg.message)
                )
                self.assertTrue(
                    "Row 36 - part_number: Uploading of this subpart skipped. Couldn&#x27;t parse part number."
                    in str(msg.message)
                )
                self.assertTrue(
                    "Row 37 - part_number: Uploading of this subpart skipped. Couldn&#x27;t parse part number."
                    in str(msg.message)
                )
            self.assertTrue("Row 39 - count: " in str(msg.message))
            self.assertTrue(
                "Row 40 - level: Assembly levels must decrease by no more than 1 from sequential rows."
                in str(msg.message)
            )

        # Check that 2 rows of 103-0002-00 in one assembly gets combined into one part, and added to the 2 that already exist = 2 + 1 + 1
        parent_part_number = "107-0003-22" if self.organization.number_variation_len > 0 else "107-0003"
        parent_part = Part.from_part_number(parent_part_number, organization=self.organization)
        bom = parent_part.indented()
        part_number_to_check = "103-0002-00" if self.organization.number_variation_len > 0 else "103-0002"
        self.assertEqual(list(bom.parts.values())[6].part.full_part_number(), part_number_to_check)
        self.assertEqual(list(bom.parts.values())[6].subpart.count, 4)

        # Test infinite recursion error gets thrown
        test_file = (
            "test_full_bom_with_errors_infinite_recursion.csv"
            if self.organization.number_variation_len > 0
            else "test_full_bom_no_variations_with_errors_infinite_recursion.csv"
        )
        with open(f"{TEST_FILES_DIR}/{test_file}") as test_csv:
            response = self.client.post(
                reverse("bom:upload-bom"),
                {"file": test_csv, "parent_part_number": p3.full_part_number()},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)

        messages = list(response.context.get("messages"))
        for idx, msg in enumerate(messages):
            self.assertTrue("it would cause infinite recursion. Uploading of this subpart skipped." in str(msg.message))
            self.assertTrue("Row 15" in str(msg.message))

    @parameterized.expand(
        [
            ("bom_exports/1155T158.csv", 8),
            ("bom_exports/1155F190.csv", 6),
            ("bom_exports/2183S119.csv", 10),
            ("bom_exports/CGM4554.csv", 11),
            ("bom_exports/CGM5357.csv", 8),
            ("bom_exports/CNE5393.csv", 8),
            ("bom_exports/CNE5393_fake.csv", 8),
        ]
    )
    def test_upload_bom_custom_csv(self, test_file, num_parts):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        if self.organization.number_scheme == constants.NUMBER_SCHEME_INTELLIGENT:
            # Test OK upload
            p4_rev = create_a_fake_part_revision(p4, create_a_fake_assembly())
            with open(f"{TEST_FILES_DIR}/{test_file}") as test_csv:
                response = self.client.post(
                    reverse("bom:upload-bom"),
                    {"file": test_csv, "parent_part_number": p4.full_part_number()},
                    follow=True,
                )

            with open(f"{TEST_FILES_DIR}/{test_file}") as test_csv:
                reader = csv.DictReader(test_csv)
                test_list = list(reader)

            messages = list(response.context.get("messages"))
            for msg in messages:
                self.assertEqual(msg.tags, "info")
                self.assertNotEqual(msg.tags, "error")

            parent_part = Part.from_part_number(p4.full_part_number(), organization=self.organization)
            bom = parent_part.indented()
            bom_list = list(bom.parts.values())
            # number of bom.parts = Num. of test_list + parent part
            self.assertEqual(len(bom.parts), len(test_list) + 1)

            # Check that we successfully updated an existing part
            p2.refresh_from_db()
            p2_rev = p2.latest()
            p2_mp = p2.primary_manufacturer_part
            self.assertEqual(p2_rev.revision, "1")
            self.assertEqual(p2_rev.description, "Brown dog")
            self.assertEqual(p2_mp.manufacturer.name, "Nordic Semiconductor")
            self.assertEqual(p2_mp.manufacturer_part_number, "GRM1555C1H100JA01D")

            # Check that parts get uploaded correctly
            for idx, item in enumerate(test_list):
                assertion_message = f"Index: {idx + 1}, CSV PN: {item[next(iter(item))]}, BoM PN: {bom_list[idx + 1].part.full_part_number()}"
                self.assertEqual(
                    item[next(iter(item))],
                    bom_list[idx + 1].part.full_part_number(),
                    assertion_message,
                )
                if bom_list[idx + 1].indent_level > 0:
                    self.assertEqual(
                        float(convert_arabic_to_english(item[list(item.keys())[-2]])),
                        bom_list[idx + 1].subpart.count,
                        assertion_message,
                    )

            # Test OK upload with parent part number
            p4_rev = create_a_fake_part_revision(p4, create_a_fake_assembly())
            with open(f"{TEST_FILES_DIR}/{test_file}") as test_csv:
                response = self.client.post(
                    reverse("bom:upload-bom"),
                    {"file": test_csv, "parent_part_number": p4.full_part_number()},
                    follow=True,
                )
            self.assertEqual(response.status_code, 200)

            messages = list(response.context.get("messages"))
            for msg in messages:
                self.assertEqual(msg.tags, "info", msg.message)
                self.assertNotEqual(msg.tags, "error", msg.message)

            p4.refresh_from_db()
            p4_rev.refresh_from_db()
            self.assertEqual(len(p4_rev.indented().parts), num_parts + 1)

    @parameterized.expand(
        [
            ("bom_exports/1155T158.csv", 1000, 2291816, 2360),
            ("bom_exports/1155F190.csv", 1010, 1856590, 1851),
            ("bom_exports/2183S119.csv", 1015, 732879, 736),
            ("bom_exports/3024K205.csv", 1000, 1675335, 1886),
            ("bom_exports/CGM4554.csv", 100, 345149, 3451),
            ("bom_exports/CGM5357.csv", 100, 551692, 5516),
            ("bom_exports/CNE5393.csv", 100, 147675, 1476),
            ("bom_exports/CNE5393_fake.csv", 100, 159478, 1594),
            ("bom_exports/CPM5163.csv", 100, 592968, 5929),
            ("bom_exports/1155S100.csv", 565, 944305, 1692),
        ]
    )
    def test_childs_cost_calcs(self, test_file, childs_quantity, childs_cost, bom_unit_cost):
        if self.organization.number_scheme == constants.NUMBER_SCHEME_INTELLIGENT:
            # Upload parts with prices
            with open("bom/test_files/test_new_parts_sellers_intelligent.csv") as test_csv:
                response = self.client.post(reverse("bom:upload-parts"), {"file": test_csv})
            self.assertEqual(response.status_code, 302)

            # create some materials with bom as nested boms

            # test_frit1
            frit1 = Part(number_item="2183S119", organization=self.organization)
            frit1.save()
            frit1_rev = create_a_fake_part_revision(frit1, create_a_fake_assembly(), material="with_loi")
            frit1_rev.save()
            frit1.refresh_from_db()
            frit1_rev.refresh_from_db()
            with open(f"{TEST_FILES_DIR}/bom_exports/2183S119.csv") as test_csv:
                frit1_response = self.client.post(
                    reverse("bom:upload-bom"),
                    {
                        "file": test_csv,
                        "parent_part_number": frit1.full_part_number(),
                    },
                    follow=True,
                )
            self.assertEqual(frit1_response.status_code, 200)

            # test_frit2
            frit2 = Part(number_item="1155F190", organization=self.organization)
            frit2.save()
            frit2_rev = create_a_fake_part_revision(frit2, create_a_fake_assembly(), material="with_loi")
            frit2_rev.save()
            frit2.refresh_from_db()
            frit2_rev.refresh_from_db()
            with open(f"{TEST_FILES_DIR}/bom_exports/1155F190.csv") as test_csv:
                frit2_response = self.client.post(
                    reverse("bom:upload-bom"),
                    {
                        "file": test_csv,
                        "parent_part_number": frit2.full_part_number(),
                    },
                    follow=True,
                )
            self.assertEqual(frit2_response.status_code, 200)

            # test_frit3
            frit3 = Part(number_item="1155T158", organization=self.organization)
            frit3.save()
            frit3_rev = create_a_fake_part_revision(frit3, create_a_fake_assembly(), material="with_loi")
            frit3_rev.save()
            frit3.refresh_from_db()
            frit3_rev.refresh_from_db()
            with open(f"{TEST_FILES_DIR}/bom_exports/1155T158.csv") as test_csv:
                frit3_response = self.client.post(
                    reverse("bom:upload-bom"),
                    {
                        "file": test_csv,
                        "parent_part_number": frit3.full_part_number(),
                    },
                    follow=True,
                )
            self.assertEqual(frit3_response.status_code, 200)

            # test_frit4
            frit4 = Part(number_item="3024K205", organization=self.organization)
            frit4.save()
            frit4_rev = create_a_fake_part_revision(frit4, create_a_fake_assembly(), material="with_loi")
            frit4_rev.save()
            frit4.refresh_from_db()
            frit4_rev.refresh_from_db()
            with open(f"{TEST_FILES_DIR}/bom_exports/3024K205.csv") as test_csv:
                frit4_response = self.client.post(
                    reverse("bom:upload-bom"),
                    {
                        "file": test_csv,
                        "parent_part_number": frit4.full_part_number(),
                    },
                    follow=True,
                )
            self.assertEqual(frit4_response.status_code, 200)

            (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
            csv_material_code = test_file.split("/")[1].split(".")[0]
            # TODO: don't hardcode this regex in test
            # define regex matching code "1155F190"
            with_loi_regex = r"^[0-9]{4}[A-Z]{1}[0-9]{3}$"
            # check if csv_material_code matches the regex
            if re.match(with_loi_regex, csv_material_code):
                p4_rev_material = "with_loi"
            else:
                p4_rev_material = "no_loi"
            p4_rev = create_a_fake_part_revision(p4, create_a_fake_assembly(), material=p4_rev_material)
            with open(f"{TEST_FILES_DIR}/{test_file}") as test_csv:
                response = self.client.post(
                    reverse("bom:upload-bom"),
                    {"file": test_csv, "parent_part_number": p4.full_part_number()},
                    follow=True,
                )
            self.assertEqual(response.status_code, 200)

            messages = list(response.context.get("messages"))
            for msg in messages:
                self.assertEqual(msg.tags, "info", msg.message)
                self.assertNotEqual(msg.tags, "error", msg.message)

            p4.refresh_from_db()
            p4_rev.refresh_from_db()
            # TODO: remove.
            # assemblies_list = Assembly.objects.all()
            # list all Assembly. Non-empty ones are:
            # F190
            # S119
            # T158
            # K205
            self.assertEqual(
                int(p4_rev.indented().parts[str(p4_rev.id)].childs_cost.amount),
                childs_cost,
            )
            self.assertEqual(
                p4_rev.indented().parts[str(p4_rev.id)].childs_quantity,
                childs_quantity,
            )
            self.assertEqual(
                int(p4_rev.indented().unit_cost.amount),
                bom_unit_cost,
            )

    def test_part_upload_bom_corner_cases(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        # p2's assembly already includes p1; nesting p2 under p1 would recurse.
        recursion_csv = (
            "part_number,quantity,manufacturer_part_number,dnp,reference,description\n"
            f"{p2.full_part_number()},1,abc123,,U1,cycle\n"
        )
        response = self.client.post(
            reverse("bom:part-upload-bom", kwargs={"part_id": p1.id}),
            {"file": SimpleUploadedFile("recursion.csv", recursion_csv.encode("utf-8"))},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        messages = list(response.context.get("messages"))
        for msg in messages:
            self.assertEqual(msg.tags, "error")
            self.assertTrue("recursion" in str(msg.message))

        # p4 has no PartRevision; upload should default revision rather than error.
        no_rev_csv = (
            "part_number,quantity,manufacturer_part_number,dnp,reference,description\n"
            f"{p4.full_part_number()},1,abc123,,U3,norev\n"
        )
        response = self.client.post(
            reverse("bom:part-upload-bom", kwargs={"part_id": p1.id}),
            {"file": SimpleUploadedFile("no_rev.csv", no_rev_csv.encode("utf-8"))},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        messages = list(response.context.get("messages"))
        for msg in messages:
            self.assertNotEqual(msg.tags, "error")  # Should be OK since we will default revision to 1

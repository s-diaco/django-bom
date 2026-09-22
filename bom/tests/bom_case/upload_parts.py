"""BOM tests: upload parts."""

from django.urls import reverse
from bom.helpers import (
    create_some_fake_part_classes,
)
from bom.models import Part, PartClass
from bom.tests.bom_case.base import TEST_FILES_DIR


class UploadPartsTestsMixin:
    def test_upload_parts(self):
        create_some_fake_part_classes(self.organization)

        # Should pass
        with open(f"{TEST_FILES_DIR}/test_new_parts.csv") as test_csv:
            response = self.client.post(reverse("bom:upload-parts"), {"file": test_csv}, follow=True)
        messages = list(response.context.get("messages"))
        for msg in messages:
            self.assertEqual(msg.tags, "info")
        new_part_count = Part.objects.all().count()
        self.assertEqual(new_part_count, 4)

        # Part revs should be created for each part
        for p in Part.objects.all():
            self.assertIsNotNone(p.latest())

        # Should fail because class doesn't exist
        with open(f"{TEST_FILES_DIR}/test_new_parts_2.csv") as test_csv:
            response = self.client.post(reverse("bom:upload-parts"), {"file": test_csv})
        self.assertEqual(response.status_code, 302)
        found_error = False
        for m in response.wsgi_request._messages:
            if "Part class 216 in row 2" in str(m) and "Uploading of this part skipped." in str(m):
                found_error = True
        self.assertTrue(found_error)

        # Part should be skipped because it already exists
        with open(f"{TEST_FILES_DIR}/test_new_parts_3.csv") as test_csv:
            response = self.client.post(reverse("bom:upload-parts"), {"file": test_csv})
        self.assertEqual(response.status_code, 302)
        found_error = False
        for m in response.wsgi_request._messages:
            if (
                "Part already exists for manufacturer part 2 in row GhostBuster2000. Uploading of this part skipped."
                in str(m)
            ):
                found_error = True
        self.assertTrue(found_error)

    def test_upload_parts_break_tolerance(self):
        create_some_fake_part_classes(self.organization)

        # Should break with data error
        with open(f"{TEST_FILES_DIR}/test_new_parts_broken.csv") as test_csv:
            response = self.client.post(reverse("bom:upload-parts"), {"file": test_csv}, follow=True)
        messages = list(response.context.get("messages"))

        self.assertTrue(len(messages) > 0)
        for msg in messages:
            self.assertEqual(msg.tags, "error")

    def test_upload_part_with_sellers(self):
        create_some_fake_part_classes(self.organization)
        # Should pass
        initial_parts_count = Part.objects.all().count()
        with open("bom/test_files/test_new_parts_sellers.csv") as test_csv:
            response = self.client.post(reverse("bom:upload-parts"), {"file": test_csv})
        self.assertEqual(response.status_code, 302)

        parts_count = Part.objects.all().count()
        self.assertEqual(parts_count - initial_parts_count, 4)

    def test_upload_part_classes(self):
        # Should pass
        with open(f"{TEST_FILES_DIR}/test_part_classes.csv") as test_csv:
            response = self.client.post(
                reverse("bom:settings"),
                {"file": test_csv, "submit-part-class-upload": ""},
            )
        self.assertEqual(response.status_code, 200)

        new_part_class_count = PartClass.objects.all().count()
        self.assertEqual(new_part_class_count, 37)

        # Should not hit 500 errors on anything below
        # Submit with no file
        response = self.client.post(reverse("bom:settings"), {"submit-part-class-upload": ""})
        self.assertEqual(response.status_code, 200)

        # Submit with blank header and comments
        with open(f"{TEST_FILES_DIR}/test_part_classes_no_comment.csv") as test_csv:
            response = self.client.post(
                reverse("bom:settings"),
                {"file": test_csv, "submit-part-class-upload": ""},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            "Part class 102 Resistor on row 3 is already defined. Uploading of this part class skipped."
            in str(response.content)
        )

        # Submit with a weird csv file that sort of works
        with open(f"{TEST_FILES_DIR}/test_part_classes_blank_rows.csv") as test_csv:
            response = self.client.post(
                reverse("bom:settings"),
                {"file": test_csv, "submit-part-class-upload": ""},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            "in row 3 does not have a value. Uploading of this part class skipped." in str(response.content)
        )
        self.assertTrue(
            "in row 4 does not have a value. Uploading of this part class skipped." in str(response.content)
        )

        # Submit with a csv file exported with a byte order mask, typically from MS word I think
        with open(f"{TEST_FILES_DIR}/test_part_classes_byte_order.csv") as test_csv:
            response = self.client.post(
                reverse("bom:settings"),
                {"file": test_csv, "submit-part-class-upload": ""},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        messages = list(response.context.get("messages"))
        for msg in messages:
            self.assertTrue("None on row" not in str(msg.message))

    def test_upload_part_classes_sample(self):
        # Should pass
        with open(f"{TEST_FILES_DIR}/sample_part_classes.csv") as test_csv:
            response = self.client.post(
                reverse("bom:settings"),
                {"file": test_csv, "submit-part-class-upload": ""},
            )
        self.assertEqual(response.status_code, 200)

        new_part_class_count = PartClass.objects.all().count()
        self.assertEqual(new_part_class_count, 37)

    def test_upload_part_classes_parts_and_boms(self):
        self.organization.number_item_len = 5
        self.organization.save()

        # Upload part classes
        with open(f"{TEST_FILES_DIR}/test_part_classes_4.csv") as test_csv:
            response = self.client.post(
                reverse("bom:settings"),
                {"file": test_csv, "submit-part-class-upload": ""},
            )
        self.assertEqual(response.status_code, 200)

        new_part_class_count = PartClass.objects.all().count()
        self.assertEqual(new_part_class_count, 39)

        # Upload parts (strip -VV when org has no variations)
        response = self.client.post(
            reverse("bom:upload-parts"),
            {"file": self._csv_upload(f"{TEST_FILES_DIR}/test_new_parts_4.csv")},
            follow=True,
        )
        messages = list(response.context.get("messages"))
        for msg in messages:
            self.assertEqual(msg.tags, "info")

        self.assertEqual(response.status_code, 200)
        new_part_count = Part.objects.all().count()
        self.assertEqual(new_part_count, 88)
        for p in Part.objects.all():
            self.assertIsNotNone(p.latest())

        pcba_class = PartClass.objects.filter(code=652).first()
        variation = "0A" if self.organization.number_variation_len > 0 else None
        pcba = Part.objects.filter(
            number_class=pcba_class,
            number_item="00003",
            number_variation=variation,
        ).first()

        response = self.client.post(
            reverse("bom:part-upload-bom", kwargs={"part_id": pcba.id}),
            {"file": self._csv_upload(f"{TEST_FILES_DIR}/test_bom_652-00003-0A.csv")},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        messages = list(response.context.get("messages"))

        for msg in messages:
            self.assertNotEqual(msg.tags, "error")
            self.assertEqual(msg.tags, "info")

        subparts = pcba.latest().assembly.subparts.all().order_by("id")
        self.assertEqual(subparts[0].reference, "C1")
        self.assertEqual(subparts[1].reference, "C2, C21")
        self.assertEqual(subparts[2].reference, "C23")
        pcba = Part.objects.filter(
            number_class=pcba_class,
            number_item="00004",
            number_variation=variation,
        ).first()

        response = self.client.post(
            reverse("bom:part-upload-bom", kwargs={"part_id": pcba.id}),
            {"file": self._csv_upload(f"{TEST_FILES_DIR}/test_bom_652-00004-0A.csv")},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        messages = list(response.context.get("messages"))
        for idx, msg in enumerate(messages):
            self.assertNotEqual(msg.tags, "error")
            self.assertEqual(msg.tags, "info")

        # Check that that rows that have a part number already used but which denote a distinct designator are
        # consolidated into one subpart with one part number but multiple designators and matching quantity counts.
        subparts = pcba.latest().assembly.subparts.all().order_by("id")
        self.assertEqual(subparts[0].reference, "C1, C2")
        self.assertEqual(subparts[0].count, 2)
        self.assertEqual(subparts[1].reference, "C3, C4, C5, C6, C11")
        self.assertEqual(subparts[1].count, 5)
        self.assertEqual(subparts[2].reference, "C7, C8, C9, C10, C14, C18, C22, C33")
        self.assertEqual(subparts[2].count, 8)
        self.assertEqual(subparts[16].reference, "Y1")
        self.assertEqual(subparts[16].count, 1)

    def test_edit_user_meta(self):
        response = self.client.post(
            reverse(
                "bom:user-meta-edit",
                kwargs={"user_meta_id": self.user.bom_profile().id},
            )
        )
        self.assertEqual(response.status_code, 200)

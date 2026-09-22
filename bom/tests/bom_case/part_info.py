"""BOM tests: part info."""

from django.urls import reverse
from bom.helpers import (
    create_some_fake_parts,
)


class PartInfoTestsMixin:
    def test_part_info(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        response = self.client.post(reverse("bom:part-info", kwargs={"part_id": p1.id}))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(reverse("bom:part-info", kwargs={"part_id": p2.id}))
        self.assertEqual(response.status_code, 200)

        # test having no revisions
        response = self.client.post(reverse("bom:part-info", kwargs={"part_id": p4.id}))
        self.assertEqual(response.status_code, 200)

        # set quantity
        response = self.client.post(reverse("bom:part-info", kwargs={"part_id": p1.id}), {"quantity": 1000})
        self.assertEqual(response.status_code, 200)

        # test cache hit - TODO: probably want to make sure cache works
        response = self.client.post(reverse("bom:part-info", kwargs={"part_id": p1.id}))
        self.assertEqual(response.status_code, 200)

    def test_part_info_empty_sourcing(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        response = self.client.get(reverse("bom:part-info", kwargs={"part_id": p3.id}))
        self.assertEqual(response.status_code, 200)
        decoded_content = response.content.decode("utf-8")
        self.assertIn("هیچ تأمین کننده‌ای مشخص نشده است.", decoded_content)
        self.assertNotIn('id="seller-parts"', decoded_content)

        response = self.client.get(reverse("bom:part-info", kwargs={"part_id": p1.id}))
        self.assertEqual(response.status_code, 200)
        decoded_content = response.content.decode("utf-8")
        self.assertIn('id="seller-parts"', decoded_content)

    def test_part_info_overview_print_button(self):
        (p1, p2, _p3, _p4) = create_some_fake_parts(organization=self.organization)
        product_rev = p2.latest()
        product_rev.material = "with_loi"
        product_rev.save()

        response = self.client.get(reverse("bom:part-info", kwargs={"part_id": p2.id}))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn('id="overview-tab"', html)
        self.assertIn('id="overview-print-button"', html)
        self.assertIn("دانلود CSV درخت محصول", html)
        self.assertNotIn("مدیریت درخت محصول", html)
        self.assertIn("printing-overview", html)
        self.assertIn('id="indented-bom-overview"', html)
        # Locale-safe BoM price calc: numeric attrs + JS reads (not Money display text)
        self.assertIn("data-quantity=", html)
        self.assertIn(".attr('data-unit-cost')", html)
        self.assertIn(".attr('data-quantity')", html)

    def test_part_manage_bom(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        response = self.client.post(
            reverse(
                "bom:part-manage-bom",
                kwargs={
                    "part_id": p1.id,
                    "part_revision_id": p1.latest().id,
                },
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("bom:part-info", kwargs={"part_id": p1.id}), response.url)
        self.assertIn("tab_anchor=bom", response.url)

        response = self.client.post(
            reverse(
                "bom:part-manage-bom",
                kwargs={
                    "part_id": p2.id,
                    "part_revision_id": p1.latest().id,
                },
            )
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            reverse(
                "bom:part-manage-bom",
                kwargs={
                    "part_id": p3.id,
                    "part_revision_id": p3.latest().id,
                },
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("tab_anchor=bom", response.url)

    def test_part_export_bom(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        response = self.client.post(reverse("bom:part-export-bom", kwargs={"part_id": p1.id}))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(reverse("bom:part-export-bom-sourcing", kwargs={"part_id": p1.id}))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(reverse("bom:part-export-bom-sourcing-detailed", kwargs={"part_id": p1.id}))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse(
                "bom:part-revision-export-bom-sourcing",
                kwargs={"part_revision_id": p3.latest().id},
            )
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse(
                "bom:part-revision-export-bom-sourcing-detailed",
                kwargs={"part_revision_id": p3.latest().id},
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_part_revision_export_bom(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        response = self.client.post(
            reverse(
                "bom:part-revision-export-bom",
                kwargs={"part_revision_id": p1.latest().id},
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_part_revision_export_bom_flat(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        response = self.client.post(
            reverse(
                "bom:part-revision-export-bom-flat",
                kwargs={"part_revision_id": p1.latest().id},
            )
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse(
                "bom:part-revision-export-bom-flat-sourcing",
                kwargs={"part_revision_id": p1.latest().id},
            )
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse(
                "bom:part-revision-export-bom-flat-sourcing-detailed",
                kwargs={"part_revision_id": p1.latest().id},
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_export_parts(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        response = self.client.get(reverse("bom:home"), {"download": ""}, follow=True)
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("bom:home"), {"download": f"{p1.id}"}, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_export_part_list(self):
        create_some_fake_parts(organization=self.organization)

        response = self.client.post(reverse("bom:export-part-list"))
        self.assertEqual(response.status_code, 200)

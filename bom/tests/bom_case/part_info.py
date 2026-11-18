"""BOM tests: part info."""

from copy import deepcopy

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from django.utils import translation

from bom.helpers import (
    create_a_fake_assembly_with_subpart,
    create_a_fake_part_revision,
    create_some_fake_part_classes,
    create_some_fake_parts,
)
from bom.models import Part


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
        self.assertTrue(
            "دانلود CSV درخت محصول" in html or "Download BOM CSV" in html,
            "overview download CSV action missing",
        )
        self.assertNotIn("مدیریت درخت محصول", html)
        self.assertIn("printing-overview", html)
        self.assertIn('id="indented-bom-overview"', html)
        # Print button waits for Parastoo via bomPrint before window.print().
        self.assertIn("bomPrint", html)
        self.assertIn("Parastoo.woff2", html)
        self.assertIn("Parastoo-Bold.woff2", html)
        self.assertIn('rel="preload"', html)
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

        response = self.client.get(reverse("bom:materials"), {"download": ""}, follow=True)
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("bom:materials"), {"download": f"{p1.id}"}, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_export_part_list(self):
        create_some_fake_parts(organization=self.organization)

        response = self.client.post(reverse("bom:export-part-list"))
        self.assertEqual(response.status_code, 200)

    def _create_part_with_many_parents(self, parent_count):
        """Child part used by parent_count distinct parent revisions."""
        pc1 = create_some_fake_part_classes(self.organization)[0]
        child = Part(
            number_class=pc1,
            number_item="9001",
            organization=self.organization,
        )
        child.save()
        child_rev = create_a_fake_part_revision(child, None)

        parents = []
        for i in range(parent_count):
            parent = Part(
                number_class=pc1,
                number_item=str(9100 + i),
                organization=self.organization,
            )
            parent.save()
            assy = create_a_fake_assembly_with_subpart(child_rev, reference=f"R{i}")
            parent_rev = create_a_fake_part_revision(
                parent, assy, description=f"Parent {i}", revision="1"
            )
            parents.append(parent_rev)
        return child, parents

    def test_part_info_where_used_pagination(self):
        child, parents = self._create_part_with_many_parents(12)
        url = reverse("bom:part-info", kwargs={"part_id": child.id})

        config = deepcopy(settings.BOM_CONFIG_DEFAULT)
        config["admin_dashboard"]["page_size"] = 10

        with override_settings(BOM_CONFIG=config):
            page1 = self.client.get(url, {"tab_anchor": "used"})
            self.assertEqual(page1.status_code, 200)
            where_used = page1.context["where_used"]
            where_used_part = page1.context["where_used_part"]
            self.assertEqual(len(where_used), 10)
            self.assertEqual(where_used.paginator.count, 12)
            self.assertTrue(where_used.has_other_pages())
            self.assertEqual(len(where_used_part), 10)
            self.assertTrue(where_used_part.has_other_pages())

            html = page1.content.decode("utf-8")
            self.assertIn('id="used"', html)
            used_start = html.find('id="used"')
            used_end = html.find('id="sourcing"', used_start)
            if used_end == -1:
                used_end = html.find('id="customers"', used_start)
            if used_end == -1:
                used_end = html.find('id="overview"', used_start)
            used_html = html[used_start:used_end] if used_end != -1 else html[used_start:]
            # Paginate like materials: no max-height/overflow scroll viewport on the wrap.
            self.assertNotIn("overflow: scroll", used_html)
            self.assertNotIn("overflow-y", used_html)
            self.assertIn("bom-table-wrap--fit", used_html)
            self.assertIn("responsive-table-wrapper", used_html)
            self.assertIn("bom-pagination", html)
            self.assertIn("?page=2", html)
            self.assertIn("#used", html)
            self.assertIn("per_page=", html)
            # Columns and parent part-info links preserved.
            self.assertIn(parents[0].part.full_part_number(), html)
            self.assertIn(
                reverse(
                    "bom:part-info-history",
                    kwargs={
                        "part_id": parents[0].part.id,
                        "part_revision_id": parents[0].id,
                    },
                ),
                html,
            )

            page2 = self.client.get(url, {"page": 2, "tab_anchor": "used"})
            self.assertEqual(page2.status_code, 200)
            self.assertEqual(len(page2.context["where_used"]), 2)
            self.assertEqual(len(page2.context["where_used_part"]), 2)

            larger = self.client.get(url, {"per_page": 25, "tab_anchor": "used"})
            self.assertEqual(len(larger.context["where_used"]), 12)
            self.assertFalse(larger.context["where_used"].has_other_pages())
            self.assertNotIn("bom-pagination", larger.content.decode("utf-8"))

    def test_part_info_where_used_empty_state(self):
        pc1 = create_some_fake_part_classes(self.organization)[0]
        orphan = Part(
            number_class=pc1,
            number_item="9999",
            organization=self.organization,
        )
        orphan.save()
        create_a_fake_part_revision(orphan, None)

        response = self.client.get(
            reverse("bom:part-info", kwargs={"part_id": orphan.id}),
            {"tab_anchor": "used"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["where_used"].paginator.count, 0)
        self.assertFalse(response.context["where_used"].has_other_pages())
        html = response.content.decode("utf-8")
        self.assertNotIn("bom-pagination", html)
        # Both accordion sections start open so empty copy is visible without a click.
        used_start = html.find('id="used"')
        used_end = html.find('id="sourcing"', used_start)
        if used_end == -1:
            used_end = html.find('id="customers"', used_start)
        used_html = html[used_start:used_end] if used_end != -1 else html[used_start:]
        self.assertEqual(used_html.count('<li class="active">'), 2)
        # Client follows LANGUAGE_CODE (fa-IR); match compiled gettext, not English msgid.
        with translation.override(settings.LANGUAGE_CODE):
            empty_msg = translation.gettext("This material is not used in any product.")
            empty_msg_long = translation.gettext(
                "This material is not used in any product. To add it to a product, "
                "go to that product's bill of materials and add the subpart."
            )
        self.assertIn(empty_msg, used_html)
        self.assertIn(empty_msg_long, used_html)

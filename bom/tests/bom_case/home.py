"""BOM tests: home."""

from copy import deepcopy
from re import finditer
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from bom import constants
from bom.helpers import (
    create_a_fake_part_revision,
    create_some_fake_part_classes,
    create_some_fake_parts,
)
from bom.models import Part, Seller


class HomeTestsMixin:
    def test_home(self):
        response = self.client.post(reverse("bom:home"))
        self.assertEqual(response.status_code, 200)

        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        response = self.client.post(reverse("bom:home"))
        self.assertEqual(response.status_code, 200)

        # Make sure only one part shows up
        decoded_content = response.content.decode("utf-8")
        main_content = decoded_content[
            decoded_content.find("<main>") + len("<main>") : decoded_content.rfind("</main>")
        ]
        occurances = [m.start() for m in finditer(p1.full_part_number(), main_content)]
        self.assertEqual(len(occurances), 1)

        response = self.client.get(
            reverse("bom:home"),
            {"q": p1.primary_manufacturer_part.manufacturer_part_number},
        )
        self.assertEqual(response.status_code, 200)

        # Test search
        response = self.client.get(reverse("bom:home"), {"q": f'"{p1.full_part_number()}"'})
        self.assertEqual(len(response.context["part_revs"]), 1)

    def test_home_partial_part_search(self):
        (p1, _p2, _p3, _p4) = create_some_fake_parts(organization=self.organization)

        response = self.client.get(reverse("bom:home"), {"q": "333"})
        self.assertEqual(response.status_code, 200)
        part_numbers = [pr.part.full_part_number() for pr in response.context["part_revs"]]
        self.assertIn(p1.full_part_number(), part_numbers)

        if self.organization.number_scheme == constants.NUMBER_SCHEME_SEMI_INTELLIGENT:
            response = self.client.get(reverse("bom:home"), {"q": "200-33"})
            self.assertEqual(response.status_code, 200)
            part_numbers = [pr.part.full_part_number() for pr in response.context["part_revs"]]
            self.assertIn(p1.full_part_number(), part_numbers)

        response = self.client.get(reverse("bom:home"), {"q": f'"{p1.full_part_number()}"'})
        self.assertEqual(len(response.context["part_revs"]), 1)

    def test_home_pagination_footer_bar(self):
        pc1 = create_some_fake_part_classes(self.organization)[0]
        for i in range(15):
            part = Part(
                number_class=pc1,
                number_item=str(1000 + i),
                organization=self.organization,
            )
            part.save()
            create_a_fake_part_revision(part, None)

        config = deepcopy(settings.BOM_CONFIG_DEFAULT)
        config["admin_dashboard"]["page_size"] = 1

        with override_settings(BOM_CONFIG=config):
            response = self.client.get(reverse("bom:home"), {"page": 2})
            self.assertEqual(response.status_code, 200)
            html = response.content.decode("utf-8")
            nav_start = html.find('<nav class="bom-pagination')
            nav_end = html.find("</nav>", nav_start)
            self.assertNotEqual(nav_start, -1)
            nav = html[nav_start:nav_end]
            self.assertIn("از", nav)
            self.assertNotIn("نمایش", nav)
            self.assertNotIn("/ صفحه", nav)
            self.assertNotIn("…", nav)
            self.assertIn("?page=1", nav)
            first_btn = nav.find('aria-label="اول"')
            last_btn = nav.find('aria-label="آخر"')
            self.assertNotEqual(first_btn, -1)
            self.assertNotEqual(last_btn, -1)
            self.assertIn("last_page", nav[first_btn : first_btn + 120])
            self.assertIn("first_page", nav[last_btn : last_btn + 120])
            self.assertIn("expand_more", nav)
            self.assertIn("per_page=", nav)

    def test_home_pagination_per_page(self):
        pc1 = create_some_fake_part_classes(self.organization)[0]
        for i in range(30):
            part = Part(
                number_class=pc1,
                number_item=str(2000 + i),
                organization=self.organization,
            )
            part.save()
            create_a_fake_part_revision(part, None)

        config = deepcopy(settings.BOM_CONFIG_DEFAULT)
        config["admin_dashboard"]["page_size"] = 25

        with override_settings(BOM_CONFIG=config):
            default = self.client.get(reverse("bom:home"))
            self.assertEqual(len(default.context["part_revs"]), 25)

            larger = self.client.get(reverse("bom:home"), {"per_page": 50})
            self.assertEqual(len(larger.context["part_revs"]), 30)

            invalid = self.client.get(reverse("bom:home"), {"per_page": 999})
            self.assertEqual(len(invalid.context["part_revs"]), 25)

    def test_sellers_pagination_rtl_arrows(self):
        Seller.objects.bulk_create([Seller(name=f"Seller-{i}", organization=self.organization) for i in range(15)])

        config = deepcopy(settings.BOM_CONFIG_DEFAULT)
        config["admin_dashboard"]["page_size"] = 1

        with override_settings(BOM_CONFIG=config):
            response = self.client.get(reverse("bom:sellers"), {"page": 2})
            self.assertEqual(response.status_code, 200)
            html = response.content.decode("utf-8")
            nav_start = html.find('<nav class="bom-pagination')
            nav_end = html.find("</nav>", nav_start)
            self.assertNotEqual(nav_start, -1)
            nav = html[nav_start:nav_end]
            first_btn = nav.find('aria-label="اول"')
            right_idx = nav.find("chevron_right")
            left_idx = nav.find("chevron_left")
            last_btn = nav.find('aria-label="آخر"')
            self.assertNotEqual(first_btn, -1)
            self.assertNotEqual(right_idx, -1)
            self.assertNotEqual(left_idx, -1)
            self.assertNotEqual(last_btn, -1)
            self.assertLess(first_btn, right_idx)
            self.assertLess(right_idx, left_idx)
            self.assertLess(left_idx, last_btn)
            self.assertIn("last_page", nav[first_btn : first_btn + 120])
            self.assertIn("first_page", nav[last_btn : last_btn + 120])

    def test_home_print_all_rows(self):
        (p1, p2, p3, _p4) = create_some_fake_parts(organization=self.organization)
        raw_rev = p1.latest()
        raw_rev.material = "no_bom"
        raw_rev.save()
        product_rev = p2.latest()
        product_rev.material = "with_loi"
        product_rev.save()
        product_rev_2 = p3.latest()
        product_rev_2.material = "no_loi"
        product_rev_2.save()

        config = deepcopy(settings.BOM_CONFIG_DEFAULT)
        config["admin_dashboard"]["page_size"] = 1

        with override_settings(BOM_CONFIG=config):
            paged = self.client.get(reverse("bom:home"))
            self.assertEqual(paged.status_code, 200)
            self.assertEqual(len(paged.context["part_revs"]), 1)
            self.assertTrue(paged.context["part_revs"].has_other_pages())
            paged_html = paged.content.decode("utf-8")
            self.assertIn("print=1", paged_html)
            self.assertTrue(
                "print</i>Print" in paged_html or "print</i>چاپ" in paged_html,
                "print action label missing",
            )
            self.assertNotIn("window.print();", paged_html)
            self.assertIn("bom-pagination", paged_html)

            printed = self.client.get(reverse("bom:home"), {"print": "1"})
            self.assertEqual(printed.status_code, 200)
            self.assertGreater(len(printed.context["part_revs"]), 1)
            self.assertFalse(printed.context["part_revs"].has_other_pages())
            self.assertTrue(printed.context["print_auto"])
            printed_html = printed.content.decode("utf-8")
            self.assertIn("window.print", printed_html)
            self.assertNotIn('id="print-now-button"', printed_html)
            self.assertNotIn("jquery-3.4.1.min.js", printed_html)
            self.assertIn("print-page-body", printed_html)
            self.assertNotIn("bom-pagination", printed_html)
            self.assertIn("printer-doc", printed_html)
            self.assertIn("bom/img/lithium.png", printed_html)
            self.assertIn("printer-doc-title", printed_html)
            self.assertTrue(
                "items" in printed_html or "مورد" in printed_html,
                "print item count label missing",
            )
            self.assertIsNotNone(printed.context["print_generated_at"])
            self.assertIn(p1.full_part_number(), printed_html)
            self.assertIn(p2.full_part_number(), printed_html)
            self.assertIn(p3.full_part_number(), printed_html)
            self.assertNotIn("dropdown-content", printed_html)

            config["admin_dashboard"]["print_auto_threshold"] = 2
            large_print = self.client.get(reverse("bom:home"), {"print": "1"})
            self.assertEqual(large_print.status_code, 200)
            self.assertFalse(large_print.context["print_auto"])
            self.assertTrue(large_print.context["print_confirm_only"])
            self.assertGreater(large_print.context["print_row_count"], 2)
            large_html = large_print.content.decode("utf-8")
            self.assertIn("print_go=1", large_html)
            self.assertTrue(
                "Download as XLSX" in large_html or "دانلود با فرمت اکسل" in large_html,
                "xlsx download action missing",
            )
            self.assertNotIn(p1.full_part_number(), large_html)
            self.assertNotIn("<tbody>", large_html)

            large_go = self.client.get(reverse("bom:home"), {"print": "1", "print_go": "1"})
            self.assertEqual(large_go.status_code, 200)
            self.assertTrue(large_go.context["print_auto"])
            self.assertIn(p1.full_part_number(), large_go.content.decode("utf-8"))

            raw = self.client.get(reverse("bom:home"), {"print": "1", "print_go": "1", "product": "0"})
            self.assertEqual(raw.status_code, 200)
            raw_numbers = [pr.part.full_part_number() for pr in raw.context["part_revs"]]
            self.assertEqual(raw_numbers, [p1.full_part_number()])
            self.assertEqual(raw.context["print_row_count"], 1)

            products = self.client.get(reverse("bom:home"), {"print": "1", "print_go": "1", "product": "1"})
            self.assertEqual(products.status_code, 200)
            product_numbers = [pr.part.full_part_number() for pr in products.context["part_revs"]]
            self.assertIn(p2.full_part_number(), product_numbers)
            self.assertIn(p3.full_part_number(), product_numbers)
            self.assertNotIn(p1.full_part_number(), product_numbers)

            search = self.client.get(
                reverse("bom:home"),
                {"print": "1", "print_go": "1", "q": f'"{p1.full_part_number()}"'},
            )
            self.assertEqual(len(search.context["part_revs"]), 1)
            self.assertEqual(next(iter(search.context["part_revs"])).part.id, p1.id)

"""Materials search part-number typeahead (JSON endpoint + page wiring)."""

import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse

from bom.helpers import (
    create_some_fake_parts,
    create_user_and_organization,
    suggest_part_numbers,
)
from bom.models import Organization, Part
import bom.constants as constants


User = get_user_model()


@override_settings(BOM_CONFIG=settings.BOM_CONFIG_DEFAULT)
class MaterialsPartNumberSuggestTests(TransactionTestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.organization = create_user_and_organization()
        self.profile = self.user.bom_profile(organization=self.organization)
        self.profile.role = "A"
        self.profile.save()
        self.parts = create_some_fake_parts(organization=self.organization)
        self.url = reverse("bom:materials-part-number-suggest")

    def test_requires_login(self):
        response = self.client.get(self.url, {"q": "200"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.url)

    def test_suggests_part_numbers_only(self):
        self.client.login(username="kasper", password="ghostpassword")
        target = next(p for p in self.parts if p.full_part_number().startswith("200"))
        pn = target.full_part_number()
        response = self.client.get(self.url, {"q": pn[:3]})
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertIn("results", payload)
        self.assertIn(pn, payload["results"])
        # Part-number only: MPN / manufacturer must never appear.
        for item in payload["results"]:
            self.assertNotEqual(item, "STM32F401CEU6")
            self.assertNotIn("Acme", item)
            self.assertNotIn("┆", item)

    def test_short_query_returns_empty(self):
        self.client.login(username="kasper", password="ghostpassword")
        response = self.client.get(self.url, {"q": "20"})
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertEqual(payload["results"], [])

    def test_respects_limit(self):
        self.client.login(username="kasper", password="ghostpassword")
        # Class 200 / 500 / 50A — "00" is under min length; use a broad PN fragment.
        response = self.client.get(self.url, {"q": "000", "limit": 1})
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertLessEqual(len(payload["results"]), 1)

    def test_org_scoped(self):
        other_user = User.objects.create_user(
            "other", "other@example.com", "ghostpassword"
        )
        other_org = Organization.objects.create(
            name="Other Org",
            subscription=constants.SUBSCRIPTION_TYPE_PRO,
            number_scheme=constants.NUMBER_SCHEME_SEMI_INTELLIGENT,
            number_item_len=4,
            number_variation_len=constants.NUMBER_VARIATION_LEN_DEFAULT,
            owner=other_user,
        )
        create_some_fake_parts(organization=other_org)

        self.client.login(username="kasper", password="ghostpassword")
        own_pns = {
            p.full_part_number()
            for p in Part.objects.filter(organization=self.organization)
        }
        response = self.client.get(self.url, {"q": "200"})
        payload = json.loads(response.content.decode("utf-8"))
        self.assertTrue(payload["results"])
        for pn in payload["results"]:
            self.assertIn(pn, own_pns)

    def test_helper_excludes_synopsis_and_mpn_matches(self):
        # Ensure a synopsis/MPN-only string does not produce PN suggestions.
        self.assertEqual(suggest_part_numbers(self.organization, "STM32", limit=15), [])

    def test_materials_page_wires_remote_typeahead(self):
        self.client.login(username="kasper", password="ghostpassword")
        response = self.client.get(reverse("bom:materials"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn(self.url, html)
        self.assertIn("minLength: 3", html)
        self.assertIn("debounce: 200", html)
        # Search input uses remote source — no embedded materials catalog dict.
        search_script_start = html.index("$('input.autocomplete').autocomplete({")
        search_script = html[search_script_start : search_script_start + 500]
        self.assertIn("source:", search_script)
        self.assertNotIn("data:", search_script)
        self.assertNotIn("JSON.parse", search_script)

    def test_free_text_search_still_works(self):
        self.client.login(username="kasper", password="ghostpassword")
        target = next(p for p in self.parts if p.full_part_number().startswith("200"))
        pn = target.full_part_number()
        response = self.client.get(reverse("bom:materials"), {"q": pn})
        self.assertEqual(response.status_code, 200)
        self.assertIn(pn, response.content.decode("utf-8"))

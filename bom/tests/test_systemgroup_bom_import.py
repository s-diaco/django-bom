"""Tests for SystemGroup PAC Engineering BoM importer (fixture-driven)."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from bom.helpers import create_some_fake_parts, create_user_and_organization
from bom.models import Part
from bom.systemgroup.client import (
    SystemGroupClient,
    SystemGroupClientError,
    bom_edit_url,
    extract_bom_id_from_url,
)
from bom.systemgroup.forms import SystemGroupBomImportForm
from bom.systemgroup.importer import import_parsed_bom, parsed_bom_to_csv_bytes
from bom.systemgroup.parser import (
    SystemGroupParseError,
    parse_bom_document,
    parse_login_form,
)

FIXTURES = Path("bom/test_files/systemgroup")


@override_settings()
class SystemGroupLoginParseTests(TestCase):
    def test_parse_login_form_extracts_aspnet_fields(self):
        html = (FIXTURES / "login.aspx.html").read_text(encoding="utf-8")
        form = parse_login_form(html)
        self.assertEqual(form.username_name, "ctl00$MainContent$UserName")
        self.assertEqual(form.password_name, "ctl00$MainContent$Password")
        self.assertIn("__VIEWSTATE", form.hidden)
        self.assertIn("__EVENTVALIDATION", form.hidden)
        self.assertEqual(form.submit_name, "ctl00$MainContent$LoginButton")
        self.assertEqual(form.method, "post")

    def test_parse_login_form_missing_password_raises(self):
        with self.assertRaises(SystemGroupParseError):
            parse_login_form("<html><form><input name='u' type='text'></form></html>")


class SystemGroupBomParseTests(TestCase):
    def test_parse_html_fixture(self):
        html = (FIXTURES / "bom_edit.html").read_text(encoding="utf-8")
        bom = parse_bom_document(html, content_type="text/html")
        self.assertEqual(bom.bom_id, "39477")
        self.assertEqual(bom.parent_part_number, "500-9001-00")
        self.assertEqual(bom.parent_revision, "1")
        self.assertEqual(len(bom.lines), 3)
        self.assertEqual(bom.lines[0].part_number, "200-3333-00")
        self.assertEqual(bom.lines[0].quantity, "2")
        self.assertEqual(bom.lines[0].reference, "U1, U2")
        self.assertEqual(bom.lines[1].part_number, "500-7777-00")
        self.assertEqual(bom.lines[1].manufacturer_name, "Acme")
        self.assertEqual(bom.lines[1].manufacturer_part_number, "ACM-7777")
        self.assertEqual(bom.lines[2].dnp.lower(), "dnp")
        self.assertEqual(bom.source, "html-table")

    def test_parse_json_fixture(self):
        raw = (FIXTURES / "bom_edit.json").read_text(encoding="utf-8")
        bom = parse_bom_document(raw, content_type="application/json")
        self.assertEqual(bom.bom_id, "39477")
        self.assertEqual(bom.parent_part_number, "500-9001-00")
        self.assertEqual(len(bom.lines), 2)
        self.assertEqual(bom.lines[1].manufacturer_part_number, "ACM-7777")

    def test_parse_embedded_json_in_html(self):
        html = """
        <html><body>
        <script type="application/json" id="bom-data">
        {"bom_id":"1","parent":{"part_number":"500-9001-00","description":"P"},
         "lines":[{"part_number":"200-3333-00","quantity":1,"description":"C"}]}
        </script>
        </body></html>
        """
        bom = parse_bom_document(html)
        self.assertEqual(bom.source, "html-embedded-json")
        self.assertEqual(len(bom.lines), 1)

    def test_empty_document_raises(self):
        with self.assertRaises(SystemGroupParseError):
            parse_bom_document("   ")


class SystemGroupClientTests(TestCase):
    def test_build_login_payload(self):
        html = (FIXTURES / "login.aspx.html").read_text(encoding="utf-8")
        form = parse_login_form(html)
        client = SystemGroupClient(
            base_url="http://192.168.3.193/",
            username="alice",
            password="secret",
        )
        payload = client.build_login_payload(form)
        self.assertEqual(payload["ctl00$MainContent$UserName"], "alice")
        self.assertEqual(payload["ctl00$MainContent$Password"], "secret")
        self.assertEqual(payload["__VIEWSTATE"], "/wEPDwUKLTFixtureViewState")
        self.assertEqual(payload["ctl00$MainContent$LoginButton"], "Log in")

    def test_bom_edit_url(self):
        url = bom_edit_url("http://192.168.3.193/", 39477)
        self.assertIn("Shell.aspx", url)
        self.assertIn("Edit.aspx", url)
        # page=...Edit.aspx?id=39477 is query-encoded
        self.assertIn("id%3D39477", url)

    def test_extract_bom_id_from_url(self):
        self.assertEqual(
            extract_bom_id_from_url(
                "http://192.168.3.193/Shell.aspx?page=PAC/Engineering/BomPages/Edit.aspx?id=39477"
            ),
            "39477",
        )
        encoded = bom_edit_url("http://192.168.3.193/", 39477)
        self.assertEqual(extract_bom_id_from_url(encoded), "39477")
        self.assertEqual(
            extract_bom_id_from_url(
                "http://192.168.3.193/PAC/Engineering/BomPages/Edit.aspx?id=12"
            ),
            "12",
        )
        self.assertIsNone(extract_bom_id_from_url("http://example/no-id"))

    def test_credentials_from_env_missing(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemGroupClientError):
                SystemGroupClient()

    def test_login_and_fetch_bom_with_session_mock(self):
        login_html = (FIXTURES / "login.aspx.html").read_text(encoding="utf-8")
        bom_html = (FIXTURES / "bom_edit.html").read_text(encoding="utf-8")

        session = mock.Mock()
        login_get = mock.Mock(status_code=200, text=login_html, url="http://crm/Authentication/Login.aspx")
        login_get.raise_for_status = mock.Mock()
        login_post = mock.Mock(
            status_code=200,
            text="<html>ok</html>",
            url="http://crm/Default.aspx",
        )
        login_post.raise_for_status = mock.Mock()
        bom_get = mock.Mock(
            status_code=200,
            text=bom_html,
            url="http://crm/Shell.aspx",
            headers={"Content-Type": "text/html"},
        )
        bom_get.raise_for_status = mock.Mock()
        session.get.side_effect = [login_get, bom_get]
        session.post.return_value = login_post

        client = SystemGroupClient(
            base_url="http://crm/",
            username="u",
            password="p",
            session=session,
        )
        body, ctype = client.fetch_bom(39477)
        self.assertIn("BomLinesGrid", body)
        self.assertIn("text/html", ctype)
        self.assertEqual(session.post.call_count, 1)


class SystemGroupImportSemanticsTests(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        self.parts = create_some_fake_parts(organization=self.organization)
        # pt1 is 200-3333-00
        self.existing = self.parts[0]
        self.assertEqual(self.existing.full_part_number(), "200-3333-00")
        # Use pt2 as parent assembly to fill
        self.parent = self.parts[1]
        if self.parent.latest().assembly is None:
            from bom.helpers import create_a_fake_assembly

            rev = self.parent.latest()
            rev.assembly = create_a_fake_assembly()
            rev.save()

    def test_csv_bytes_include_parent_row(self):
        bom = parse_bom_document(
            (FIXTURES / "bom_edit.json").read_text(encoding="utf-8"),
            content_type="application/json",
        )
        raw = parsed_bom_to_csv_bytes(bom, include_parent_row=True).decode()
        self.assertIn("500-9001-00", raw)
        self.assertIn("200-3333-00", raw)
        self.assertTrue(raw.splitlines()[1].startswith("0,"))

    def test_fill_existing_and_create_new(self):
        before_count = Part.objects.filter(organization=self.organization).count()
        bom = parse_bom_document(
            (FIXTURES / "bom_edit.html").read_text(encoding="utf-8")
        )
        # Force attach under existing parent; skip CRM parent create
        result = import_parsed_bom(
            self.organization,
            bom,
            parent_part=self.parent,
        )
        self.assertTrue(result.ok, result.errors)
        self.assertTrue(result.successes)

        after_count = Part.objects.filter(organization=self.organization).count()
        # One new part (500-7777-00); 200-3333-00 already existed
        self.assertEqual(after_count, before_count + 1)
        new_part = Part.from_part_number("500-7777-00", self.organization)
        self.assertIsNotNone(new_part.latest())
        self.assertEqual(new_part.latest().description, "Brand new child from CRM")

        subparts = list(self.parent.latest().assembly.subparts.all())
        pns = {sp.part_revision.part.full_part_number() for sp in subparts}
        self.assertIn("200-3333-00", pns)
        self.assertIn("500-7777-00", pns)

        # Existing part filled: CSV importer appends qty onto matching
        # (part_revision, do_not_load) subparts. pt2 already had 200-3333-00
        # count=4 non-dnp from fixtures → 4+2=6; dnp row is new → 3.
        existing_links = [
            sp
            for sp in subparts
            if sp.part_revision.part.full_part_number() == "200-3333-00"
        ]
        self.assertEqual(len(existing_links), 2)
        by_dnp = {sp.do_not_load: sp for sp in existing_links}
        self.assertEqual(by_dnp[False].count, 6)
        self.assertEqual(by_dnp[True].count, 3)

    def test_create_parent_when_missing(self):
        bom = parse_bom_document(
            (FIXTURES / "bom_edit.json").read_text(encoding="utf-8"),
            content_type="application/json",
        )
        self.assertFalse(
            Part.objects.filter(
                organization=self.organization,
                number_item="9001",
            ).exists()
        )
        result = import_parsed_bom(self.organization, bom)
        self.assertTrue(result.ok, result.errors)
        parent = Part.from_part_number("500-9001-00", self.organization)
        self.assertIsNotNone(parent.latest())
        self.assertGreaterEqual(parent.latest().assembly.subparts.count(), 1)

    def test_dry_run_does_not_write(self):
        before = Part.objects.filter(organization=self.organization).count()
        bom = parse_bom_document(
            (FIXTURES / "bom_edit.json").read_text(encoding="utf-8"),
            content_type="application/json",
        )
        result = import_parsed_bom(
            self.organization, bom, parent_part=self.parent, dry_run=True
        )
        self.assertTrue(result.ok)
        self.assertTrue(result.dry_run)
        self.assertEqual(
            Part.objects.filter(organization=self.organization).count(), before
        )


class SystemGroupManagementCommandTests(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        create_some_fake_parts(organization=self.organization)

    def test_import_from_html_file(self):
        parts = Part.objects.filter(organization=self.organization).order_by("id")
        # Use a part that is not a line item in the fixture (avoid self-as-child).
        parent = [p for p in parts if p.full_part_number() != "200-3333-00"][0]
        if parent.latest().assembly is None:
            from bom.helpers import create_a_fake_assembly

            rev = parent.latest()
            rev.assembly = create_a_fake_assembly()
            rev.save()

        call_command(
            "import_systemgroup_bom",
            organization_id=self.organization.id,
            html_file=str(FIXTURES / "bom_edit.html"),
            parent_part=parent.full_part_number(),
        )
        parent.refresh_from_db()
        pns = {
            sp.part_revision.part.full_part_number()
            for sp in parent.latest().assembly.subparts.all()
        }
        self.assertIn("500-7777-00", pns)
        self.assertIn("200-3333-00", pns)

    def test_requires_bom_id_or_file(self):
        with self.assertRaises(CommandError):
            call_command(
                "import_systemgroup_bom",
                organization_id=self.organization.id,
            )


class SystemGroupAdminGuiTests(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        create_some_fake_parts(organization=self.organization)
        self.client = Client()
        self.client.login(username="kasper", password="ghostpassword")
        self.url = reverse("bom:import-systemgroup-bom")

    def test_admin_get_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Import SystemGroup BoM")
        self.assertContains(response, "CRM_BASE_URL")

    def test_viewer_denied(self):
        profile = self.user.bom_profile()
        profile.role = "V"
        profile.save()
        response = self.client.get(self.url, HTTP_REFERER=reverse("bom:materials"))
        self.assertIn(response.status_code, (301, 302, 303, 307, 308))
        self.assertEqual(response.url, reverse("bom:materials"))

    def test_form_extracts_id_from_crm_url(self):
        form = SystemGroupBomImportForm(
            data={
                "crm_url": "http://192.168.3.193/Shell.aspx?page=PAC/Engineering/BomPages/Edit.aspx?id=39477",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["bom_id"], "39477")

    def test_post_html_upload_imports(self):
        parent = [
            p
            for p in Part.objects.filter(organization=self.organization)
            if p.full_part_number() != "200-3333-00"
        ][0]
        if parent.latest().assembly is None:
            from bom.helpers import create_a_fake_assembly

            rev = parent.latest()
            rev.assembly = create_a_fake_assembly()
            rev.save()

        html = (FIXTURES / "bom_edit.html").read_bytes()
        response = self.client.post(
            self.url,
            {
                "parent_part_number": parent.full_part_number(),
                "source_file": SimpleUploadedFile(
                    "bom_edit.html", html, content_type="text/html"
                ),
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        parent.refresh_from_db()
        pns = {
            sp.part_revision.part.full_part_number()
            for sp in parent.latest().assembly.subparts.all()
        }
        self.assertIn("500-7777-00", pns)

    def test_upload_menu_link_present_for_admin(self):
        response = self.client.get(reverse("bom:materials"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("bom:import-systemgroup-bom"))
        self.assertContains(response, "Import SystemGroup BoM")

    def test_part_bom_tab_deep_link(self):
        # BoM tab only renders for product revisions (has_bom material type).
        part = [
            p
            for p in Part.objects.filter(organization=self.organization)
            if p.latest() is not None
        ][0]
        self.organization.ensure_default_product_types()
        product_code = next(
            pt.code for pt in self.organization.product_types.all() if pt.has_bom
        )
        rev = part.latest()
        rev.material = product_code
        rev.save()
        response = self.client.get(
            reverse("bom:part-info", kwargs={"part_id": part.id}) + "?tab_anchor=bom"
        )
        self.assertEqual(response.status_code, 200)
        expected = (
            reverse("bom:import-systemgroup-bom")
            + f"?parent_part={part.full_part_number()}"
        )
        self.assertContains(response, "Import from SystemGroup CRM")
        self.assertContains(response, expected)

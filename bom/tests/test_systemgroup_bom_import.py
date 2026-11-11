"""Tests for SystemGroup PAC Engineering BoM importer (fixture-driven)."""

from __future__ import annotations

import re
from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.translation import gettext as _

from bom.helpers import create_some_fake_parts, create_user_and_organization
from bom.models import Part
from bom.systemgroup.client import (
    SystemGroupClient,
    SystemGroupClientError,
    bom_edit_direct_url,
    bom_edit_url,
    bom_list_direct_url,
    bom_list_url,
    extract_bom_id_from_url,
)
from bom.systemgroup.access import (
    client_for_user_meta,
    crm_base_url_from_organization,
    user_can_import_systemgroup,
    user_meta_has_systemgroup_credentials,
)
from bom.systemgroup.forms import SystemGroupBomImportForm
from bom.systemgroup.importer import (
    AmbiguousBomMatch,
    ExistingBomConflict,
    NoBomMatch,
    import_parsed_bom,
    list_revisions_for_part,
    parsed_bom_to_csv_bytes,
    resolve_bom_from_list,
    run_systemgroup_import,
)
from bom.systemgroup.parser import (
    SystemGroupParseError,
    match_bom_list_entries,
    normalize_crm_decimal,
    parse_bom_document,
    parse_bom_list_document,
    parse_login_form,
    split_bom_code,
)
from bom.systemgroup.rsa_login import (
    bi_to_hex,
    build_hashed_password,
    deterministic_randbelow,
    digit_size_for_modulus,
    encrypted_string,
    unicode_correct_invalid_characters,
)

FIXTURES = Path("bom/test_files/systemgroup")


@override_settings()
class SystemGroupLoginParseTests(TestCase):
    def test_parse_login_form_extracts_aspnet_fields(self):
        html = (FIXTURES / "login.aspx.html").read_text(encoding="utf-8")
        form = parse_login_form(html)
        self.assertEqual(form.username_name, "txtUsername")
        self.assertEqual(form.password_name, "txtPassword")
        self.assertIn("__VIEWSTATE", form.hidden)
        self.assertIn("__EVENTVALIDATION", form.hidden)
        self.assertTrue(form.uses_rsa_password)
        self.assertEqual(form.rsa_exponent_hex, "010001")
        self.assertTrue(form.rsa_modulus_hex)
        self.assertEqual(form.session_id, "fixture-session-001")
        self.assertEqual(form.hashed_password_name, "hashedPassword")
        self.assertEqual(form.hid_submit_name, "btnHidSubmit")
        self.assertEqual(form.method, "post")

    def test_parse_login_form_missing_password_raises(self):
        with self.assertRaises(SystemGroupParseError):
            parse_login_form("<html><form><input name='u' type='text'></form></html>")


class SystemGroupRsaLoginTests(TestCase):
    # Fresh 1024-bit keypair for decrypt round-trips only (not the CRM key).
    _N_HEX = (
        "cc175d0a4536caa7ce8b05bb30b8b2da836d9fc82e7bfbd31daadbbbb816b40bcc8fac18"
        "4dbdd85c6ccd763a0c3df10b77a8d6fb54507d13a62b1ddc68420f8d1929551c03485646"
        "bddb24010d37eb92b8280c74eee3e1ad2b1bfb12a4df8733cc6590829619a3ae76ea76ed"
        "627084a6642d91141008b7336fbb59abcb9ccf65"
    )
    _D_HEX = (
        "8848b5ad6d08a88d23e43be0832962ed7dc40f658a7cea6d50ab4e6ded00e41bd8eebbb9"
        "c2f819e9a6121177b3c30d1a5e3e55c8a0c5daafeb4f717244009106b2a7d09fe23625af"
        "55661274814b25cc25d245fb658bf6720cbef7480b3df8b832e23f4bd594ceaee8e4a0d1"
        "84f0d4dc51a25a28a10f9229e953ea1711e34621"
    )
    _E_HEX = "010001"

    def test_unicode_correct_arabic_yeh_keh(self):
        # Arabic yeh U+064A → Farsi yeh U+06CC; Arabic kaf U+0643 → Farsi keheh U+06A9
        self.assertEqual(
            unicode_correct_invalid_characters("\u064a\u0643"),
            "\u06cc\u06a9",
        )
        self.assertEqual(unicode_correct_invalid_characters("abc"), "abc")

    def test_digit_size_1024(self):
        n = int(self._N_HEX, 16)
        self.assertEqual(n.bit_length(), 1024)
        self.assertEqual(digit_size_for_modulus(n), 128)

    def test_encrypted_string_roundtrip_pkcs1(self):
        plaintext = "fixture-session-001--s3cret"
        ct_hex = encrypted_string(
            plaintext,
            exponent_hex=self._E_HEX,
            modulus_hex=self._N_HEX,
            randbelow=deterministic_randbelow(42),
        )
        self.assertTrue(re.fullmatch(r"[0-9a-f]+( [0-9a-f]+)*", ct_hex))
        c_int = int(ct_hex.split()[0], 16)
        n = int(self._N_HEX, 16)
        d = int(self._D_HEX, 16)
        m_int = pow(c_int, d, n)
        k = digit_size_for_modulus(n)
        em = m_int.to_bytes(k, "big")
        self.assertEqual(em[0], 0x00)
        self.assertEqual(em[1], 0x02)
        sep = em.index(0x00, 2)
        recovered = em[sep + 1 :]
        self.assertEqual(recovered.decode("utf-8"), plaintext)

    def test_build_hashed_password_uses_session_separator(self):
        ct = build_hashed_password(
            "pw",
            session_id="SID",
            exponent_hex=self._E_HEX,
            modulus_hex=self._N_HEX,
            randbelow=deterministic_randbelow(7),
        )
        c_int = int(ct.split()[0], 16)
        n = int(self._N_HEX, 16)
        d = int(self._D_HEX, 16)
        em = pow(c_int, d, n).to_bytes(digit_size_for_modulus(n), "big")
        sep = em.index(0x00, 2)
        self.assertEqual(em[sep + 1 :].decode("utf-8"), "SID--pw")

    def test_bi_to_hex_groups(self):
        self.assertEqual(bi_to_hex(0), "0000")
        self.assertEqual(bi_to_hex(0x2), "0002")
        self.assertEqual(bi_to_hex(0xABCD), "abcd")


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

    def test_parse_telerik_edit_html_eds_materials(self):
        """Live Edit.aspx: lines from eds_BomMaterials_updatedData, not rgRow."""
        html = (FIXTURES / "bom_edit_telerik.html").read_text(encoding="utf-8")
        bom = parse_bom_document(html, content_type="text/html")
        self.assertEqual(bom.source, "html-eds-materials")
        self.assertEqual(bom.bom_id, "39485")
        self.assertEqual(bom.parent_part_number, "1155F229")
        self.assertEqual(bom.parent_revision, "A2*10-C")
        self.assertIn("1155F229", bom.parent_description)
        self.assertEqual(len(bom.lines), 3)
        self.assertEqual(bom.lines[0].part_number, "003-00")
        self.assertEqual(bom.lines[0].quantity, "70")
        self.assertIn("براکس", bom.lines[0].description)
        self.assertEqual(bom.lines[1].part_number, "008-11")
        self.assertEqual(bom.lines[1].quantity, "10")

    def test_parse_materials_json_fixture(self):
        raw = (FIXTURES / "bom_edit_materials.json").read_text(encoding="utf-8")
        bom = parse_bom_document(raw, content_type="application/json")
        self.assertEqual(bom.bom_id, "39485")
        self.assertEqual(len(bom.lines), 3)
        self.assertEqual(bom.lines[0].part_number, "003-00")
        self.assertEqual(bom.lines[0].quantity, "70")

    def test_normalize_crm_decimal(self):
        self.assertEqual(normalize_crm_decimal("70/000000000000000"), "70")
        self.assertEqual(normalize_crm_decimal("10/500"), "10.5")
        self.assertEqual(normalize_crm_decimal("‎12‏"), "12")

    def test_empty_document_raises(self):
        with self.assertRaises(SystemGroupParseError):
            parse_bom_document("   ")


class SystemGroupBomListParseTests(TestCase):
    def test_split_bom_code(self):
        self.assertEqual(split_bom_code("500-9001-00/1"), ("500-9001-00", "1"))
        self.assertEqual(split_bom_code("500-9001-00/A"), ("500-9001-00", "A"))
        self.assertEqual(split_bom_code("1155F229/A2*10-C"), ("1155F229", "A2*10-C"))
        self.assertEqual(split_bom_code("CGM5883"), ("CGM5883", ""))
        self.assertEqual(split_bom_code("2183S914*2-C"), ("2183S914*2-C", ""))
        self.assertEqual(split_bom_code("500-9001-00"), ("500-9001-00", ""))
        self.assertEqual(split_bom_code(""), ("", ""))

    def test_parse_list_html_fixture(self):
        html = (FIXTURES / "bom_list.html").read_text(encoding="utf-8")
        entries = parse_bom_list_document(html, content_type="text/html")
        self.assertEqual(len(entries), 4)
        self.assertEqual(entries[0].bom_id, "39477")
        self.assertEqual(entries[0].part_number, "500-9001-00")
        self.assertEqual(entries[0].revision, "1")
        self.assertIn("Edit.aspx?id=39477", entries[0].edit_url)
        self.assertEqual(entries[1].bom_id, "40001")
        self.assertEqual(entries[1].revision, "A")
        self.assertEqual(entries[2].part_number, "500-1111-00")

    def test_parse_telerik_list_html_fixture(self):
        """Live-trimmed List.aspx: static header + rgRow, bidi/comma ids."""
        html = (FIXTURES / "bom_list_telerik.html").read_text(encoding="utf-8")
        entries = parse_bom_list_document(html, content_type="text/html")
        self.assertEqual(len(entries), 4)
        self.assertEqual(entries[0].bom_id, "39485")
        self.assertEqual(entries[0].part_number, "1155F229")
        self.assertEqual(entries[0].revision, "A2*10-C")
        self.assertIn("1155F229", entries[0].description)
        # Number without slash → whole value is PN, empty revision
        self.assertEqual(entries[1].bom_id, "39484")
        self.assertEqual(entries[1].part_number, "CGM5883")
        self.assertEqual(entries[1].revision, "")
        self.assertEqual(entries[3].part_number, "2183S914*2-C")

    def test_parse_telerik_list_json_fixture(self):
        raw = (FIXTURES / "bom_list_telerik.json").read_text(encoding="utf-8")
        entries = parse_bom_list_document(raw, content_type="application/json")
        self.assertEqual(len(entries), 4)
        self.assertEqual(entries[0].bom_id, "39485")
        self.assertEqual(entries[0].part_number, "1155F229")
        self.assertEqual(entries[0].revision, "A2*10-C")
        self.assertEqual(entries[1].part_number, "CGM5883")

    def test_match_telerik_number_slash_and_bare(self):
        entries = parse_bom_list_document(
            (FIXTURES / "bom_list_telerik.json").read_text(encoding="utf-8"),
            content_type="application/json",
        )
        hits = match_bom_list_entries(entries, part_number="1155F229")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].bom_id, "39485")
        hits_full = match_bom_list_entries(
            entries, part_number="1155F229/A2*10-C"
        )
        self.assertEqual([h.bom_id for h in hits_full], ["39485"])
        hits_bare = match_bom_list_entries(entries, part_number="CGM5883")
        self.assertEqual([h.bom_id for h in hits_bare], ["39484"])

    def test_parse_list_json_fixture(self):
        raw = (FIXTURES / "bom_list.json").read_text(encoding="utf-8")
        entries = parse_bom_list_document(raw, content_type="application/json")
        self.assertEqual(len(entries), 4)
        self.assertEqual(entries[0].part_number, "500-9001-00")
        self.assertEqual(entries[0].revision, "1")
        self.assertEqual(entries[3].bom_id, "42000")
        self.assertEqual(entries[3].revision, "2")
        self.assertEqual(entries[3].description, "Unique description match target")

    def test_match_by_part_number_unique(self):
        entries = parse_bom_list_document(
            (FIXTURES / "bom_list.json").read_text(encoding="utf-8"),
            content_type="application/json",
        )
        hits = match_bom_list_entries(entries, part_number="500-1111-00")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].bom_id, "41000")

    def test_match_by_part_number_ambiguous(self):
        entries = parse_bom_list_document(
            (FIXTURES / "bom_list.html").read_text(encoding="utf-8")
        )
        hits = match_bom_list_entries(entries, part_number="500-9001-00")
        self.assertEqual(len(hits), 2)
        self.assertEqual({h.bom_id for h in hits}, {"39477", "40001"})

    def test_match_narrows_ambiguous_pn_with_revision(self):
        entries = parse_bom_list_document(
            (FIXTURES / "bom_list.html").read_text(encoding="utf-8")
        )
        hits = match_bom_list_entries(
            entries, part_number="500-9001-00", revision="1"
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].bom_id, "39477")
        hits_a = match_bom_list_entries(
            entries, part_number="500-9001-00", revision="A"
        )
        self.assertEqual(len(hits_a), 1)
        self.assertEqual(hits_a[0].bom_id, "40001")

    def test_match_by_description_fallback(self):
        entries = parse_bom_list_document(
            (FIXTURES / "bom_list.json").read_text(encoding="utf-8"),
            content_type="application/json",
        )
        hits = match_bom_list_entries(
            entries, description="Unique description match target"
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].bom_id, "42000")

    def test_match_narrows_ambiguous_pn_with_description(self):
        entries = parse_bom_list_document(
            (FIXTURES / "bom_list.html").read_text(encoding="utf-8")
        )
        hits = match_bom_list_entries(
            entries,
            part_number="500-9001-00",
            description="Fixture assembly from SystemGroup",
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].bom_id, "39477")

    def test_resolve_no_match(self):
        with self.assertRaises(NoBomMatch):
            resolve_bom_from_list(
                part_number="999-0000-00",
                list_path=FIXTURES / "bom_list.json",
            )

    def test_resolve_ambiguous(self):
        with self.assertRaises(AmbiguousBomMatch) as ctx:
            resolve_bom_from_list(
                part_number="500-9001-00",
                list_path=FIXTURES / "bom_list.html",
            )
        self.assertEqual(len(ctx.exception.matches), 2)


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
        self.assertEqual(payload["txtUsername"], "alice")
        self.assertEqual(payload["txtPassword"], "")  # cleared; RSA hashedPassword used
        self.assertEqual(payload["__VIEWSTATE"], "/wEPDwUKLTFixtureViewState")
        self.assertIn("btnHidSubmit", payload)
        self.assertNotIn("btnSubmit", payload)
        self.assertTrue(payload["hashedPassword"])
        self.assertRegex(payload["hashedPassword"], r"^[0-9a-f]+( [0-9a-f]+)*$")
        # Decrypt with CRM public encrypt is one-way here; ensure plaintext shape via
        # our test key in SystemGroupRsaLoginTests. Spot-check session separator length.
        self.assertGreater(len(payload["hashedPassword"]), 64)

    def test_bom_edit_url(self):
        url = bom_edit_url("http://192.168.3.193/", 39477)
        self.assertIn("Shell.aspx", url)
        self.assertIn("Edit.aspx", url)
        # page=...Edit.aspx?id=39477 is query-encoded
        self.assertIn("id%3D39477", url)

    def test_bom_edit_direct_url(self):
        url = bom_edit_direct_url("http://192.168.3.193/", 39477)
        self.assertIn("Edit.aspx", url)
        self.assertIn("id=39477", url)
        self.assertNotIn("Shell.aspx", url)

    def test_bom_list_url(self):
        url = bom_list_url("http://192.168.3.193/")
        self.assertIn("Shell.aspx", url)
        self.assertIn("List.aspx", url)
        self.assertIn("EntityName%3DBom", url)
        self.assertIn("SystemGroup.PAC.Engineering", url)

    def test_bom_list_direct_url(self):
        url = bom_list_direct_url("http://192.168.3.193/")
        self.assertIn("List.aspx", url)
        self.assertIn("EntityName=Bom", url)
        self.assertNotIn("Shell.aspx", url)

    def test_fetch_bom_skips_shell_chrome(self):
        """Shell HTML has no tables; client must prefer direct Edit.aspx."""
        login_html = (FIXTURES / "login.aspx.html").read_text(encoding="utf-8")
        shell_html = (
            "<!DOCTYPE html><html><head>"
            "<script>var _$isThisShellPage = true;</script>"
            "<title>Shell</title></head><body>chrome</body></html>"
        )
        edit_html = (FIXTURES / "bom_edit.html").read_text(encoding="utf-8")

        session = mock.Mock()
        login_get = mock.Mock(
            status_code=200, text=login_html, url="http://crm/Authentication/Login.aspx"
        )
        login_get.raise_for_status = mock.Mock()
        login_post = mock.Mock(
            status_code=200, text="<html>ok</html>", url="http://crm/Default.aspx"
        )
        login_post.raise_for_status = mock.Mock()

        def _resp(url: str, text: str) -> mock.Mock:
            r = mock.Mock(
                status_code=200,
                text=text,
                url=url,
                headers={"Content-Type": "text/html"},
            )
            r.raise_for_status = mock.Mock()
            return r

        def get_side_effect(url, *args, **kwargs):
            if "Login.aspx" in url:
                return login_get
            if "Shell.aspx" in url:
                return _resp(url, shell_html)
            if "Edit.aspx" in url:
                return _resp(url, edit_html)
            raise AssertionError(f"unexpected GET {url}")

        session.get.side_effect = get_side_effect
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
        self.assertNotIn("_$isThisShellPage", body)
        # Prefer-predicate: if Shell is requested first, skip it for Edit.
        body2, _ = client._fetch_first_ok(
            [
                bom_edit_url("http://crm/", 39477),
                bom_edit_direct_url("http://crm/", 39477),
            ],
            "BoM Edit page",
            prefer_predicate=lambda b, _c: "_$isthisshellpage" not in b.lower()
            and "<table" in b.lower(),
        )
        self.assertIn("BomLinesGrid", body2)

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
        # Parent already has a BoM tree from fixtures — append (keep).
        result = import_parsed_bom(
            self.organization,
            bom,
            parent_part=self.parent,
            existing_bom_action="keep",
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
            self.organization,
            bom,
            parent_part=self.parent,
            existing_bom_action="keep",
            dry_run=True,
        )
        self.assertTrue(result.ok)
        self.assertTrue(result.dry_run)
        self.assertEqual(
            Part.objects.filter(organization=self.organization).count(), before
        )

    def test_existing_bom_raises_without_action(self):
        bom = parse_bom_document(
            (FIXTURES / "bom_edit.html").read_text(encoding="utf-8")
        )
        with self.assertRaises(ExistingBomConflict):
            import_parsed_bom(
                self.organization,
                bom,
                parent_part=self.parent,
            )


class SystemGroupManagementCommandTests(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        create_some_fake_parts(organization=self.organization)

    def test_import_from_html_file(self):
        from bom.helpers import create_a_fake_assembly

        parts = Part.objects.filter(organization=self.organization).order_by("id")
        # Use a part that is not a line item in the fixture (avoid self-as-child).
        parent = [
            p
            for p in parts
            if p.full_part_number() != "200-3333-00" and p.latest() is not None
        ][0]
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


class SystemGroupListResolveImportTests(TestCase):
    def setUp(self):
        from bom.helpers import create_a_fake_assembly

        self.user, self.organization = create_user_and_organization()
        self.parts = create_some_fake_parts(organization=self.organization)
        self.parent = self.parts[1]
        # Start from an empty BoM so imports do not need keep/replace.
        rev = self.parent.latest()
        rev.assembly = create_a_fake_assembly()
        rev.save()

    def test_list_revisions_for_part_returns_all_revs(self):
        rows = list_revisions_for_part(
            "500-9001-00",
            list_path=FIXTURES / "bom_list.json",
        )
        self.assertEqual({r.bom_id for r in rows}, {"39477", "40001"})
        self.assertEqual({r.revision for r in rows}, {"1", "A"})

    def test_list_revisions_strips_accidental_rev_suffix(self):
        rows = list_revisions_for_part(
            "500-9001-00/1",
            list_path=FIXTURES / "bom_list.json",
        )
        self.assertEqual(len(rows), 2)

    def test_run_import_resolves_unique_pn_from_list_file(self):
        # Parent PN won't match list; resolve unique list PN via description-less
        # path by calling resolve then import with bom_id — exercise full helper:
        entry = resolve_bom_from_list(
            part_number="500-1111-00",
            list_path=FIXTURES / "bom_list.json",
        )
        self.assertEqual(entry.bom_id, "41000")
        result = run_systemgroup_import(
            self.organization,
            bom_id=entry.bom_id,
            parent_part_number=self.parent.full_part_number(),
            html_path=FIXTURES / "bom_edit.html",
        )
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.resolved_bom_id, "41000")

    def test_run_import_list_file_and_html_with_unique_parent_pn(self):
        # Create a Lithium part whose full PN matches unique list entry.
        # Fake parts use 200-3333-00 / 500-.... Check numbering scheme.
        pn = self.parent.full_part_number()
        list_json = {
            "rows": [
                {
                    "id": "39477",
                    "part_number": pn,
                    "description": "Matched parent",
                    "revision": "1",
                    "edit_url": f"Shell.aspx?page=PAC/Engineering/BomPages/Edit.aspx?id=39477",
                }
            ]
        }
        import json

        result = run_systemgroup_import(
            self.organization,
            parent_part_number=pn,
            from_list=True,
            list_json=json.dumps(list_json),
            html_path=FIXTURES / "bom_edit.html",
            dry_run=True,
        )
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.resolved_bom_id, "39477")
        self.assertTrue(
            any("Resolved CRM BoM" in s for s in result.successes),
            result.successes,
        )

    def test_run_import_ambiguous_raises(self):
        import json

        pn = self.parent.full_part_number()
        list_json = json.dumps(
            {
                "rows": [
                    {
                        "id": "39477",
                        "part_number": pn,
                        "description": "A",
                        "edit_url": "Edit.aspx?id=39477",
                    },
                    {
                        "id": "40001",
                        "part_number": pn,
                        "description": "B",
                        "edit_url": "Edit.aspx?id=40001",
                    },
                ]
            }
        )
        with self.assertRaises(AmbiguousBomMatch) as ctx:
            run_systemgroup_import(
                self.organization,
                parent_part_number=pn,
                from_list=True,
                list_json=list_json,
                html_path=FIXTURES / "bom_edit.html",
            )
        self.assertEqual(len(ctx.exception.matches), 2)

    def test_cli_from_list_browse_prints_rows(self):
        from io import StringIO

        out = StringIO()
        call_command(
            "import_systemgroup_bom",
            organization_id=self.organization.id,
            from_list=True,
            list_file=str(FIXTURES / "bom_list.json"),
            stdout=out,
        )
        text = out.getvalue()
        self.assertIn("39477", text)
        self.assertIn("500-9001-00", text)

    def test_cli_ambiguous_exits(self):
        import json
        import tempfile
        from io import StringIO

        pn = self.parent.full_part_number()
        payload = json.dumps(
            {
                "rows": [
                    {
                        "id": "1",
                        "part_number": pn,
                        "description": "A",
                        "edit_url": "Edit.aspx?id=1",
                    },
                    {
                        "id": "2",
                        "part_number": pn,
                        "description": "B",
                        "edit_url": "Edit.aspx?id=2",
                    },
                ]
            }
        )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(payload)
            list_path = tmp.name
        err = StringIO()
        with self.assertRaises(CommandError):
            call_command(
                "import_systemgroup_bom",
                organization_id=self.organization.id,
                parent_part=pn,
                from_list=True,
                list_file=list_path,
                html_file=str(FIXTURES / "bom_edit.html"),
                stderr=err,
            )

    def test_fetch_bom_list_with_session_mock(self):
        login_html = (FIXTURES / "login.aspx.html").read_text(encoding="utf-8")
        bom_html = (FIXTURES / "bom_edit.html").read_text(encoding="utf-8")

        session = mock.Mock()
        login_get = mock.Mock(
            status_code=200, text=login_html, url="http://crm/Authentication/Login.aspx"
        )
        login_get.raise_for_status = mock.Mock()
        login_post = mock.Mock(
            status_code=200, text="<html>ok</html>", url="http://crm/Default.aspx"
        )
        login_post.raise_for_status = mock.Mock()
        bom_get = mock.Mock(
            status_code=200,
            text=bom_html,
            url="http://crm/Shell.aspx",
            headers={"Content-Type": "text/html"},
        )
        bom_get.raise_for_status = mock.Mock()
        # list_json resolves offline — only login GET + Edit GET hit the network.
        session.get.side_effect = [login_get, bom_get]
        session.post.return_value = login_post

        client = SystemGroupClient(
            base_url="http://crm/",
            username="u",
            password="p",
            session=session,
        )
        import json

        rev = self.parent.latest().revision if self.parent.latest() else "1"
        list_payload = json.dumps(
            {
                "rows": [
                    {
                        "id": "39477",
                        "bom_code": f"{self.parent.full_part_number()}/{rev}",
                        "description": "x",
                        "edit_url": "Edit.aspx?id=39477",
                    },
                    {
                        "id": "39999",
                        "bom_code": f"{self.parent.full_part_number()}/OTHER",
                        "description": "wrong rev",
                        "edit_url": "Edit.aspx?id=39999",
                    },
                ]
            }
        )
        result = run_systemgroup_import(
            self.organization,
            parent_part_number=self.parent.full_part_number(),
            parent_revision=str(rev),
            client=client,
            list_json=list_payload,
            dry_run=True,
        )
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.resolved_bom_id, "39477")
        self.assertEqual(session.get.call_count, 2)


class SystemGroupAccessTests(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        self.profile = self.user.bom_profile()

    def test_requires_org_flag_url_and_credentials(self):
        self.assertFalse(user_can_import_systemgroup(self.user))
        self.organization.systemgroup_import_enabled = True
        self.organization.save(update_fields=["systemgroup_import_enabled"])
        self.assertFalse(user_can_import_systemgroup(self.user))
        self.profile.systemgroup_username = "u"
        self.profile.systemgroup_password = "p"
        self.profile.save(
            update_fields=["systemgroup_username", "systemgroup_password"]
        )
        self.assertTrue(user_meta_has_systemgroup_credentials(self.profile))
        self.assertFalse(user_can_import_systemgroup(self.user))
        self.organization.systemgroup_crm_base_url = "http://crm.example/"
        self.organization.save(update_fields=["systemgroup_crm_base_url"])
        self.assertTrue(user_can_import_systemgroup(self.user))
        self.assertTrue(self.profile.can_import_systemgroup())

    def test_client_uses_organization_crm_base_url(self):
        self.organization.systemgroup_crm_base_url = "http://crm.example"
        self.organization.save(update_fields=["systemgroup_crm_base_url"])
        self.profile.systemgroup_username = "u"
        self.profile.systemgroup_password = "p"
        self.profile.save(
            update_fields=["systemgroup_username", "systemgroup_password"]
        )
        self.assertEqual(
            crm_base_url_from_organization(self.organization),
            "http://crm.example/",
        )
        client = client_for_user_meta(self.profile)
        self.assertEqual(client.base_url, "http://crm.example/")
        self.assertEqual(client.username, "u")

    def test_client_missing_org_url_raises(self):
        self.profile.systemgroup_username = "u"
        self.profile.systemgroup_password = "p"
        self.profile.save(
            update_fields=["systemgroup_username", "systemgroup_password"]
        )
        with self.assertRaises(SystemGroupClientError) as ctx:
            client_for_user_meta(self.profile)
        self.assertIn("Settings → Organization", str(ctx.exception))


class SystemGroupAdminGuiTests(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        create_some_fake_parts(organization=self.organization)
        self.organization.systemgroup_import_enabled = True
        self.organization.systemgroup_crm_base_url = "http://192.168.3.193/"
        self.organization.save(
            update_fields=[
                "systemgroup_import_enabled",
                "systemgroup_crm_base_url",
            ]
        )
        profile = self.user.bom_profile()
        profile.systemgroup_username = "crm-user"
        profile.systemgroup_password = "crm-pass"
        profile.save(
            update_fields=["systemgroup_username", "systemgroup_password"]
        )
        self.client = Client()
        self.client.login(username="kasper", password="ghostpassword")
        self.url = reverse("bom:import-systemgroup-bom")

    def test_admin_get_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Import SystemGroup BoM")
        self.assertContains(response, "Part ID")
        self.assertContains(response, "Load revisions")
        self.assertContains(response, "Part ID + Revision")
        self.assertContains(response, "Get the BoM")
        self.assertContains(response, "Settings → Organization")

    def test_load_revisions_shows_pick_list(self):
        matches = parse_bom_list_document(
            (FIXTURES / "bom_list.json").read_text(encoding="utf-8"),
            content_type="application/json",
        )
        pn_matches = [m for m in matches if m.part_number == "500-9001-00"]
        self.assertGreaterEqual(len(pn_matches), 2)
        with mock.patch(
            "bom.systemgroup.importer.list_revisions_for_part",
            return_value=pn_matches,
        ), mock.patch(
            "bom.systemgroup.access.client_for_user_meta",
            return_value=mock.Mock(),
        ):
            response = self.client.post(
                self.url,
                {"part_id": "500-9001-00", "load_revisions": "1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CRM revisions for")
        self.assertContains(response, "Import this BoM")
        self.assertContains(response, "39477")
        self.assertContains(response, "40001")

    def test_load_revisions_unreachable_crm_shows_error_not_500(self):
        with mock.patch(
            "bom.systemgroup.access.client_for_user_meta",
            side_effect=SystemGroupClientError(
                "Failed to fetch login page: Connection refused"
            ),
        ):
            response = self.client.post(
                self.url,
                {"part_id": "1155F229", "load_revisions": "1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Failed to fetch login page")
        self.assertNotContains(response, "Import this BoM")

    def test_load_revisions_missing_base_url_shows_error_not_500(self):
        with mock.patch(
            "bom.systemgroup.access.client_for_user_meta",
            side_effect=SystemGroupClientError(
                "Missing SystemGroup CRM base URL. Set it under "
                "Settings → Organization."
            ),
        ):
            response = self.client.post(
                self.url,
                {"part_id": "1155F229", "load_revisions": "1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Missing SystemGroup CRM base URL")

    def test_get_the_bom_unreachable_crm_shows_error_not_500(self):
        with mock.patch(
            "bom.systemgroup.access.client_for_user_meta",
            side_effect=SystemGroupClientError(
                "Could not reach the SystemGroup CRM login page: Connection refused"
            ),
        ):
            response = self.client.post(
                self.url,
                {"part_id_revision": "1155F229/A2"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Could not reach the SystemGroup CRM")

    def test_import_selected_revision_posts_bom_id_and_rev(self):
        html = (FIXTURES / "bom_edit.html").read_bytes()
        # Same payload shape as the revision-picker "Import this BoM" button.
        response = self.client.post(
            self.url,
            {
                "part_id": "500-1111-00",
                "parent_part_number": "500-1111-00",
                "parent_revision": "A1",
                "bom_id": "41000",
                "source_file": SimpleUploadedFile(
                    "bom_edit.html", html, content_type="text/html"
                ),
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        created = Part.from_part_number("500-1111-00", self.organization)
        self.assertEqual(created.latest().revision, "A1")
        pns = {
            sp.part_revision.part.full_part_number()
            for sp in created.latest().assembly.subparts.all()
        }
        self.assertIn("500-7777-00", pns)

    def test_import_disabled_without_user_credentials(self):
        profile = self.user.bom_profile()
        profile.systemgroup_username = ""
        profile.systemgroup_password = ""
        profile.save(
            update_fields=["systemgroup_username", "systemgroup_password"]
        )
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (301, 302, 303, 307, 308))
        self.assertEqual(
            response.url, reverse("bom:settings", kwargs={"tab_anchor": "user"})
        )

    def test_import_disabled_when_org_flag_off(self):
        self.organization.systemgroup_import_enabled = False
        self.organization.save(update_fields=["systemgroup_import_enabled"])
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (301, 302, 303, 307, 308))
        self.assertEqual(
            response.url,
            reverse("bom:settings", kwargs={"tab_anchor": "organization"}),
        )

    def test_import_disabled_without_org_crm_base_url(self):
        self.organization.systemgroup_crm_base_url = ""
        self.organization.save(update_fields=["systemgroup_crm_base_url"])
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (301, 302, 303, 307, 308))
        self.assertEqual(
            response.url,
            reverse("bom:settings", kwargs={"tab_anchor": "organization"}),
        )

    def test_home_hides_import_without_credentials(self):
        profile = self.user.bom_profile()
        profile.systemgroup_password = ""
        profile.save(update_fields=["systemgroup_password"])
        response = self.client.get(reverse("bom:home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Import material")

    def test_settings_saves_systemgroup_credentials(self):
        response = self.client.post(
            reverse("bom:settings", kwargs={"tab_anchor": "user"}),
            {
                "submit-edit-user": "1",
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "email": self.user.email,
                "calendar": "J",
                "language": "en",
                "systemgroup_username": "new-crm",
                "systemgroup_password": "new-secret",
            },
        )
        self.assertIn(response.status_code, (200, 302))
        profile = self.user.bom_profile()
        profile.refresh_from_db()
        self.assertEqual(profile.systemgroup_username, "new-crm")
        self.assertEqual(profile.systemgroup_password, "new-secret")

    def test_settings_saves_organization_crm_base_url(self):
        response = self.client.post(
            reverse("bom:settings", kwargs={"tab_anchor": "organization"}),
            {
                "submit-edit-organization": "1",
                "name": self.organization.name,
                "currency": self.organization.currency.code
                if hasattr(self.organization.currency, "code")
                else self.organization.currency,
                "owner": self.user.id,
                "systemgroup_import_enabled": "on",
                "systemgroup_crm_base_url": "http://10.0.0.5",
            },
        )
        self.assertIn(response.status_code, (200, 302))
        self.organization.refresh_from_db()
        self.assertTrue(self.organization.systemgroup_import_enabled)
        self.assertEqual(
            self.organization.systemgroup_crm_base_url, "http://10.0.0.5"
        )

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

    def test_form_allows_parent_part_without_bom_id(self):
        form = SystemGroupBomImportForm(data={"parent_part_number": "500-9001-00"})
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_part_id_revision_splits_pn_rev(self):
        form = SystemGroupBomImportForm(data={"part_id_revision": "1155F229/A2*10-C"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["parent_part_number"], "1155F229")
        self.assertEqual(form.cleaned_data["parent_revision"], "A2*10-C")

    def test_form_part_id_with_load_revisions(self):
        form = SystemGroupBomImportForm(
            data={"part_id": "1155F229", "load_revisions": "1"}
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["part_id"], "1155F229")
        self.assertEqual(form.cleaned_data["parent_part_number"], "1155F229")
        self.assertTrue(form.cleaned_data["load_revisions"])

    def test_form_allows_browse_list_alone(self):
        form = SystemGroupBomImportForm(data={"browse_list": True})
        self.assertTrue(form.is_valid(), form.errors)

    def test_post_ambiguous_list_shows_pick_list(self):
        list_json = (FIXTURES / "bom_list.json").read_text(encoding="utf-8")
        parent = Part.objects.filter(organization=self.organization).first()
        matches = parse_bom_list_document(list_json, content_type="application/json")[:2]
        with mock.patch(
            "bom.systemgroup.importer.run_systemgroup_import",
            side_effect=AmbiguousBomMatch(matches, "500-9001-00"),
        ) as mocked:
            response = self.client.post(
                self.url,
                {"parent_part_number": parent.full_part_number()},
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pick one")
        self.assertContains(response, "39477")
        self.assertContains(response, "40001")
        mocked.assert_called()

    def test_post_html_upload_imports(self):
        from bom.helpers import create_a_fake_assembly

        parent = [
            p
            for p in Part.objects.filter(organization=self.organization)
            if p.full_part_number() != "200-3333-00" and p.latest() is not None
        ][0]
        rev = parent.latest()
        # Empty BoM so import does not hit keep/replace conflict.
        rev.assembly = create_a_fake_assembly()
        rev.save()

        html = (FIXTURES / "bom_edit.html").read_bytes()
        response = self.client.post(
            self.url,
            {
                "part_id_revision": f"{parent.full_part_number()}/{rev.revision}",
                "source_file": SimpleUploadedFile(
                    "bom_edit.html", html, content_type="text/html"
                ),
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        rev.refresh_from_db()
        pns = {
            sp.part_revision.part.full_part_number()
            for sp in rev.assembly.subparts.all()
        }
        self.assertIn("500-7777-00", pns)

    def test_upload_menu_link_present_for_admin(self):
        response = self.client.get(reverse("bom:materials"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("bom:import-systemgroup-bom"))
        self.assertContains(response, "Import SystemGroup BoM")

    def test_home_has_import_material_button(self):
        response = self.client.get(reverse("bom:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("bom:import-systemgroup-bom"))
        self.assertContains(response, "Import material")

    def test_part_bom_tab_has_no_systemgroup_link(self):
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
        self.assertNotContains(response, "Import from SystemGroup CRM")
        # Locale-aware: CI compiles fa-IR catalogs (gettext), so English msgid
        # alone fails when the active language translates this heading.
        self.assertContains(response, _("Add all subparts"))
        self.assertContains(
            response, reverse("bom:part-upload-bom", kwargs={"part_id": part.id})
        )

    def _parent_with_existing_bom(self):
        from bom.helpers import create_a_fake_assembly_with_subpart

        parts = [
            p
            for p in Part.objects.filter(organization=self.organization)
            if p.latest() is not None
        ]
        parent = next(p for p in parts if p.full_part_number() != "200-3333-00")
        other = next(p for p in parts if p.id != parent.id)
        rev = parent.latest()
        rev.assembly = create_a_fake_assembly_with_subpart(other.latest())
        rev.save()
        self.assertGreater(rev.assembly.subparts.count(), 0)
        return parent, rev

    def test_existing_bom_prompts_keep_or_replace(self):
        parent, rev = self._parent_with_existing_bom()
        html = (FIXTURES / "bom_edit.html").read_bytes()
        response = self.client.post(
            self.url,
            {
                "part_id_revision": f"{parent.full_part_number()}/{rev.revision}",
                "source_file": SimpleUploadedFile(
                    "bom_edit.html", html, content_type="text/html"
                ),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Existing BoM found")
        self.assertContains(response, "Keep existing BoM")
        self.assertContains(response, "Replace with imported BoM")

    def test_replace_existing_bom_clears_then_imports(self):
        parent, rev = self._parent_with_existing_bom()
        html = (FIXTURES / "bom_edit.html").read_bytes()
        response = self.client.post(
            self.url,
            {
                "part_id_revision": f"{parent.full_part_number()}/{rev.revision}",
                "existing_bom_action": "replace",
                "source_file": SimpleUploadedFile(
                    "bom_edit.html", html, content_type="text/html"
                ),
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        rev.refresh_from_db()
        pns = {
            sp.part_revision.part.full_part_number()
            for sp in rev.assembly.subparts.all()
        }
        self.assertIn("500-7777-00", pns)

    def test_keep_existing_bom_appends(self):
        parent, rev = self._parent_with_existing_bom()
        before = set(
            sp.part_revision.part.full_part_number()
            for sp in rev.assembly.subparts.all()
        )
        html = (FIXTURES / "bom_edit.html").read_bytes()
        response = self.client.post(
            self.url,
            {
                "part_id_revision": f"{parent.full_part_number()}/{rev.revision}",
                "existing_bom_action": "keep",
                "source_file": SimpleUploadedFile(
                    "bom_edit.html", html, content_type="text/html"
                ),
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        rev.refresh_from_db()
        after = {
            sp.part_revision.part.full_part_number()
            for sp in rev.assembly.subparts.all()
        }
        self.assertTrue(before.issubset(after))
        self.assertIn("500-7777-00", after)

    def test_creates_missing_part_and_revision(self):
        html = (FIXTURES / "bom_edit.html").read_bytes()
        # Class 500 exists from fixtures; item 9001 does not.
        self.assertFalse(
            Part.objects.filter(
                organization=self.organization, number_item="9001"
            ).exists()
        )
        response = self.client.post(
            self.url,
            {
                "part_id_revision": "500-9001-00/A1",
                "source_file": SimpleUploadedFile(
                    "bom_edit.html", html, content_type="text/html"
                ),
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        created = Part.from_part_number("500-9001-00", self.organization)
        self.assertIsNotNone(created.latest())
        self.assertEqual(created.latest().revision, "A1")
        pns = {
            sp.part_revision.part.full_part_number()
            for sp in created.latest().assembly.subparts.all()
        }
        self.assertIn("500-7777-00", pns)

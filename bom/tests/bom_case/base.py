"""Shared TestBOM setUp and helpers."""

import csv
import io
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TransactionTestCase, override_settings
from django.utils import translation
from bom.helpers import (
    create_user_and_organization,
)

TEST_FILES_DIR = "bom/test_files"


@override_settings(BOM_CONFIG=settings.BOM_CONFIG_DEFAULT)
class TestBOMBase(TransactionTestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.organization = create_user_and_organization()
        self.profile = self.user.bom_profile(organization=self.organization)
        self.profile.role = "A"
        self.profile.save()
        self.client.login(username="kasper", password="ghostpassword")
        translation.activate("en-US")

    def _assert_part_number_already_in_use(self, response):
        """Duplicate-PN errors are gettext'd; Client follows LANGUAGE_CODE (fa-IR)."""
        content = response.content.decode()
        with translation.override(settings.LANGUAGE_CODE):
            marker = translation.gettext("Part number {0} already in use.").partition("{0}")[2]
        self.assertIn(marker, content)

    def _csv_upload(self, path, strip_variation=None):
        """Open a CSV for upload; strip -VV from part_number columns when needed."""
        if strip_variation is None:
            strip_variation = self.organization.number_variation_len == 0
        with open(path, newline="") as src:
            if not strip_variation:
                return SimpleUploadedFile(path.split("/")[-1], src.read().encode())
            reader = csv.DictReader(src)
            fieldnames = reader.fieldnames
            rows = []
            for row in reader:
                for key in ("part_number",):
                    if key in row and row[key]:
                        pieces = row[key].split("-")
                        if len(pieces) == 3:
                            row[key] = f"{pieces[0]}-{pieces[1]}"
                rows.append(row)
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        return SimpleUploadedFile(path.split("/")[-1], buf.getvalue().encode())

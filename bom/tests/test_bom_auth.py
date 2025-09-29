from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse

TEST_FILES_DIR = "bom/test_files"


@override_settings(BOM_CONFIG=settings.BOM_CONFIG_DEFAULT)
class TestBomAuth(TransactionTestCase):
    def setUp(self):
        self.client = Client()

    def test_create_organization(self):
        User.objects.create_user("kasper", "kasper@McFadden.com", "ghostpassword")
        self.client.login(username="kasper", password="ghostpassword")

        organization_form_data = {
            "name": "Kasper Inc.",
            "number_scheme": "S",
            "number_class_code_len": 3,
            "number_item_len": 4,
            "number_variation_len": 2,
        }

        response = self.client.post(
            reverse("bom:organization-create"), organization_form_data
        )
        self.assertEqual(response.status_code, 302)

    def test_create_organization_intelligent(self):
        User.objects.create_user("kasper", "kasper@McFadden.com", "ghostpassword")
        self.client.login(username="kasper", password="ghostpassword")

        organization_form_data = {
            "name": "Kasper Inc.",
            "number_scheme": "I",
        }

        response = self.client.post(
            reverse("bom:organization-create"), organization_form_data
        )
        self.assertEqual(response.status_code, 302)

    def test_create_organization_intelligent_with_fields(self):
        User.objects.create_user("kasper", "kasper@McFadden.com", "ghostpassword")
        self.client.login(username="kasper", password="ghostpassword")

        organization_form_data = {
            "name": "Kasper Inc.",
            "number_scheme": "I",
            "number_class_code_len": 3,
            "number_item_len": 4,
            "number_variation_len": 2,
        }

        response = self.client.post(
            reverse("bom:organization-create"), organization_form_data
        )
        self.assertEqual(response.status_code, 302)

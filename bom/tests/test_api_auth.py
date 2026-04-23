from django.contrib.auth.models import User
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient

from bom.models import Organization, UserMeta


class TestApiAuth(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "ghostpassword"
        self.user = User.objects.create_user(
            username="kasper",
            email="kasper@example.com",
            password=self.password,
            first_name="Kasper",
            last_name="McFadden",
        )
        self.organization = Organization.objects.create(
            name="Kasper Inc.",
            subscription="F",
            owner=self.user,
        )
        UserMeta.objects.create(
            user=self.user, organization=self.organization, role="A"
        )

    def _get_tokens(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": self.user.username, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        return response.data

    def test_token_obtain_pair(self):
        self._get_tokens()

    def test_auth_me_requires_authentication(self):
        response = self.client.get(reverse("auth_me"))
        self.assertEqual(response.status_code, 401)

    def test_auth_me_returns_current_user_and_profile(self):
        tokens = self._get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = self.client.get(reverse("auth_me"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.user.id)
        self.assertEqual(response.data["username"], self.user.username)
        self.assertEqual(response.data["profile"]["role"], "A")
        self.assertEqual(
            response.data["profile"]["organization"]["id"],
            self.organization.id,
        )

    def test_logout_blacklists_refresh_token(self):
        tokens = self._get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        logout_response = self.client.post(
            reverse("token_blacklist"),
            {"refresh": tokens["refresh"]},
            format="json",
        )
        self.assertEqual(logout_response.status_code, 200)

        refresh_response = self.client.post(
            reverse("token_refresh"),
            {"refresh": tokens["refresh"]},
            format="json",
        )
        self.assertIn(refresh_response.status_code, [400, 401])

    def test_logout_requires_refresh_token(self):
        tokens = self._get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = self.client.post(reverse("token_blacklist"), {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_user_detail_forbidden_for_different_user(self):
        other_user = User.objects.create_user(
            username="alex",
            email="alex@example.com",
            password="anotherpassword",
        )
        tokens = self._get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = self.client.get(
            reverse("user-detail", kwargs={"user_id": other_user.id})
        )
        self.assertEqual(response.status_code, 403)

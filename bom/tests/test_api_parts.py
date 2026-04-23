from django.contrib.auth.models import User
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient

from bom.models import (
    Manufacturer,
    ManufacturerPart,
    Organization,
    Part,
    PartClass,
    PartRevision,
    UserMeta,
)


class TestApiParts(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "ghostpassword"
        self.user = User.objects.create_user(
            username="kasper",
            email="kasper@example.com",
            password=self.password,
        )
        self.organization = Organization.objects.create(
            name="Kasper Inc.",
            subscription="F",
            owner=self.user,
        )
        UserMeta.objects.create(
            user=self.user, organization=self.organization, role="A"
        )

        self.part_class = PartClass.objects.create(
            organization=self.organization,
            code="RES",
            name="Resistors",
        )
        self.manufacturer = Manufacturer.objects.create(
            organization=self.organization,
            name="Ohmite",
        )

    def _auth(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": self.user.username, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def _create_part_with_latest_revision(
        self,
        number_item,
        number_variation,
        description,
        searchable_synopsis,
    ):
        part = Part.objects.create(
            organization=self.organization,
            number_class=self.part_class,
            number_item=number_item,
            number_variation=number_variation,
        )
        manufacturer_part = ManufacturerPart.objects.create(
            part=part,
            manufacturer=self.manufacturer,
            manufacturer_part_number=f"MPN-{number_item}",
        )
        part.primary_manufacturer_part = manufacturer_part
        part.save()
        PartRevision.objects.create(
            part=part,
            revision="1",
            description=description,
            searchable_synopsis=searchable_synopsis,
            displayable_synopsis=searchable_synopsis,
        )
        latest = PartRevision.objects.create(
            part=part,
            revision="2",
            description=f"latest-{description}",
            searchable_synopsis=f"latest-{searchable_synopsis}",
            displayable_synopsis=f"latest-{searchable_synopsis}",
        )
        return part, latest

    def test_parts_list_requires_authentication(self):
        response = self.client.get(reverse("part-list"))
        self.assertEqual(response.status_code, 401)

    def test_parts_list_returns_only_latest_revision_rows_for_org(self):
        self._auth()
        _, latest = self._create_part_with_latest_revision(
            number_item="0001",
            number_variation="01",
            description="resistor",
            searchable_synopsis="10k resistor",
        )

        outsider = User.objects.create_user(
            username="outsider",
            email="outsider@example.com",
            password="anotherpassword",
        )
        outsider_org = Organization.objects.create(
            name="Outsider Org",
            subscription="F",
            owner=outsider,
        )
        outsider_class = PartClass.objects.create(
            organization=outsider_org,
            code="CAP",
            name="Capacitors",
        )
        outsider_part = Part.objects.create(
            organization=outsider_org,
            number_class=outsider_class,
            number_item="9999",
            number_variation="99",
        )
        PartRevision.objects.create(part=outsider_part, revision="1")

        response = self.client.get(reverse("part-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["id"], latest.id)
        self.assertEqual(row["part_class"]["code"], "RES")
        self.assertEqual(row["primary_manufacturer_name"], "Ohmite")

    def test_parts_list_supports_search_query(self):
        self._auth()
        self._create_part_with_latest_revision(
            number_item="0001",
            number_variation="01",
            description="resistor",
            searchable_synopsis="10k resistor",
        )
        self._create_part_with_latest_revision(
            number_item="0002",
            number_variation="01",
            description="capacitor",
            searchable_synopsis="1uF capacitor",
        )

        response = self.client.get(reverse("part-list"), {"q": "resistor"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertIn("resistor", response.data["results"][0]["synopsis"])

    def test_parts_list_supports_pagination(self):
        self._auth()
        for index in range(3):
            self._create_part_with_latest_revision(
                number_item=f"00{index + 1}0",
                number_variation="01",
                description=f"desc-{index}",
                searchable_synopsis=f"synopsis-{index}",
            )

        response = self.client.get(reverse("part-list"), {"page_size": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])

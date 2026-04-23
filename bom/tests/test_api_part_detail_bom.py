from django.contrib.auth.models import User
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient

from bom.models import (
    AssemblySubparts,
    Organization,
    Part,
    PartClass,
    PartRevision,
    Subpart,
    UserMeta,
)


class TestApiPartDetailAndBom(TransactionTestCase):
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

        self.parent_part = Part.objects.create(
            organization=self.organization,
            number_class=self.part_class,
            number_item="0001",
            number_variation="01",
        )
        self.parent_rev1 = PartRevision.objects.create(
            part=self.parent_part,
            revision="1",
            description="parent-r1",
            searchable_synopsis="parent older revision",
            displayable_synopsis="parent older revision",
        )
        self.parent_latest = PartRevision.objects.create(
            part=self.parent_part,
            revision="2",
            description="parent-r2",
            searchable_synopsis="parent latest revision",
            displayable_synopsis="parent latest revision",
        )

        self.child_part = Part.objects.create(
            organization=self.organization,
            number_class=self.part_class,
            number_item="0002",
            number_variation="01",
        )
        self.child_latest = PartRevision.objects.create(
            part=self.child_part,
            revision="1",
            description="child-r1",
            searchable_synopsis="child part",
            displayable_synopsis="child part",
        )

        subpart = Subpart.objects.create(
            part_revision=self.child_latest,
            count=2,
            reference="R1,R2",
            do_not_load=False,
        )
        AssemblySubparts.objects.create(
            assembly=self.parent_latest.assembly,
            subpart=subpart,
        )

    def _auth(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": self.user.username, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_part_detail_requires_authentication(self):
        response = self.client.get(
            reverse("part-detail", kwargs={"part_id": self.parent_part.id})
        )
        self.assertEqual(response.status_code, 401)

    def test_part_detail_returns_latest_revision_by_default(self):
        self._auth()
        response = self.client.get(
            reverse("part-detail", kwargs={"part_id": self.parent_part.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.parent_latest.id)
        self.assertEqual(response.data["description"], "parent-r2")

    def test_part_detail_can_select_specific_revision(self):
        self._auth()
        response = self.client.get(
            reverse("part-detail", kwargs={"part_id": self.parent_part.id}),
            {"revision_id": str(self.parent_rev1.id)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.parent_rev1.id)
        self.assertEqual(response.data["description"], "parent-r1")

    def test_part_detail_is_scoped_to_organization(self):
        self._auth()
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

        response = self.client.get(
            reverse("part-detail", kwargs={"part_id": outsider_part.id})
        )
        self.assertEqual(response.status_code, 404)

    def test_part_bom_returns_indented_tree_items(self):
        self._auth()
        response = self.client.get(
            reverse("part-bom", kwargs={"part_id": self.parent_part.id}),
            {"view": "indented", "quantity": "5"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["view"], "indented")
        self.assertEqual(response.data["quantity"], 5)
        self.assertGreaterEqual(len(response.data["items"]), 2)
        child_rows = [
            item
            for item in response.data["items"]
            if item["part_revision_id"] == self.child_latest.id
        ]
        self.assertEqual(len(child_rows), 1)
        self.assertEqual(child_rows[0]["references"], "R1, R2")
        self.assertEqual(child_rows[0]["indent_level"], 1)

    def test_part_bom_supports_flat_view(self):
        self._auth()
        response = self.client.get(
            reverse("part-bom", kwargs={"part_id": self.parent_part.id}),
            {"view": "flat"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["view"], "flat")

    def test_part_bom_rejects_invalid_view(self):
        self._auth()
        response = self.client.get(
            reverse("part-bom", kwargs={"part_id": self.parent_part.id}),
            {"view": "invalid"},
        )
        self.assertEqual(response.status_code, 400)

    def test_part_bom_rejects_invalid_quantity(self):
        self._auth()
        response = self.client.get(
            reverse("part-bom", kwargs={"part_id": self.parent_part.id}),
            {"quantity": "0"},
        )
        self.assertEqual(response.status_code, 400)

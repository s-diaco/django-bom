"""BOM tests: revisions."""

from django.urls import reverse
from bom.helpers import (
    create_some_fake_parts,
)


class RevisionsTestsMixin:
    def test_part_revision_release(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        response = self.client.get(
            reverse(
                "bom:part-revision-release",
                kwargs={"part_id": p1.id, "part_revision_id": p1.latest().id},
            )
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse(
                "bom:part-revision-release",
                kwargs={"part_id": p1.id, "part_revision_id": p1.latest().id},
            )
        )

        self.assertEqual(response.status_code, 302)

    def test_part_revision_revert(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        response = self.client.get(
            reverse(
                "bom:part-revision-revert",
                kwargs={"part_id": p1.id, "part_revision_id": p1.latest().id},
            )
        )

        self.assertEqual(response.status_code, 302)

    def test_part_revision_new(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)

        response = self.client.get(reverse("bom:part-revision-new", kwargs={"part_id": p1.id}))
        self.assertEqual(response.status_code, 200)

        # Create new part revision from part without an existing part revision
        response = self.client.get(reverse("bom:part-revision-new", kwargs={"part_id": p4.id}))
        self.assertEqual(response.status_code, 200)

        new_part_revision_form_data = {
            "description": "new rev",
            "revision": "4",
            "attribute": "resistance",
            "value": "10k",
            "part": p1.id,
            "configuration": "W",
            "copy_assembly": "False",
        }

        response = self.client.post(
            reverse("bom:part-revision-new", kwargs={"part_id": p1.id}),
            new_part_revision_form_data,
        )

        self.assertEqual(response.status_code, 302)

        # Create new part revision, copy over the assembly, increment revision, then make sure the old revision
        # didn't change
        new_part_revision_form_data = {
            "description": "new rev",
            "revision": "5",
            "part": p3.id,
            "configuration": "W",
            "copy_assembly": "true",
        }

        response = self.client.post(
            reverse("bom:part-revision-new", kwargs={"part_id": p3.id}),
            new_part_revision_form_data,
        )

        revs = p3.revisions().order_by("-id")
        latest = revs[0]
        previous = revs[1]
        previous_subpart_ids = previous.assembly.subparts.all().values_list("id", flat=True)
        new_subpart_ids = latest.assembly.subparts.all().values_list("id", flat=True)

        self.assertEqual(response.status_code, 302)
        self.assertNotEqual([], new_subpart_ids)
        for nsid in new_subpart_ids:
            self.assertNotIn(nsid, previous_subpart_ids)

    def test_part_revision_edit(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        response = self.client.get(
            reverse(
                "bom:part-revision-edit",
                kwargs={"part_id": p1.id, "part_revision_id": p1.latest().id},
            )
        )

        self.assertEqual(response.status_code, 200)

        edit_part_revision_form_data = {
            "description": "new rev",
            "revision": "4",
            "attribute": "resistance",
            "value": "10k",
            "part": p1.id,
        }

        response = self.client.post(
            reverse(
                "bom:part-revision-edit",
                kwargs={"part_id": p1.id, "part_revision_id": p1.latest().id},
            ),
            edit_part_revision_form_data,
        )

        self.assertEqual(response.status_code, 302)

    def test_part_revision_delete(self):
        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        response = self.client.post(
            reverse(
                "bom:part-revision-delete",
                kwargs={"part_id": p1.id, "part_revision_id": p1.latest().id},
            )
        )

        self.assertEqual(response.status_code, 302)

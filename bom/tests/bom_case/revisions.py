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

    def test_displayable_synopsis_uses_product_type_name(self):
        from django.conf import settings
        from django.utils import translation
        from django.utils.translation import gettext

        from bom.models import PartRevision

        (p1, p2, p3, p4) = create_some_fake_parts(organization=self.organization)
        self.organization.ensure_default_product_types()
        rev = p1.latest()
        rev.material = "with_loi"
        # Even if the thread is en-US (TestBOMBase), displayable freezes LANGUAGE_CODE.
        translation.activate("en-US")
        rev.save()
        rev.refresh_from_db()

        pt = rev.product_type
        self.assertIsNotNone(pt)
        self.assertEqual(pt.name, "Frit")
        with translation.override(settings.LANGUAGE_CODE):
            material_label = gettext(pt.name)
        self.assertNotEqual(material_label, "with_loi")
        self.assertIn(material_label, rev.displayable_synopsis)
        self.assertNotIn("with_loi", rev.displayable_synopsis)
        # Searchable synopsis keeps the raw choice code.
        self.assertIn("with_loi", rev.searchable_synopsis)
        self.assertNotIn(material_label, rev.searchable_synopsis)

        if settings.LANGUAGE_CODE.lower().startswith("fa"):
            self.assertEqual(material_label, "فریت")
            self.assertIn("فریت", rev.displayable_synopsis)
            self.assertNotIn("Frit", rev.displayable_synopsis)

        # Stale English/raw cache is fixed by the shared refresh (migration 0069).
        PartRevision.objects.filter(pk=rev.pk).update(
            displayable_synopsis=f"{rev.description or ''} Frit with_loi "
        )
        rev.refresh_from_db()
        self.assertIn("with_loi", rev.displayable_synopsis)
        PartRevision.refresh_all_cached_synopses()
        rev.refresh_from_db()
        self.assertIn(material_label, rev.displayable_synopsis)
        self.assertNotIn("with_loi", rev.displayable_synopsis)
        if settings.LANGUAGE_CODE.lower().startswith("fa"):
            self.assertNotIn("Frit", rev.displayable_synopsis)
        self.assertEqual(rev.synopsis(), rev.displayable_synopsis)

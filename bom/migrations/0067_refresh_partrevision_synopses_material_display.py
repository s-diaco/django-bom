"""Refresh cached PartRevision synopses after material display labels.

displayable_synopsis / searchable_synopsis are written on PartRevision.save().
Existing rows still store raw material codes (with_loi / no_loi / no_bom) until
re-saved. Recompute both fields with current generate_synopsis() so displayable
uses get_material_display() while searchable keeps the raw code.
"""

from django.db import migrations


def refresh_part_revision_synopses(apps, schema_editor):
    # Historical models lack generate_synopsis / get_material_display; use the
    # live model so this stays aligned with bom.models.PartRevision.
    from bom.models import PartRevision

    batch = []
    fields = ["searchable_synopsis", "displayable_synopsis"]
    for pr in PartRevision.objects.all().iterator(chunk_size=500):
        pr.searchable_synopsis = pr.generate_synopsis(True)
        pr.displayable_synopsis = pr.generate_synopsis(False)
        batch.append(pr)
        if len(batch) >= 500:
            PartRevision.objects.bulk_update(batch, fields)
            batch.clear()
    if batch:
        PartRevision.objects.bulk_update(batch, fields)


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0066_organization_systemgroup_crm_base_url"),
    ]

    operations = [
        migrations.RunPython(
            refresh_part_revision_synopses,
            migrations.RunPython.noop,
        ),
    ]

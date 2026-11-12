"""Re-refresh PartRevision synopses to use ProductType names.

0067 regenerated displayable_synopsis with MATERIAL_TYPES /
get_material_display(). Displayable synopsis should use the org's
ProductType.name (gettext) instead. Re-run the same bulk refresh against
current generate_synopsis().
"""

from django.db import migrations


def refresh_part_revision_synopses(apps, schema_editor):
    # Live model: generate_synopsis / product_type are not on historical models.
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
        ("bom", "0067_refresh_partrevision_synopses_material_display"),
    ]

    operations = [
        migrations.RunPython(
            refresh_part_revision_synopses,
            migrations.RunPython.noop,
        ),
    ]

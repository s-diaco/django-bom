"""Re-refresh displayable synopses under settings.LANGUAGE_CODE.

Prior refreshes could freeze English ProductType names into
displayable_synopsis when gettext ran without activating fa-IR.
generate_synopsis(False) now always uses translation.override(LANGUAGE_CODE);
recompute cached rows so migrate fixes prod.
"""

from django.db import migrations


def refresh_part_revision_synopses(apps, schema_editor):
    from bom.models import PartRevision

    PartRevision.refresh_all_cached_synopses()


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0068_refresh_synopses_product_type_names"),
    ]

    operations = [
        migrations.RunPython(
            refresh_part_revision_synopses,
            migrations.RunPython.noop,
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0066_organization_systemgroup_crm_base_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="systemgroup_part_id_max_results",
            field=models.PositiveIntegerField(
                default=10,
                help_text=(
                    "Max CRM BoM rows returned for Part ID StartsWith search "
                    "(Load revisions). Default 10."
                ),
            ),
        ),
    ]

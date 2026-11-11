from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0065_systemgroup_import_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="systemgroup_crm_base_url",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Base URL of the on-LAN SystemGroup CRM "
                    "(e.g. http://192.168.3.193/). Required for live import."
                ),
                max_length=512,
            ),
        ),
    ]

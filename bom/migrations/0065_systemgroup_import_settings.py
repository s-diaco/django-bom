from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0064_sellerpart_unit_cost_two_decimals"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="systemgroup_import_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Allow organization admins who have saved SystemGroup "
                    "credentials to import BoMs from the CRM."
                ),
            ),
        ),
        migrations.AddField(
            model_name="usermeta",
            name="systemgroup_username",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="usermeta",
            name="systemgroup_password",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]

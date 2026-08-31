from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("bom", "0055_usermeta_calendar"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="customer",
            name="default_profit_percent",
        ),
    ]

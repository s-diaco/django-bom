from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bom", "0069_usermeta_birthday"),
    ]

    operations = [
        migrations.AddField(
            model_name="usermeta",
            name="birthday_jalali",
            field=models.BooleanField(default=False),
        ),
    ]

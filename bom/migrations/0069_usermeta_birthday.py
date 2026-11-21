from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bom", "0068_partrevision_material_product_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="usermeta",
            name="birthday_day",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[MinValueValidator(1), MaxValueValidator(31)],
            ),
        ),
        migrations.AddField(
            model_name="usermeta",
            name="birthday_month",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[MinValueValidator(1), MaxValueValidator(12)],
            ),
        ),
    ]

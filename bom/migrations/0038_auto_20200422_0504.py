# Generated by Django 3.0.5 on 2020-04-22 05:04

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0037_auto_20200405_1642"),
    ]

    operations = [
        migrations.AlterField(
            model_name="part",
            name="number_variation",
            field=models.CharField(
                blank=True,
                default=None,
                max_length=16,
                null=True,
                validators=[
                    django.core.validators.RegexValidator(
                        "^[0-9a-zA-Z]*$", "Only alphanumeric characters are allowed."
                    )
                ],
            ),
        ),
    ]

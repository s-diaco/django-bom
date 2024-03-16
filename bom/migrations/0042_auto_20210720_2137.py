# Generated by Django 3.2.4 on 2021-07-20 21:37

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0041_organization_subscription_quantity"),
    ]

    operations = [
        migrations.AddField(
            model_name="partrevision",
            name="temperature_rating_range_max",
            field=models.DecimalField(
                blank=True, decimal_places=3, default=None, max_digits=7, null=True
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="temperature_rating_range_min",
            field=models.DecimalField(
                blank=True, decimal_places=3, default=None, max_digits=7, null=True
            ),
        ),
    ]

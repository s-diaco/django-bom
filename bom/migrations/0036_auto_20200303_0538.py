# Generated by Django 2.2.9 on 2020-03-03 05:38

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0035_auto_20200303_0111"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="partclass",
            unique_together={("code", "organization")},
        ),
    ]

# Generated by Django 2.1.1 on 2018-11-26 02:01

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0008_auto_20181030_0427"),
    ]

    operations = [
        migrations.AddField(
            model_name="subpart",
            name="reference",
            field=models.TextField(blank=True, default="", null=True),
        ),
    ]

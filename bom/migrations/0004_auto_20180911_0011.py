# Generated by Django 2.1.1 on 2018-09-11 00:11

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0003_sellerpart_data_source"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sellerpart",
            name="data_source",
            field=models.CharField(blank=True, default=None, max_length=32, null=True),
        ),
    ]

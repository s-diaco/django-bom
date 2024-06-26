# Generated by Django 2.2.2 on 2019-08-11 21:40

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0021_auto_20190627_0428"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sellerpart",
            name="minimum_order_quantity",
            field=models.IntegerField(default=1),
        ),
        migrations.AlterField(
            model_name="sellerpart",
            name="minimum_pack_quantity",
            field=models.IntegerField(default=1),
        ),
        migrations.AlterField(
            model_name="sellerpart",
            name="nre_cost",
            field=models.DecimalField(decimal_places=4, default=0, max_digits=8),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="sellerpart",
            name="unit_cost",
            field=models.DecimalField(decimal_places=4, default=0, max_digits=8),
            preserve_default=False,
        ),
    ]

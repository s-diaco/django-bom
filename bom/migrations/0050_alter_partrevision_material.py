# Generated by Django 5.0.6 on 2024-06-30 07:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bom", "0049_alter_sellerpart_unit_cost"),
    ]

    operations = [
        migrations.AlterField(
            model_name="partrevision",
            name="material",
            field=models.CharField(
                blank=True,
                choices=[
                    ("with_loi", "با لحاظ کردن پرت (فریت)"),
                    ("no_loi", "بدون احتساب پرت (کامپوند، جوهر یا …)"),
                    ("no_bom", "مواد اولیه"),
                ],
                default=None,
                max_length=32,
                null=True,
            ),
        ),
    ]
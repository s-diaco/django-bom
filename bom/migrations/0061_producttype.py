from decimal import Decimal

import djmoney.models.fields
from django.db import migrations, models
import django.db.models.deletion


DEFAULT_PRODUCT_TYPES = (
    ("with_loi", "With loss (LOI) (Frit)", True, True),
    ("no_loi", "Without loss (LOI) (compound, ink, …)", True, False),
    ("no_bom", "Raw materials", False, False),
)


def seed_product_types(apps, schema_editor):
    Organization = apps.get_model("bom", "Organization")
    ProductType = apps.get_model("bom", "ProductType")
    PartRevision = apps.get_model("bom", "PartRevision")
    SellerPart = apps.get_model("bom", "SellerPart")

    for org in Organization.objects.all():
        currency = org.currency or "USD"
        for index, (code, name, has_bom, apply_loi) in enumerate(DEFAULT_PRODUCT_TYPES):
            amount = Decimal(0)
            overhead_currency = currency
            if has_bom:
                part_ids = (
                    PartRevision.objects.filter(
                        part__organization=org, material=code
                    )
                    .values_list("part_id", flat=True)
                    .distinct()
                )
                seller_part = (
                    SellerPart.objects.filter(
                        manufacturer_part__part_id__in=part_ids
                    )
                    .exclude(unit_cost=0)
                    .first()
                )
                if seller_part is not None:
                    amount = seller_part.unit_cost
                    overhead_currency = seller_part.unit_cost_currency or currency
            ProductType.objects.get_or_create(
                organization=org,
                code=code,
                defaults={
                    "name": name,
                    "has_bom": has_bom,
                    "apply_loi": apply_loi,
                    "overhead": amount,
                    "overhead_currency": overhead_currency,
                    "sort_order": index,
                },
            )


def unseed_product_types(apps, schema_editor):
    ProductType = apps.get_model("bom", "ProductType")
    ProductType.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0060_nullable_unknown_seller_manufacturer"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductType",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", models.SlugField(max_length=32)),
                ("name", models.CharField(max_length=255)),
                ("has_bom", models.BooleanField(default=True)),
                ("apply_loi", models.BooleanField(default=False)),
                (
                    "overhead_currency",
                    djmoney.models.fields.CurrencyField(
                        default="USD", editable=False, max_length=3
                    ),
                ),
                (
                    "overhead",
                    djmoney.models.fields.MoneyField(
                        decimal_places=0,
                        default=Decimal("0"),
                        default_currency="USD",
                        max_digits=19,
                    ),
                ),
                ("sort_order", models.PositiveIntegerField(default=0)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="product_types",
                        to="bom.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order", "code"],
                "unique_together": {("organization", "code")},
            },
        ),
        migrations.RunPython(seed_product_types, unseed_product_types),
    ]

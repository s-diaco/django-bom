# Generated manually for nullable unknown seller/manufacturer

from django.db import migrations, models
import django.db.models.deletion


DEFAULT_PLACEHOLDER_NAME = "انتخاب نشده (پیش فرض)"


def null_out_placeholder_sellers_and_manufacturers(apps, schema_editor):
    Seller = apps.get_model("bom", "Seller")
    SellerPart = apps.get_model("bom", "SellerPart")
    Manufacturer = apps.get_model("bom", "Manufacturer")
    ManufacturerPart = apps.get_model("bom", "ManufacturerPart")

    placeholder_sellers = Seller.objects.filter(name__iexact=DEFAULT_PLACEHOLDER_NAME)
    SellerPart.objects.filter(seller__in=placeholder_sellers).update(seller=None)
    placeholder_sellers.delete()

    placeholder_mfgs = Manufacturer.objects.filter(
        name__iexact=DEFAULT_PLACEHOLDER_NAME
    )
    ManufacturerPart.objects.filter(manufacturer__in=placeholder_mfgs).update(
        manufacturer=None
    )
    placeholder_mfgs.delete()


def noop_reverse(apps, schema_editor):
    # Sentinel rows are not recreated; null FKs remain valid.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0059_sync_sellerpart_shipping_currency"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sellerpart",
            name="seller",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="bom.seller",
            ),
        ),
        migrations.AlterField(
            model_name="manufacturerpart",
            name="manufacturer",
            field=models.ForeignKey(
                blank=True,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="bom.manufacturer",
            ),
        ),
        migrations.RunPython(
            null_out_placeholder_sellers_and_manufacturers,
            noop_reverse,
        ),
    ]

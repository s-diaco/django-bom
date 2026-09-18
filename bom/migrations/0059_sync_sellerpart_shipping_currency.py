# Data migration: align shipping_currency with unit_cost_currency after 0058
# defaulted shipping to USD.

from django.db import migrations
from django.db.models import F


def sync_shipping_currency(apps, schema_editor):
    SellerPart = apps.get_model("bom", "SellerPart")
    SellerPart.objects.exclude(shipping_currency=F("unit_cost_currency")).update(
        shipping_currency=F("unit_cost_currency")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("bom", "0058_sellerpart_shipping_customs_duty"),
    ]

    operations = [
        migrations.RunPython(sync_shipping_currency, migrations.RunPython.noop),
    ]

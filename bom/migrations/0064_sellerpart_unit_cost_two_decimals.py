import djmoney.models.fields
import djmoney.money
from django.db import migrations


class Migration(migrations.Migration):
    """Re-assert 2dp on seller-part money columns.

    Intermediate LI-43 work briefly used decimal_places=4 under the same
    0063 migration name; DBs that applied that revision stay at scale 4
    while Django state says 2. Re-alter so storage matches
    UNIT_COST_DECIMAL_PLACES.
    """

    dependencies = [
        ("bom", "0063_sellerpart_decimal_unit_cost"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sellerpart",
            name="shipping",
            field=djmoney.models.fields.MoneyField(
                decimal_places=2,
                default=djmoney.money.Money(0, "USD"),
                default_currency="USD",
                max_digits=19,
            ),
        ),
        migrations.AlterField(
            model_name="sellerpart",
            name="unit_cost",
            field=djmoney.models.fields.MoneyField(
                decimal_places=2, default_currency="USD", max_digits=19
            ),
        ),
    ]

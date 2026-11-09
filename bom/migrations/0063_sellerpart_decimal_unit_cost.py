import djmoney.models.fields
import djmoney.money
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("bom", "0062_customerprice_order_quantity_verbose"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customerprice",
            name="base_cost",
            field=djmoney.models.fields.MoneyField(
                decimal_places=4, default_currency="USD", max_digits=19
            ),
        ),
        migrations.AlterField(
            model_name="customerprice",
            name="price",
            field=djmoney.models.fields.MoneyField(
                decimal_places=4, default_currency="USD", max_digits=19
            ),
        ),
        migrations.AlterField(
            model_name="producttype",
            name="overhead",
            field=djmoney.models.fields.MoneyField(
                decimal_places=4,
                default=djmoney.money.Money(0, "USD"),
                default_currency="USD",
                max_digits=19,
            ),
        ),
        migrations.AlterField(
            model_name="sellerpart",
            name="shipping",
            field=djmoney.models.fields.MoneyField(
                decimal_places=4,
                default=djmoney.money.Money(0, "USD"),
                default_currency="USD",
                max_digits=19,
            ),
        ),
        migrations.AlterField(
            model_name="sellerpart",
            name="unit_cost",
            field=djmoney.models.fields.MoneyField(
                decimal_places=4, default_currency="USD", max_digits=19
            ),
        ),
    ]

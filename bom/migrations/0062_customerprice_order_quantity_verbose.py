from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bom", "0061_producttype"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customerprice",
            name="quantity",
            field=models.PositiveIntegerField(verbose_name="Order quantity"),
        ),
    ]

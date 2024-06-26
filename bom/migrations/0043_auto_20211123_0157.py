# Generated by Django 3.2.4 on 2021-11-23 01:57

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0042_auto_20210720_2137"),
    ]

    operations = [
        migrations.AlterField(
            model_name="partrevision",
            name="value_units",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "-----"),
                    ("Ohms", "Ω"),
                    ("mOhms", "mΩ"),
                    ("kOhms", "kΩ"),
                    ("MOhms", "MΩ"),
                    ("F", "F"),
                    ("pF", "pF"),
                    ("nF", "nF"),
                    ("uF", "μF"),
                    ("V", "V"),
                    ("uV", "μV"),
                    ("mV", "mV"),
                    ("A", "A"),
                    ("uA", "μA"),
                    ("mA", "mA"),
                    ("C", "°C"),
                    ("F", "°F"),
                    ("H", "H"),
                    ("nH", "nH"),
                    ("mH", "mH"),
                    ("uH", "μH"),
                    ("Hz", "Hz"),
                    ("kHz", "kHz"),
                    ("MHz", "MHz"),
                    ("GHz", "GHz"),
                    ("Other", "Other"),
                ],
                default=None,
                max_length=5,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="subpart",
            name="count",
            field=models.FloatField(
                default=1, validators=[django.core.validators.MinValueValidator(0)]
            ),
        ),
    ]

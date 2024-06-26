# Generated by Django 2.2.5 on 2019-12-05 23:46

from django.db import migrations, models
import django.utils.timezone
import bom


def update_part_classes(apps, schema_editor):
    Part = apps.get_model("bom", "Part")
    PartClass = apps.get_model("bom", "PartClass")
    Organization = apps.get_model("bom", "Organization")

    for o in Organization.objects.all():
        for p in Part.objects.filter(organization=o):
            pc = p.number_class
            new_pc, _ = PartClass.objects.get_or_create(
                code=pc.code, name=pc.name, comment=pc.comment, organization=o
            )
            p.number_class = new_pc
            p.save()


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0022_auto_20190811_2140"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="partclass",
            options={"ordering": ["code"]},
        ),
        migrations.AlterModelOptions(
            name="partrevision",
            options={"ordering": ["part"]},
        ),
        migrations.AddField(
            model_name="organization",
            name="number_item_len",
            field=models.PositiveIntegerField(
                default=4,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(10),
                ],
            ),
        ),
        migrations.AddField(
            model_name="partclass",
            name="organization",
            field=models.ForeignKey(
                default=1,
                on_delete=django.db.models.deletion.CASCADE,
                to="bom.Organization",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="partrevision",
            name="color",
            field=models.CharField(blank=True, default=None, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="current_rating",
            field=models.DecimalField(
                blank=True, decimal_places=3, default=None, max_digits=7, null=True
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="current_rating_units",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "-----"),
                    ("A", "A"),
                    ("uA", "μV"),
                    ("mA", "mA"),
                    ("kA", "kA"),
                    ("MA", "MA"),
                    ("Other", "Other"),
                ],
                default=None,
                max_length=2,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="finish",
            field=models.CharField(blank=True, default=None, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="frequency",
            field=models.DecimalField(
                blank=True, decimal_places=3, default=None, max_digits=7, null=True
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="frequency_units",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "-----"),
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
        migrations.AddField(
            model_name="partrevision",
            name="height",
            field=models.DecimalField(
                blank=True, decimal_places=3, default=None, max_digits=7, null=True
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="height_units",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "-----"),
                    ("mil", "mil"),
                    ("in", "in"),
                    ("ft", "ft"),
                    ("yd", "yd"),
                    ("km", "km"),
                    ("m", "m"),
                    ("cm", "cm"),
                    ("um", "um"),
                    ("nm", "nm"),
                    ("Other", "Other"),
                ],
                default=None,
                max_length=5,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="interface",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "-----"),
                    ("I2C", "I2C"),
                    ("SPI", "SPI"),
                    ("CAN", "CAN"),
                    ("One-Wire", "1-Wire"),
                    ("RS485", "RS-485"),
                    ("RS232", "RS-232"),
                    ("WiFi", "Wi-Fi"),
                    ("4G", "4G"),
                    ("BT", "Bluetooth"),
                    ("BTLE", "Bluetooth LE"),
                    ("Z_Wave", "Z-Wave"),
                    ("Zigbee", "Zigbee"),
                    ("LAN", "LAN"),
                    ("USB", "USB"),
                    ("HDMI", "HDMI"),
                    ("Other", "Other"),
                ],
                default=None,
                max_length=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="length",
            field=models.DecimalField(
                blank=True, decimal_places=3, default=None, max_digits=7, null=True
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="length_units",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "-----"),
                    ("mil", "mil"),
                    ("in", "in"),
                    ("ft", "ft"),
                    ("yd", "yd"),
                    ("km", "km"),
                    ("m", "m"),
                    ("cm", "cm"),
                    ("um", "um"),
                    ("nm", "nm"),
                    ("Other", "Other"),
                ],
                default=None,
                max_length=5,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="material",
            field=models.CharField(blank=True, default=None, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="memory",
            field=models.DecimalField(
                blank=True, decimal_places=3, default=None, max_digits=7, null=True
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="memory_units",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "-----"),
                    ("KB", "KB"),
                    ("MB", "MB"),
                    ("GB", "GB"),
                    ("TB", "TB"),
                    ("Other", "Other"),
                ],
                default=None,
                max_length=5,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="package",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "-----"),
                    ("0201 smd", "0201 smd"),
                    ("0402 smd", "0402 smd"),
                    ("0603 smd", "0603 smd"),
                    ("0805 smd", "0805 smd"),
                    ("1206 smd", "1206 smd"),
                    ("1210 smd", "1210 smd"),
                    ("1812 smd", "1812 smd"),
                    ("2010 smd", "2010 smd"),
                    ("2512 smd", "2512 smd"),
                    ("1/8 radial", "1/8 radial"),
                    ("1/4 radial", "1/4 radial"),
                    ("1/2 radial", "1/2 radial"),
                    ("Size A", "Size A"),
                    ("Size B", "Size B"),
                    ("Size C", "Size C"),
                    ("Size D", "Size D"),
                    ("Size E", "Size E"),
                    ("SOT-23", "SOT-23"),
                    ("SOT-223", "SOT-233"),
                    ("DIL", "DIL"),
                    ("SOP", "SOP"),
                    ("SOIC", "SOIC"),
                    ("QFN", "QFN"),
                    ("QFP", "QFP"),
                    ("QFT", "QFT"),
                    ("PLCCP", "PLCC"),
                    ("VGA", "VGA"),
                    ("Other", "Other"),
                ],
                default=None,
                max_length=16,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="pin_count",
            field=models.DecimalField(
                blank=True, decimal_places=0, default=None, max_digits=3, null=True
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="power_rating",
            field=models.DecimalField(
                blank=True, decimal_places=3, default=None, max_digits=7, null=True
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="power_rating_units",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "-----"),
                    ("W", "W"),
                    ("uW", "μW"),
                    ("mW", "mW"),
                    ("kW", "kW"),
                    ("MW", "MW"),
                    ("Other", "Other"),
                ],
                default=None,
                max_length=5,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="supply_voltage",
            field=models.DecimalField(
                blank=True, decimal_places=3, default=None, max_digits=7, null=True
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="supply_voltage_units",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "-----"),
                    ("V", "V"),
                    ("uV", "μV"),
                    ("mV", "mV"),
                    ("kV", "kV"),
                    ("MV", "MV"),
                    ("Other", "Other"),
                ],
                default=None,
                max_length=5,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="temperature_rating",
            field=models.DecimalField(
                blank=True, decimal_places=3, default=None, max_digits=7, null=True
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="temperature_rating_units",
            field=models.CharField(
                blank=True,
                choices=[("", "-----"), ("C", "°C"), ("F", "°F"), ("Other", "Other")],
                default=None,
                max_length=5,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="tolerance",
            field=models.CharField(
                blank=True,
                default=None,
                max_length=6,
                null=True,
                validators=[bom.validators.validate_pct],
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="value_units",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "-----"),
                    ("Ohms", "Ω"),
                    ("mOhms", "mΩ"),
                    ("kOhms", "kΩ"),
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
                    ("Other", "Other"),
                ],
                default=None,
                max_length=5,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="voltage_rating",
            field=models.DecimalField(
                blank=True, decimal_places=3, default=None, max_digits=7, null=True
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="voltage_rating_units",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "-----"),
                    ("V", "V"),
                    ("uV", "μV"),
                    ("mV", "mV"),
                    ("kV", "kV"),
                    ("MV", "MV"),
                    ("Other", "Other"),
                ],
                default=None,
                max_length=2,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="wavelength",
            field=models.DecimalField(
                blank=True, decimal_places=3, default=None, max_digits=7, null=True
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="wavelength_units",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "-----"),
                    ("km", "km"),
                    ("m", "m"),
                    ("cm", "cm"),
                    ("um", "μm"),
                    ("nm", "nm"),
                    ("A", "A"),
                    ("Other", "Other"),
                ],
                default=None,
                max_length=5,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="weight",
            field=models.DecimalField(
                blank=True, decimal_places=3, default=None, max_digits=7, null=True
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="weight_units",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "-----"),
                    ("mg", "mg"),
                    ("g", "g"),
                    ("kg", "kg"),
                    ("oz", "oz"),
                    ("lb", "lb"),
                    ("Other", "Other"),
                ],
                default=None,
                max_length=5,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="width",
            field=models.DecimalField(
                blank=True, decimal_places=3, default=None, max_digits=7, null=True
            ),
        ),
        migrations.AddField(
            model_name="partrevision",
            name="width_units",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "-----"),
                    ("mil", "mil"),
                    ("in", "in"),
                    ("ft", "ft"),
                    ("yd", "yd"),
                    ("km", "km"),
                    ("m", "m"),
                    ("cm", "cm"),
                    ("um", "um"),
                    ("nm", "nm"),
                    ("Other", "Other"),
                ],
                default=None,
                max_length=5,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="subpart",
            name="do_not_load",
            field=models.BooleanField(default=False, verbose_name="Do Not Load"),
        ),
        migrations.AlterField(
            model_name="part",
            name="number_item",
            field=models.CharField(
                blank=True,
                default=None,
                max_length=10,
                validators=[
                    django.core.validators.RegexValidator(
                        "^[0-9]*$", "Only numeric characters are allowed."
                    )
                ],
            ),
        ),
        migrations.AlterField(
            model_name="partclass",
            name="code",
            field=models.CharField(max_length=3),
        ),
        migrations.AlterField(
            model_name="partrevision",
            name="description",
            field=models.CharField(blank=True, default="", max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="partrevision",
            name="revision",
            field=models.CharField(db_index=True, default="1", max_length=4),
        ),
        migrations.AlterField(
            model_name="sellerpart",
            name="lead_time_days",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sellerpart",
            name="minimum_order_quantity",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AlterField(
            model_name="sellerpart",
            name="minimum_pack_quantity",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AlterField(
            model_name="subpart",
            name="count",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AlterUniqueTogether(
            name="partclass",
            unique_together={("code", "name", "organization")},
        ),
        migrations.RunPython(update_part_classes),
    ]

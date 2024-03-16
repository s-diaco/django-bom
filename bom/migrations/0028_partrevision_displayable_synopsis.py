# Generated by Django 2.2.8 on 2019-12-23 18:00

from django.db import migrations, models
from bom.utils import strip_trailing_zeros


def synopsis(pr, make_searchable=False):
    self = pr

    def verbosify(
        val, units=None, pre=None, pre_whitespace=True, post=None, post_whitespace=True
    ):
        elaborated = ""
        if val is not None and val != "":
            try:
                elaborated = strip_trailing_zeros(str(val))
                if units is not None and units != "":
                    elaborated += units
                if pre is not None and pre != "":
                    elaborated = pre + (" " if pre_whitespace else "") + elaborated
                if post is not None and post != "":
                    elaborated += (" " if post_whitespace else "") + post
                elaborated = elaborated + " "
            except ValueError:
                pass
        return elaborated

    s = ""
    s += verbosify(
        self.value,
        units=self.value_units if make_searchable else self.get_value_units_display(),
    )
    s += verbosify(self.description)
    tolerance = self.tolerance.replace("%", "") if self.tolerance else ""
    s += verbosify(tolerance, post="%", post_whitespace=False)
    s += verbosify(self.attribute)
    s += verbosify(self.package if make_searchable else self.get_package_display())
    s += verbosify(self.pin_count, post="pins")
    s += verbosify(
        self.frequency,
        units=self.frequency_units
        if make_searchable
        else self.get_frequency_units_display(),
    )
    s += verbosify(
        self.wavelength,
        units=self.wavelength_units
        if make_searchable
        else self.get_wavelength_units_display(),
    )
    s += verbosify(
        self.memory,
        units=self.memory_units if make_searchable else self.get_memory_units_display(),
    )
    s += verbosify(self.interface if make_searchable else self.get_interface_display())
    s += verbosify(
        self.supply_voltage,
        units=self.supply_voltage_units
        if make_searchable
        else self.get_supply_voltage_units_display(),
        post="supply",
    )
    s += verbosify(
        self.temperature_rating,
        units=self.temperature_rating_units
        if make_searchable
        else self.get_temperature_rating_units_display(),
        post="rating",
    )
    s += verbosify(
        self.power_rating,
        units=self.power_rating_units
        if make_searchable
        else self.get_power_rating_units_display(),
        post="rating",
    )
    s += verbosify(
        self.voltage_rating,
        units=self.voltage_rating_units
        if make_searchable
        else self.get_voltage_rating_units_display(),
        post="rating",
    )
    s += verbosify(
        self.current_rating,
        units=self.current_rating_units
        if make_searchable
        else self.get_current_rating_units_display(),
        post="rating",
    )
    s += verbosify(self.material)
    s += verbosify(self.color)
    s += verbosify(self.finish)
    s += verbosify(
        self.length,
        units=self.length_units if make_searchable else self.get_length_units_display(),
        pre="L",
    )
    s += verbosify(
        self.width,
        units=self.width_units if make_searchable else self.get_width_units_display(),
        pre="W",
    )
    s += verbosify(
        self.height,
        units=self.height_units if make_searchable else self.get_height_units_display(),
        pre="H",
    )
    s += verbosify(
        self.weight,
        units=self.weight_units if make_searchable else self.get_weight_units_display(),
    )
    return s


def update_part_revisions(apps, schema_editor):
    PartRevision = apps.get_model("bom", "PartRevision")
    for pr in PartRevision.objects.all():
        try:
            pr.displayable_synopsis = synopsis(pr, False)
            pr.save()
        except ValueError:
            pr.displayable_synopsis = pr.description
            pr.save()
            pass


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0027_auto_20191222_2347"),
    ]

    operations = [
        migrations.AddField(
            model_name="partrevision",
            name="displayable_synopsis",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                editable=False,
                max_length=255,
                null=True,
            ),
        ),
        migrations.RunPython(update_part_revisions),
    ]

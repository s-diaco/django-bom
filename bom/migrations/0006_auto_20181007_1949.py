# Generated by Django 2.1.1 on 2018-10-07 19:49

from django.db import migrations, models
import django.db.models.deletion


def update_primary_manufacturer_part(apps, schema_editor):
    Part = apps.get_model('bom', 'Part')
    ManufacturerPart = apps.get_model('bom', 'ManufacturerPart')

    for p in Part.objects.all():
        p.primary_manufacturer_part = ManufacturerPart.objects.filter(part=p)[0]
        p.save()


class Migration(migrations.Migration):

    dependencies = [
        ('bom', '0005_auto_20181007_1934'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='part',
            name='manufacturer',
        ),
        migrations.RemoveField(
            model_name='part',
            name='manufacturer_part_number',
        ),
        migrations.RemoveField(
            model_name='sellerpart',
            name='part',
        ),
        migrations.AddField(
            model_name='part',
            name='primary_manufacturer_part',
            field=models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='primary_manufacturer_part', to='bom.ManufacturerPart'),
        ),
        migrations.RunPython(update_primary_manufacturer_part),
    ]
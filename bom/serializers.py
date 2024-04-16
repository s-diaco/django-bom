from rest_framework import serializers
from bom.models import (
    Assembly,
    AssemblySubparts,
    Manufacturer,
    ManufacturerPart,
    Part,
    PartClass,
    PartRevision,
    SellerPart,
    Subpart,
    User,
    UserMeta,
)


class SellerPartSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerPart
        exclude = [
            "manufacturer_part",
            "data_source",
            "minimum_order_quantity",
            "minimum_pack_quantity",
            "lead_time_days",
            "ncnr",
            "link",
            "nre_cost",
        ]

    field_order = [
        "seller",
        "unit_cost",
    ]

from django.contrib.auth import get_user_model
from rest_framework import serializers

from bom.models import Organization, PartRevision, UserMeta

User = get_user_model()


class OrganizationSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "subscription",
            "currency",
            "number_scheme",
        ]


class UserMetaSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    organization = OrganizationSummarySerializer(read_only=True)
    is_google_authenticated = serializers.SerializerMethodField()

    class Meta:
        model = UserMeta
        fields = [
            "role",
            "role_display",
            "organization",
            "is_google_authenticated",
        ]

    def get_is_google_authenticated(self, obj):
        return obj.google_authenticated()


class MeSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_active",
            "profile",
        ]

    def get_profile(self, obj):
        profile = (
            UserMeta.objects.select_related("organization").filter(user=obj).first()
        )
        if profile is None:
            return None
        return UserMetaSerializer(profile).data


class PartClassSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()


class PartListRowSerializer(serializers.ModelSerializer):
    part_id = serializers.IntegerField(source="part.id", read_only=True)
    part_number = serializers.SerializerMethodField()
    part_class = serializers.SerializerMethodField()
    synopsis = serializers.CharField(source="searchable_synopsis", read_only=True)
    primary_manufacturer_name = serializers.SerializerMethodField()
    primary_manufacturer_part_number = serializers.SerializerMethodField()

    class Meta:
        model = PartRevision
        fields = [
            "id",
            "part_id",
            "part_number",
            "part_class",
            "revision",
            "description",
            "synopsis",
            "material",
            "primary_manufacturer_name",
            "primary_manufacturer_part_number",
        ]

    def get_part_number(self, obj):
        return obj.part.full_part_number()

    def get_part_class(self, obj):
        part_class = obj.part.number_class
        if part_class is None:
            return None
        return PartClassSummarySerializer(part_class).data

    def get_primary_manufacturer_name(self, obj):
        primary = obj.part.primary_manufacturer_part
        if primary is None or primary.manufacturer is None:
            return ""
        return primary.manufacturer.name

    def get_primary_manufacturer_part_number(self, obj):
        primary = obj.part.primary_manufacturer_part
        if primary is None:
            return ""
        return primary.manufacturer_part_number


class PartDetailSerializer(serializers.ModelSerializer):
    part_id = serializers.IntegerField(source="part.id", read_only=True)
    part_number = serializers.SerializerMethodField()
    part_class = serializers.SerializerMethodField()
    synopsis = serializers.CharField(source="searchable_synopsis", read_only=True)
    primary_manufacturer_name = serializers.SerializerMethodField()
    primary_manufacturer_part_number = serializers.SerializerMethodField()

    class Meta:
        model = PartRevision
        fields = [
            "id",
            "part_id",
            "part_number",
            "part_class",
            "revision",
            "timestamp",
            "configuration",
            "description",
            "synopsis",
            "material",
            "primary_manufacturer_name",
            "primary_manufacturer_part_number",
        ]

    def get_part_number(self, obj):
        return obj.part.full_part_number()

    def get_part_class(self, obj):
        part_class = obj.part.number_class
        if part_class is None:
            return None
        return PartClassSummarySerializer(part_class).data

    def get_primary_manufacturer_name(self, obj):
        primary = obj.part.primary_manufacturer_part
        if primary is None or primary.manufacturer is None:
            return ""
        return primary.manufacturer.name

    def get_primary_manufacturer_part_number(self, obj):
        primary = obj.part.primary_manufacturer_part
        if primary is None:
            return ""
        return primary.manufacturer_part_number

from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from bom.birthday import format_birthday_md, parse_birthday_input

from .models import (
    Assembly,
    Customer,
    CustomerPrice,
    Manufacturer,
    ManufacturerPart,
    Organization,
    Part,
    PartClass,
    PartRevision,
    ProductType,
    Seller,
    SellerPart,
    Subpart,
    UserMeta,
)


User = get_user_model()


class UserMetaAdminForm(forms.ModelForm):
    """Admin-only birthday entry: Gregorian or Jalali date → month/day stored."""

    birthday = forms.CharField(
        required=False,
        label="Birthday (surprise)",
        help_text=(
            "Gregorian or Jalali YYYY/MM/DD (year used only to interpret the "
            "calendar; Jalali keeps Jalali month/day), or MM/DD Gregorian. "
            "Leave blank to clear. Hidden from users."
        ),
    )

    class Meta:
        model = UserMeta
        fields = (
            "organization",
            "role",
            "calendar",
            "language",
            "birthday",
            "systemgroup_username",
            "systemgroup_password",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["birthday"].initial = format_birthday_md(
                self.instance.birthday_month,
                self.instance.birthday_day,
                self.instance.birthday_jalali,
            )

    def clean_birthday(self):
        # Bound forms that omit this key leave the stored birthday alone.
        # Use add_prefix so User admin TabularInline (usermeta_set-0-birthday) works.
        if self.is_bound and self.add_prefix("birthday") not in self.data:
            return "__unchanged__"
        return parse_birthday_input(self.cleaned_data.get("birthday"))

    def save(self, commit=True):
        instance = super().save(commit=False)
        parsed = self.cleaned_data.get("birthday")
        if parsed != "__unchanged__":
            if parsed is None:
                instance.birthday_month = None
                instance.birthday_day = None
                instance.birthday_jalali = False
            else:
                instance.birthday_month = parsed.month
                instance.birthday_day = parsed.day
                instance.birthday_jalali = parsed.jalali
        if commit:
            instance.save()
        return instance


class UserMetaInline(admin.TabularInline):
    model = UserMeta
    form = UserMetaAdminForm
    fields = (
        "organization",
        "role",
        "calendar",
        "language",
        "birthday",
    )
    raw_id_fields = ("organization",)
    can_delete = False
    extra = 0


class UserAdmin(UserAdmin):
    inlines = (UserMetaInline,)


class UserMetaAdmin(admin.ModelAdmin):
    form = UserMetaAdminForm
    list_display = (
        "user",
        "organization",
        "role",
        "birthday_display",
        "calendar",
        "language",
    )
    list_filter = ("role", "calendar", "language")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name")
    raw_id_fields = ("user", "organization")
    fields = (
        "user",
        "organization",
        "role",
        "calendar",
        "language",
        "birthday",
        "systemgroup_username",
        "systemgroup_password",
    )

    @admin.display(description="Birthday")
    def birthday_display(self, obj):
        return (
            format_birthday_md(
                obj.birthday_month, obj.birthday_day, obj.birthday_jalali
            )
            or "—"
        )


class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name",)


class SubpartInline(admin.TabularInline):
    model = Subpart
    fk_name = "part_revision"
    raw_id_fields = ("part_revision",)
    # readonly_fields = ('get_full_part_number', )
    #
    # def get_full_part_number(self, obj):
    #     return obj.assembly_subpart.part.full_part_number()
    # get_full_part_number.short_description = 'PartNumber'


class SellerAdmin(admin.ModelAdmin):
    list_display = ("name",)


class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "code",
        "is_active",
    )
    list_filter = ("is_active", "organization")
    search_fields = ("name", "code", "contact_name", "email")


class CustomerPriceAdmin(admin.ModelAdmin):
    list_display = (
        "customer",
        "part",
        "quantity",
        "base_cost",
        "profit_percent",
        "price",
        "is_manual_price",
        "created_at",
    )
    list_filter = ("is_manual_price", "customer__organization")
    raw_id_fields = ("customer", "part", "part_revision", "created_by")
    readonly_fields = ("created_at",)


class SellerPartAdmin(admin.ModelAdmin):
    list_display = (
        "manufacturer_part",
        "seller",
        "seller_part_number",
        "minimum_order_quantity",
        "minimum_pack_quantity",
        "unit_cost",
        "shipping",
        "customs_duty_percent",
        "lead_time_days",
        "nre_cost",
        "ncnr",
    )


class SellerPartAdminInline(admin.TabularInline):
    model = SellerPart
    raw_id_fields = (
        "seller",
        "manufacturer_part",
    )


class ManufacturerPartAdmin(admin.ModelAdmin):
    list_display = (
        "manufacturer_part_number",
        "manufacturer",
        "part",
    )
    raw_id_fields = (
        "manufacturer",
        "part",
    )
    inlines = [
        SellerPartAdminInline,
    ]


class ManufacturerPartAdminInline(admin.TabularInline):
    model = ManufacturerPart
    raw_id_fields = (
        "part",
        "manufacturer",
    )


class ProductTypeAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "code",
        "name",
        "has_bom",
        "apply_loi",
        "overhead",
    )
    list_filter = ("has_bom", "apply_loi", "organization")


class PartClassAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "comment",
    )


class PartRevisionAdminInline(admin.TabularInline):
    model = PartRevision
    raw_id_fields = ("assembly",)


class PartAdmin(admin.ModelAdmin):
    ordering = ("organization", "number_class__code", "number_item", "number_variation")
    readonly_fields = ("get_full_part_number",)
    list_display = (
        "organization",
        "get_full_part_number",
    )
    raw_id_fields = (
        "number_class",
        "primary_manufacturer_part",
    )
    inlines = [
        ManufacturerPartAdminInline,
    ]

    def get_full_part_number(self, obj):
        return obj.full_part_number()

    get_full_part_number.short_description = "PartNumber"
    get_full_part_number.admin_order_field = "number_class__part_number"


class PartRevisionAdmin(admin.ModelAdmin):
    list_display = (
        "part",
        "revision",
        "description",
        "get_assembly_size",
        "timestamp",
    )
    raw_id_fields = ("assembly",)
    readonly_fields = ("timestamp",)

    def get_assembly_size(self, obj):
        return None if obj.assembly is None else obj.assembly.subparts.count()

    get_assembly_size.short_description = "AssemblySize"


class ManufacturerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
    )


class SubpartAdmin(admin.ModelAdmin):
    list_display = (
        "part_revision",
        "count",
        "reference",
    )


class SubpartsInline(admin.TabularInline):
    model = Assembly.subparts.through
    raw_id_fields = ("subpart",)


class AssemblyAdmin(admin.ModelAdmin):
    list_display = ("id",)
    exclude = ("subparts",)
    inlines = [
        SubpartsInline,
    ]


# Try to unregister User model
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

admin.site.register(User, UserAdmin)
admin.site.register(UserMeta, UserMetaAdmin)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Seller, SellerAdmin)
admin.site.register(SellerPart, SellerPartAdmin)
admin.site.register(Customer, CustomerAdmin)
admin.site.register(CustomerPrice, CustomerPriceAdmin)
admin.site.register(ManufacturerPart, ManufacturerPartAdmin)
admin.site.register(ProductType, ProductTypeAdmin)
admin.site.register(PartClass, PartClassAdmin)
admin.site.register(Part, PartAdmin)
admin.site.register(PartRevision, PartRevisionAdmin)
admin.site.register(Manufacturer, ManufacturerAdmin)
admin.site.register(Assembly, AssemblyAdmin)
admin.site.register(Subpart, SubpartAdmin)

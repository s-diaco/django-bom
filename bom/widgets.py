"""Custom form widgets for Lithium BoM."""

from django.forms.widgets import RadioSelect
from django.utils.translation import gettext as _


class MaterialTypePicker(RadioSelect):
    """Compact Product / Raw kind toggle + subtype radios for material codes.

    Still posts the ProductType ``code`` via ``name=material`` radios so create-part
    toggles and model validation stay unchanged.
    """

    template_name = "bom/widgets/material_type_picker.html"
    option_template_name = "bom/widgets/material_type_option.html"

    def __init__(self, attrs=None, choices=(), *, raw_codes=None):
        self.raw_codes = {str(c) for c in (raw_codes or ())}
        super().__init__(attrs, choices)

    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        code = "" if value is None else str(value)
        kind = "raw" if code in self.raw_codes else "product"
        option["kind"] = kind
        option["attrs"]["data-kind"] = kind
        return option

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        selected = "" if value is None else str(value)
        selected_kind = "raw" if selected in self.raw_codes else "product"
        if not selected:
            # Match PartRevisionForm initial: prefer first raw when unset.
            selected_kind = "raw" if self.raw_codes else "product"
        context["widget"]["selected_kind"] = selected_kind
        context["widget"]["product_label"] = _("Product")
        context["widget"]["raw_label"] = _("Raw Material")
        return context

"""Admin UI form for SystemGroup BoM import."""

from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from .client import extract_bom_id_from_url


class SystemGroupBomImportForm(forms.Form):
    bom_id = forms.CharField(
        required=False,
        label=_("CRM BoM id"),
        help_text=_("SystemGroup Edit.aspx?id=… value, e.g. 39477."),
        widget=forms.TextInput(attrs={"placeholder": "39477", "autocomplete": "off"}),
    )
    crm_url = forms.CharField(
        required=False,
        label=_("CRM BoM URL"),
        help_text=_(
            "Optional. Paste a Shell/Edit URL; the BoM id is extracted if bom id is blank."
        ),
        widget=forms.TextInput(
            attrs={
                "placeholder": "Shell.aspx?page=PAC/Engineering/BomPages/Edit.aspx?id=39477",
                "autocomplete": "off",
                "class": "bom-input w-full",
            }
        ),
    )
    parent_part_number = forms.CharField(
        required=False,
        label=_("Parent part number"),
        help_text=_(
            "Optional Lithium parent. If blank, uses the CRM header part number "
            "(creates part+revision when missing)."
        ),
    )
    source_file = forms.FileField(
        required=False,
        label=_("Saved Edit HTML/JSON"),
        help_text=_(
            "Optional offline import. Skips CRM network when provided. "
            "Live fetch uses CRM_BASE_URL / CRM_USERNAME / CRM_PASSWORD from the server env."
        ),
    )
    dry_run = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Dry run (parse only, no database writes)"),
    )

    def clean(self):
        cleaned = super().clean()
        bom_id = (cleaned.get("bom_id") or "").strip()
        crm_url = (cleaned.get("crm_url") or "").strip()
        source_file = cleaned.get("source_file")

        extracted = extract_bom_id_from_url(crm_url) if crm_url else None
        if not bom_id and extracted:
            bom_id = extracted
            cleaned["bom_id"] = bom_id

        if not source_file and not bom_id:
            raise forms.ValidationError(
                _(
                    "Enter a CRM BoM id, paste a CRM Edit URL containing id=, "
                    "or upload a saved HTML/JSON file."
                ),
                code="required",
            )
        cleaned["bom_id"] = bom_id or None
        cleaned["crm_url"] = crm_url or None
        return cleaned

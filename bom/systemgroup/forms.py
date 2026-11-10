"""Admin UI form for SystemGroup BoM import."""

from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from .client import extract_bom_id_from_url


class SystemGroupBomImportForm(forms.Form):
    bom_id = forms.CharField(
        required=False,
        label=_("CRM BoM id"),
        help_text=_(
            "Optional when a parent part number is set — the CRM BoM list is "
            "matched automatically. Still accepted as a manual fallback."
        ),
        widget=forms.TextInput(attrs={"placeholder": "39477", "autocomplete": "off"}),
    )
    crm_url = forms.CharField(
        required=False,
        label=_("CRM BoM URL"),
        help_text=_(
            "Optional fallback. Paste a Shell/Edit URL; the BoM id is extracted "
            "if bom id is blank."
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
            "Lithium parent. When set without a BoM id, the CRM list is searched "
            "by this part number (and description). Leave blank to browse the "
            "list or enter an id/URL manually."
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
    browse_list = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Browse CRM BoM list"),
        help_text=_(
            "Load the CRM BoM list so you can pick a row (useful without a parent part)."
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
        parent_pn = (cleaned.get("parent_part_number") or "").strip()
        browse_list = bool(cleaned.get("browse_list"))

        extracted = extract_bom_id_from_url(crm_url) if crm_url else None
        if not bom_id and extracted:
            bom_id = extracted
            cleaned["bom_id"] = bom_id

        if not source_file and not bom_id and not parent_pn and not browse_list:
            raise forms.ValidationError(
                _(
                    "Enter a parent part number (auto-resolve from CRM list), "
                    "a CRM BoM id / Edit URL, upload a saved HTML/JSON file, "
                    "or browse the CRM BoM list."
                ),
                code="required",
            )
        cleaned["bom_id"] = bom_id or None
        cleaned["crm_url"] = crm_url or None
        cleaned["parent_part_number"] = parent_pn or None
        return cleaned

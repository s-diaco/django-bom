"""Admin UI form for SystemGroup BoM import."""

from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from .client import extract_bom_id_from_url
from .parser import split_bom_code


class SystemGroupBomImportForm(forms.Form):
    part_id_revision = forms.CharField(
        required=False,
        label=_("Part ID + Revision"),
        help_text=_(
            "Paste part number and revision as PN/rev (e.g. 1155F229/A2*10-C). "
            "Matches CRM «کد BOM» and is used to find or create the Lithium "
            "part/revision, then pull that BoM from the CRM list."
        ),
        widget=forms.TextInput(
            attrs={
                "placeholder": "1155F229/A2*10-C",
                "autocomplete": "off",
                "class": "bom-input w-full",
            }
        ),
    )
    bom_id = forms.CharField(
        required=False,
        label=_("CRM BoM id"),
        help_text=_(
            "Optional when Part ID + Revision is set — the CRM BoM list is "
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
        help_text=_("Filled from Part ID + Revision when that field is used."),
        widget=forms.HiddenInput(),
    )
    parent_revision = forms.CharField(
        required=False,
        label=_("Parent revision"),
        help_text=_("Filled from Part ID + Revision when that field is used."),
        widget=forms.HiddenInput(),
    )
    source_file = forms.FileField(
        required=False,
        label=_("Saved Edit HTML/JSON"),
        help_text=_(
            "Optional offline import. Skips CRM network when provided. "
            "Live fetch uses your Settings → User credentials and CRM_BASE_URL."
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
    existing_bom_action = forms.ChoiceField(
        required=False,
        choices=(
            ("", ""),
            ("keep", "keep"),
            ("replace", "replace"),
        ),
        widget=forms.HiddenInput(),
    )

    def clean(self):
        cleaned = super().clean()
        bom_id = (cleaned.get("bom_id") or "").strip()
        crm_url = (cleaned.get("crm_url") or "").strip()
        source_file = cleaned.get("source_file")
        parent_pn = (cleaned.get("parent_part_number") or "").strip()
        parent_rev = (cleaned.get("parent_revision") or "").strip()
        part_id_rev = (cleaned.get("part_id_revision") or "").strip()
        browse_list = bool(cleaned.get("browse_list"))
        existing_bom_action = (cleaned.get("existing_bom_action") or "").strip()

        if part_id_rev:
            code_pn, code_rev = split_bom_code(part_id_rev)
            if not code_pn:
                raise forms.ValidationError(
                    _("Part ID + Revision must include a part number."),
                    code="invalid",
                )
            parent_pn = code_pn
            if code_rev:
                parent_rev = code_rev
            cleaned["part_id_revision"] = part_id_rev

        extracted = extract_bom_id_from_url(crm_url) if crm_url else None
        if not bom_id and extracted:
            bom_id = extracted
            cleaned["bom_id"] = bom_id

        if not source_file and not bom_id and not parent_pn and not browse_list:
            raise forms.ValidationError(
                _(
                    "Enter Part ID + Revision (e.g. 1155F229/A2*10-C), "
                    "a CRM BoM id / Edit URL, upload a saved HTML/JSON file, "
                    "or browse the CRM BoM list."
                ),
                code="required",
            )
        cleaned["bom_id"] = bom_id or None
        cleaned["crm_url"] = crm_url or None
        cleaned["parent_part_number"] = parent_pn or None
        cleaned["parent_revision"] = parent_rev or None
        cleaned["existing_bom_action"] = existing_bom_action or None
        return cleaned

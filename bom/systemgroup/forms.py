"""Admin UI form for SystemGroup BoM import."""

from __future__ import annotations

from django import forms
from django.utils.translation import gettext, gettext_lazy as _

from .client import extract_bom_id_from_url
from .parser import split_bom_code


class SystemGroupLoginForm(forms.Form):
    """CRM username/password for SystemGroup login (stored on UserMeta)."""

    systemgroup_username = forms.CharField(
        required=True,
        label=_("SystemGroup username"),
        widget=forms.TextInput(
            attrs={
                "autocomplete": "username",
                "class": "bom-input w-full",
            }
        ),
    )
    systemgroup_password = forms.CharField(
        required=True,
        label=_("SystemGroup password"),
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "class": "bom-input w-full",
            }
        ),
    )


class SystemGroupBomImportForm(forms.Form):
    part_id = forms.CharField(
        required=False,
        label=_("Part ID"),
        widget=forms.TextInput(
            attrs={
                "placeholder": "1155F229 or 1155F229/A2*10-C",
                "autocomplete": "off",
                "class": "bom-input w-full",
                "dir": "ltr",
            }
        ),
    )
    bom_id = forms.CharField(
        required=False,
        label=_("CRM BoM id"),
        help_text=_(
            "Optional when Part ID is set. Still accepted as a manual fallback."
        ),
        widget=forms.TextInput(
            attrs={
                "placeholder": "39477",
                "autocomplete": "off",
                "class": "bom-input w-full",
                "dir": "ltr",
            }
        ),
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
                "dir": "ltr",
            }
        ),
    )
    parent_part_number = forms.CharField(
        required=False,
        label=_("Parent part number"),
        help_text=_("Filled from Part ID or revision pick."),
        widget=forms.HiddenInput(),
    )
    parent_revision = forms.CharField(
        required=False,
        label=_("Parent revision"),
        help_text=_("Filled from the selected CRM revision."),
        widget=forms.HiddenInput(),
    )
    source_file = forms.FileField(
        required=False,
        label=_("Saved Edit HTML/JSON"),
        help_text=_(
            "Optional offline import. Skips CRM network when provided. "
            "Live fetch uses your SystemGroup login and the "
            "organization CRM base URL."
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
    material = forms.ChoiceField(
        required=False,
        label=_("Material Type"),
        help_text=_(
            "Used for the parent part when it is created. "
            "New child parts use the first raw-material type "
            "(has BoM off). Existing parts keep their current type."
        ),
        widget=forms.Select(attrs={"class": "bom-input w-full"}),
    )

    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
        types = []
        if organization is not None:
            organization.ensure_default_product_types()
            types = list(organization.product_types.all())
        self.fields["material"].choices = [("", _("Select material type…"))] + [
            (pt.code, gettext(pt.name)) for pt in types
        ]

    def clean(self):
        cleaned = super().clean()
        bom_id = (cleaned.get("bom_id") or "").strip()
        crm_url = (cleaned.get("crm_url") or "").strip()
        source_file = cleaned.get("source_file")
        parent_pn = (cleaned.get("parent_part_number") or "").strip()
        parent_rev = (cleaned.get("parent_revision") or "").strip()
        part_id = (cleaned.get("part_id") or "").strip()
        browse_list = bool(cleaned.get("browse_list"))
        existing_bom_action = (cleaned.get("existing_bom_action") or "").strip()
        material = (cleaned.get("material") or "").strip()
        # Submit button names are not form fields; read from data.
        load_revisions = bool(
            self.data.get("load_revisions") if hasattr(self, "data") else False
        )

        valid_codes = {c for c, _ in self.fields["material"].choices if c}
        if material and valid_codes and material not in valid_codes:
            raise forms.ValidationError(_("Unknown material."), code="invalid")
        if not material and valid_codes:
            raise forms.ValidationError(
                _("Select a Material Type."),
                code="required",
            )

        # Load revisions: keep the full StartsWith query (do not strip at /).
        # Never treat a slash in Part ID as a one-shot PN/rev import.
        search_query = part_id
        if load_revisions:
            if not part_id and not parent_pn:
                raise forms.ValidationError(
                    _("Enter a Part ID to load CRM revisions."),
                    code="required",
                )
            search_query = part_id or parent_pn
            if part_id and not parent_pn:
                code_pn, _code_rev = split_bom_code(part_id)
                parent_pn = code_pn or part_id
        elif part_id and not parent_pn:
            code_pn, _code_rev = split_bom_code(part_id)
            parent_pn = code_pn or part_id
            part_id = parent_pn

        extracted = extract_bom_id_from_url(crm_url) if crm_url else None
        if not bom_id and extracted:
            bom_id = extracted
            cleaned["bom_id"] = bom_id

        if (
            not load_revisions
            and not source_file
            and not bom_id
            and not browse_list
        ):
            raise forms.ValidationError(
                _(
                    "Enter a Part ID then Load revisions, "
                    "or use More options (a CRM BoM id / Edit URL, "
                    "a saved HTML/JSON file, or browse the CRM BoM list)."
                ),
                code="required",
            )
        cleaned["bom_id"] = bom_id or None
        cleaned["crm_url"] = crm_url or None
        cleaned["part_id"] = (search_query if load_revisions else part_id) or None
        cleaned["parent_part_number"] = parent_pn or None
        cleaned["parent_revision"] = parent_rev or None
        cleaned["existing_bom_action"] = existing_bom_action or None
        cleaned["material"] = material or None
        cleaned["load_revisions"] = load_revisions
        return cleaned

from django.conf import settings

from bom.utils import get_project_version  # import the settings file


def bom_config(request):
    base_template = "bom/base.html"
    if settings.BOM_CONFIG:
        if "base_template" in settings.BOM_CONFIG:
            base_template = settings.BOM_CONFIG["base_template"]
    return {"BASE_TEMPLATE": base_template}


def project_version(request):
    return {"project_version": get_project_version()}

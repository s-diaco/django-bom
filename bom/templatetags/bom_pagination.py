from django import template

from bom.list_queries import PAGE_SIZE_CHOICES, build_querystring

register = template.Library()


@register.simple_tag
def page_size_choices():
    return PAGE_SIZE_CHOICES


@register.simple_tag(takes_context=True)
def querystring_except(context, *keys):
    return build_querystring(context["request"], *keys)


@register.simple_tag
def elided_page_range(page_obj, on_each_side=3, on_ends=2):
    return page_obj.paginator.get_elided_page_range(
        page_obj.number,
        on_each_side=on_each_side,
        on_ends=on_ends,
    )

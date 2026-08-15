from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Max, Prefetch, Subquery, prefetch_related_objects

from bom.models import ManufacturerPart, PartRevision, SellerPart

LIST_PAGE_ORDER = (
    "part__number_class__code",
    "part__number_item",
    "part__number_variation",
)
LIST_PAGE_SELLER_QUANTITY = 100
LIST_PAGE_SELECT_RELATED = (
    "part",
    "part__organization",
    "part__number_class",
    "part__primary_manufacturer_part",
)


def latest_part_revisions(parts):
    """Latest PartRevision per part. Groups by part_id before taking Max(id)."""
    latest_ids = (
        PartRevision.objects.filter(part__in=parts)
        .values("part_id")
        .annotate(max_id=Max("id"))
        .values("max_id")
    )
    return PartRevision.objects.filter(id__in=Subquery(latest_ids)).order_by(
        *LIST_PAGE_ORDER
    )


def prepare_part_revs_for_list_page(
    part_revs_page, quantity=LIST_PAGE_SELLER_QUANTITY
):
    """Prefetch seller data and attach one optimal_seller per part on a page."""
    object_list = list(part_revs_page.object_list)
    part_revs_page.object_list = object_list
    if not object_list:
        return part_revs_page

    sellerpart_qs = SellerPart.objects.select_related("seller")
    manufacturer_qs = ManufacturerPart.objects.select_related(
        "manufacturer"
    ).prefetch_related(Prefetch("sellerpart_set", queryset=sellerpart_qs))
    prefetch_related_objects(
        object_list,
        Prefetch("part__manufacturerpart_set", queryset=manufacturer_qs),
    )

    seen = {}
    for part_rev in object_list:
        part = part_rev.part
        if part.pk in seen:
            part._optimal_seller_result = seen[part.pk]
            part._optimal_seller_qty = quantity
            continue
        sellerparts = []
        for manufacturer_part in part.manufacturerpart_set.all():
            sellerparts.extend(manufacturer_part.sellerpart_set.all())
        seller = SellerPart.optimal(sellerparts, quantity)
        part._optimal_seller_result = seller
        part._optimal_seller_qty = quantity
        seen[part.pk] = seller
    return part_revs_page


def paginate_part_revs(request, part_revs, page_size):
    part_revs = part_revs.select_related(*LIST_PAGE_SELECT_RELATED)
    paginator = Paginator(part_revs, page_size)
    page = request.GET.get("page")
    try:
        part_revs = paginator.page(page)
    except PageNotAnInteger:
        part_revs = paginator.page(1)
    except EmptyPage:
        part_revs = paginator.page(paginator.num_pages)
    return prepare_part_revs_for_list_page(part_revs)

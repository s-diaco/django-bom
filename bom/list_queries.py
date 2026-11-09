from urllib.parse import urlencode

from django.conf import settings
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Max, Prefetch, Subquery, prefetch_related_objects

from bom.models import ManufacturerPart, PartRevision, SellerPart, Subpart


def latest_part_revision_ids(part_ids):
    """Subquery of max PartRevision.id per part — same rule as Part.latest()."""
    return Subquery(
        PartRevision.objects.filter(part_id__in=part_ids)
        .values("part_id")
        .annotate(max_id=Max("id"))
        .values("max_id")
    )

PAGE_SIZE_CHOICES = (10, 25, 50, 100)

LIST_PAGE_SELLER_QUANTITY = 100
LIST_PAGE_SELECT_RELATED = (
    "part",
    "part__organization",
    "part__number_class",
    "part__primary_manufacturer_part",
)

_BOM_SUBPART_SELECT_RELATED = (
    "part_revision__part__organization",
    "part_revision__part__number_class",
    "part_revision__part__primary_manufacturer_part",
    "part_revision__assembly",
)


def get_list_page_size():
    return settings.BOM_CONFIG.get("admin_dashboard", {}).get("page_size", 25)


def resolve_page_size(request):
    default = get_list_page_size()
    raw = request.GET.get("per_page")
    if raw is None:
        return default
    try:
        size = int(raw)
    except (TypeError, ValueError):
        return default
    if size in PAGE_SIZE_CHOICES:
        return size
    return default


def build_querystring(request, *exclude):
    query_params = request.GET.copy()
    for key in exclude:
        query_params.pop(key, None)
    return urlencode(query_params)


def querystring_except_page(request, *exclude):
    return build_querystring(request, "page", *exclude)


def querystring_for_per_page(request, *exclude):
    return build_querystring(request, "page", "per_page", *exclude)


def paginate_queryset(request, queryset, *, per_page=None):
    page_size = per_page if per_page is not None else resolve_page_size(request)
    paginator = Paginator(queryset, page_size)
    page = request.GET.get("page")
    try:
        return paginator.page(page)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


def _seller_nested_prefetch():
    sellerpart_qs = SellerPart.objects.select_related("seller")
    return Prefetch(
        "part_revision__part__manufacturerpart_set",
        queryset=ManufacturerPart.objects.prefetch_related(
            Prefetch("sellerpart_set", queryset=sellerpart_qs)
        ),
    )


def prefetch_bom_graphs(part_revisions):
    """BFS-prefetch assembly→subparts (+ nested sellers) for indented walks.

    Loads one BOM depth per query wave so ``_bom_walk_subparts`` / ``indented``
    can reuse the prefetch cache instead of querying per assembly node.
    """
    frontier = [pr for pr in part_revisions if pr.assembly_id is not None]
    seen_assembly_ids = set()
    subpart_qs = Subpart.objects.select_related(
        *_BOM_SUBPART_SELECT_RELATED
    ).prefetch_related(_seller_nested_prefetch())

    while frontier:
        to_prefetch = []
        for part_rev in frontier:
            if part_rev.assembly_id in seen_assembly_ids:
                continue
            seen_assembly_ids.add(part_rev.assembly_id)
            to_prefetch.append(part_rev)
        if not to_prefetch:
            break

        prefetch_related_objects(
            to_prefetch,
            Prefetch("assembly__subparts", queryset=subpart_qs),
        )

        next_frontier = []
        for part_rev in to_prefetch:
            for subpart in part_rev.assembly.subparts.all():
                child = subpart.part_revision
                if child is not None and child.assembly_id is not None:
                    next_frontier.append(child)
        frontier = next_frontier


def prepare_part_revs_for_list_page(
    part_revs_page,
    quantity=LIST_PAGE_SELLER_QUANTITY,
    *,
    attach_bom_costs=True,
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

    if attach_bom_costs:
        attach_list_unit_costs(part_revs_page)
    return part_revs_page


def paginate_part_revs(request, part_revs, page_size=None):
    page_size = page_size if page_size is not None else resolve_page_size(request)
    part_revs = part_revs.select_related(*LIST_PAGE_SELECT_RELATED)
    page_obj = paginate_queryset(request, part_revs, per_page=page_size)
    return prepare_part_revs_for_list_page(page_obj)


class UnpaginatedPartRevList:
    """Iterable stand-in for a Django Page when rendering the full list."""

    def __init__(self, object_list):
        self.object_list = object_list

    def has_other_pages(self):
        return False

    def __iter__(self):
        return iter(self.object_list)

    def __len__(self):
        return len(self.object_list)


def list_unit_cost(part_rev, *, rollup_bom=True):
    """Unit cost for list/print/export rows.

    Raw materials use the optimal seller cost (no BOM walk). Products use the
    rolled-up ``bom_unit_cost`` when ``rollup_bom`` is true.
    """
    if rollup_bom and part_rev.is_product:
        return part_rev.bom_unit_cost
    seller = part_rev.part.optimal_seller()
    return seller.unit_cost if seller else None


def attach_list_unit_costs(part_revs_page):
    """Prefetch page BoM graphs and attach ``list_unit_cost`` per row.

    Matches ``PartRevision.bom_unit_cost``: products = indented BoM + type
    overhead; raw materials = optimal seller landed unit cost.
    """
    products = [part_rev for part_rev in part_revs_page if part_rev.is_product]
    if products:
        prefetch_bom_graphs(products)

    for part_rev in part_revs_page:
        if part_rev.is_product:
            part_rev.list_unit_cost = part_rev.bom_unit_cost
        else:
            seller = part_rev.part.optimal_seller()
            part_rev.list_unit_cost = (
                seller.landed_unit_cost if seller else None
            )
    return part_revs_page


def prepare_all_part_revs_for_list_page(
    part_revs, quantity=LIST_PAGE_SELLER_QUANTITY
):
    """Prefetch seller data for every matching row (no pagination)."""
    part_revs = part_revs.select_related(*LIST_PAGE_SELECT_RELATED)
    page = prepare_part_revs_for_list_page(
        UnpaginatedPartRevList(part_revs), quantity
    )
    attach_print_unit_costs(page)
    return page


def prepare_part_revs_for_export(part_revs, quantity=LIST_PAGE_SELLER_QUANTITY):
    """Prefetch sellers and attach CSV/XLSX prices without BOM walks.

    ponytail: list export Price never calls ``indented()`` / ``bom_unit_cost``.
    That walk monopolized a 1-worker gunicorn on production
    (``/?download=1&format=csv`` → WORKER TIMEOUT → site unreachable on LAN).
    Uses seller unit_cost only. Rolled-up product cost stays on part detail /
    BOM CSV. Upgrade: Redis-cached rollup or async export if list CSV must
    show BOM prices.
    """
    part_revs = part_revs.select_related(*LIST_PAGE_SELECT_RELATED)
    page = prepare_part_revs_for_list_page(
        UnpaginatedPartRevList(part_revs),
        quantity,
        attach_bom_costs=False,
    )
    for part_rev in page:
        part_rev.print_unit_cost = list_unit_cost(part_rev, rollup_bom=False)
    return page


def attach_print_unit_costs(part_revs_page):
    """Set print_unit_cost without walking BOM trees for raw materials."""
    for part_rev in part_revs_page:
        part_rev.print_unit_cost = list_unit_cost(part_rev)
    return part_revs_page

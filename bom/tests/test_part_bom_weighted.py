from djmoney.money import Money

from bom.part_bom import PartBom, PartBomItem
from bom.part_bom_weighted import PartBomWeighted, PartBomWeightedItem


class MockOrg:
    currency = "USD"


class MockPart:
    def __init__(self, number_item="ROOT"):
        self.organization = MockOrg()
        self.number_item = number_item


class MockPartRevision:
    def __init__(self, part, applies_loi=False, is_product=False, tolerance=0):
        self.part = part
        self.applies_loi = applies_loi
        self.is_product = is_product
        self.tolerance = tolerance
        self.type_overhead = Money(0, "USD")


class MockSellerPart:
    def __init__(self, unit_cost, shipping=None, customs_duty_percent=0, nre_cost=None):
        self.unit_cost = unit_cost
        if shipping is not None:
            self.shipping = shipping
        elif unit_cost is not None:
            self.shipping = Money(0, unit_cost.currency)
        else:
            self.shipping = None
        self.customs_duty_percent = customs_duty_percent
        self.nre_cost = nre_cost if nre_cost is not None else Money(0, "USD")
        self.manufacturer_part = None

    @property
    def landed_unit_cost(self):
        from decimal import Decimal

        if self.unit_cost is None:
            return None
        duty = Decimal(self.customs_duty_percent or 0) / Decimal("100")
        shipping = self.shipping if self.shipping is not None else Money(0, self.unit_cost.currency)
        return self.unit_cost * (Decimal("1") + duty) + shipping

    def order_quantity(self, quantity):
        return quantity


def _make_item(
    bom_id,
    part,
    part_revision,
    quantity,
    indent_level,
    parent_id,
    parent_quantity,
    seller_part=None,
):
    return PartBomWeightedItem(
        bom_id=bom_id,
        part=part,
        part_revision=part_revision,
        do_not_load=False,
        references="",
        quantity=quantity,
        extended_quantity=quantity,
        seller_part=seller_part,
        indent_level=indent_level,
        parent_id=parent_id,
        subpart=None,
        parent_quantity=parent_quantity,
    )


def setup_bom(root_applies_loi=False):
    """Sample BOM: root + two children with seller costs."""
    root_part = MockPart("ROOT")
    child_part_a = MockPart("CHILD-A")
    child_part_b = MockPart("CHILD-B")

    root_rev = MockPartRevision(root_part, applies_loi=root_applies_loi)
    child_rev_a = MockPartRevision(child_part_a)
    child_rev_b = MockPartRevision(child_part_b)

    bom = PartBomWeighted(part_revision=root_rev, quantity=1)

    root = _make_item(
        bom_id=1,
        part=root_part,
        part_revision=root_rev,
        quantity=1,
        indent_level=0,
        parent_id=None,
        parent_quantity=1,
        seller_part=MockSellerPart(unit_cost=Money(100, "USD")),
    )
    child_1 = _make_item(
        bom_id=2,
        part=child_part_a,
        part_revision=child_rev_a,
        quantity=2,
        indent_level=1,
        parent_id=1,
        parent_quantity=1,
        seller_part=MockSellerPart(unit_cost=Money(50, "USD")),
    )
    child_2 = _make_item(
        bom_id=3,
        part=child_part_b,
        part_revision=child_rev_b,
        quantity=3,
        indent_level=1,
        parent_id=1,
        parent_quantity=1,
        seller_part=MockSellerPart(unit_cost=Money(30, "USD")),
    )

    bom.parts = {1: root, 2: child_1, 3: child_2}
    return bom


def test_update_as_weighted_bom_root():
    """Root early-return sets bom.unit_cost from the root item unit cost."""
    bom = setup_bom()
    root = bom.parts[1]

    bom.update_as_weighted_bom(root)

    assert bom.unit_cost == Money(100, "USD")


def test_update_as_weighted_bom_child_costs():
    """Updating one child rolls its cost into the parent."""
    bom = setup_bom()
    root = bom.parts[1]
    child_1 = bom.parts[2]

    bom.update_as_weighted_bom(child_1)

    # Both siblings are included whenever any child updates the parent.
    assert root.childs_quantity == 5  # 2 + 3
    assert root.childs_cost == Money(190, "USD")  # 2*50 + 3*30


def test_update_as_weighted_bom_parent_costs():
    """Parent childs_cost is the sum of both siblings' unit_cost * quantity."""
    bom = setup_bom()
    root = bom.parts[1]
    child_2 = bom.parts[3]

    bom.update_as_weighted_bom(child_2)

    assert root.childs_cost == Money(190, "USD")  # 100 + 90


def test_update_as_weighted_bom_with_loi():
    """LOI parent uses sintered_quantity for childs_product_quantity."""
    bom = setup_bom(root_applies_loi=True)
    root = bom.parts[1]
    child_1 = bom.parts[2]
    child_2 = bom.parts[3]

    child_1.sintered_quantity = 1.5
    child_2.sintered_quantity = 2.5

    bom.update_as_weighted_bom(child_2)

    assert root.childs_product_quantity == 4.0  # 1.5 + 2.5
    assert root.childs_cost == Money(190, "USD")  # cost still uses quantity


def test_update_as_weighted_bom_no_seller_part():
    """Leaf with no seller_part contributes 0 to parent cost."""
    bom = setup_bom()
    root = bom.parts[1]
    child_1 = bom.parts[2]

    child_1.seller_part = None
    bom.update_as_weighted_bom(child_1)

    # child_1 unit_cost is 0; child_2 still 3*30
    assert root.childs_cost == Money(90, "USD")


def test_weighted_missing_item_costs_no_seller_part():
    """Non-product leaf with no seller_part counts as Materials without price."""
    bom = setup_bom()
    child_1 = bom.parts[2]
    child_1.seller_part = None
    child_1.total_extended_quantity = 2

    bom.update_bom_for_part(child_1)

    assert bom.missing_item_costs == 1


def test_weighted_missing_item_costs_zero_unit_cost():
    """Non-product leaf with unit_cost 0 counts as Materials without price."""
    bom = setup_bom()
    child_1 = bom.parts[2]
    child_1.seller_part = MockSellerPart(unit_cost=Money(0, "USD"))
    child_1.total_extended_quantity = 2

    bom.update_bom_for_part(child_1)

    assert bom.missing_item_costs == 1


def test_weighted_missing_item_costs_none_unit_cost():
    """Non-product leaf with unit_cost None counts as Materials without price."""
    bom = setup_bom()
    child_1 = bom.parts[2]
    child_1.seller_part = MockSellerPart(unit_cost=None)

    assert bom.counts_as_missing_item_cost(child_1)


def test_weighted_missing_item_costs_priced_seller_not_counted():
    """Non-product leaf with a positive price is not missing."""
    bom = setup_bom()
    child_1 = bom.parts[2]
    child_1.total_extended_quantity = 2

    bom.update_bom_for_part(child_1)

    assert bom.missing_item_costs == 0


def test_weighted_missing_item_costs_skips_products():
    """Product assemblies are not counted even without a seller_part."""
    bom = setup_bom()
    child_1 = bom.parts[2]
    child_1.part_revision.is_product = True
    child_1.seller_part = None
    child_1.total_extended_quantity = 2

    bom.update_bom_for_part(child_1)

    assert bom.missing_item_costs == 0


def test_non_weighted_missing_item_costs_zero_and_no_seller():
    """Classic PartBom uses the same non-product None/0 price rule."""
    part = MockPart("LEAF")
    rev = MockPartRevision(part, is_product=False)
    bom = PartBom(part_revision=rev, quantity=1)

    def make_item(bom_id, seller_part):
        item = PartBomItem(
            bom_id=bom_id,
            part=part,
            part_revision=rev,
            do_not_load=False,
            references="",
            quantity=1,
            extended_quantity=1,
            seller_part=seller_part,
        )
        item.total_extended_quantity = 1
        return item

    bom.update_bom_for_part(make_item(1, MockSellerPart(unit_cost=Money(0, "USD"))))
    bom.update_bom_for_part(make_item(2, None))

    assert bom.missing_item_costs == 2
    assert bom.counts_as_missing_item_cost(
        make_item(3, MockSellerPart(unit_cost=None))
    )
    assert PartBom.seller_part_missing_price(MockSellerPart(unit_cost=Money(0, "USD")))
    assert not PartBom.seller_part_missing_price(
        MockSellerPart(unit_cost=Money(10, "USD"))
    )

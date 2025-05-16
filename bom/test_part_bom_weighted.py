import pytest
from djmoney.money import Money
from decimal import Decimal
from bom.part_bom_weighted import PartBomWeighted, PartBomWeightedItem


@pytest.fixture
def setup_bom():
    """
    Set up a sample BOM structure for testing.
    """
    # Create a root part
    root_part = PartBomWeightedItem(
        id=1,
        parent_id=None,
        indent_level=0,
        quantity=1,
        part_revision=MockPartRevision(material="standard"),
        seller_part=MockSellerPart(unit_cost=Money(100, "USD")),
        subpart=None,
        parent_quantity=1,
    )

    # Create child parts
    child_part_1 = PartBomWeightedItem(
        id=2,
        parent_id=1,
        indent_level=1,
        quantity=2,
        part_revision=MockPartRevision(material="standard"),
        seller_part=MockSellerPart(unit_cost=Money(50, "USD")),
        subpart=None,
        parent_quantity=1,
    )

    child_part_2 = PartBomWeightedItem(
        id=3,
        parent_id=1,
        indent_level=1,
        quantity=3,
        part_revision=MockPartRevision(material="with_loi"),
        seller_part=MockSellerPart(unit_cost=Money(30, "USD")),
        subpart=None,
        parent_quantity=1,
    )

    # Create a BOM object and add parts
    bom = PartBomWeighted()
    bom.parts = {1: root_part, 2: child_part_1, 3: child_part_2}

    return bom


class MockPartRevision:
    def __init__(self, material):
        self.material = material


class MockSellerPart:
    def __init__(self, unit_cost):
        self.unit_cost = unit_cost


@pytest.mark.skip(reason="Skipping test for now")
def test_update_as_weighted_bom_root(setup_bom):
    """
    Test that the root part's unit cost is calculated correctly.
    """
    bom = setup_bom
    root_part = bom.parts[1]

    # Call the method
    bom.update_as_weighted_bom(root_part)

    # Assert that the root part's unit cost is set correctly
    assert bom.unit_cost == Money(100, "USD")


@pytest.mark.skip(reason="Skipping test for now")
def test_update_as_weighted_bom_child_costs(setup_bom):
    """
    Test that the child parts' costs are calculated correctly.
    """
    bom = setup_bom
    child_part_1 = bom.parts[2]
    child_part_2 = bom.parts[3]

    # Call the method for child parts
    bom.update_as_weighted_bom(child_part_1)
    bom.update_as_weighted_bom(child_part_2)

    # Assert that the child parts' costs are calculated correctly
    assert child_part_1.childs_cost == Money(100, "USD")  # 2 * 50
    assert child_part_2.childs_cost == Money(90, "USD")  # 3 * 30


@pytest.mark.skip(reason="Skipping test for now")
def test_update_as_weighted_bom_parent_costs(setup_bom):
    """
    Test that the parent part's costs are updated based on its children.
    """
    bom = setup_bom
    root_part = bom.parts[1]

    # Call the method
    bom.update_as_weighted_bom(root_part)

    # Assert that the root part's cost includes its children's costs
    assert root_part.childs_cost == Money(190, "USD")  # 100 (child 1) + 90 (child 2)


@pytest.mark.skip(reason="Skipping test for now")
def test_update_as_weighted_bom_with_loi(setup_bom):
    """
    Test that the calculation works correctly for parts with "with_loi" material.
    """
    bom = setup_bom
    child_part_2 = bom.parts[3]

    # Set sintered quantity for the child part
    child_part_2.sintered_quantity = 2.5

    # Call the method
    bom.update_as_weighted_bom(child_part_2)

    # Assert that the cost is calculated based on sintered quantity
    assert child_part_2.childs_cost == Money(75, "USD")  # 2.5 * 30


@pytest.mark.skip(reason="Skipping test for now")
def test_update_as_weighted_bom_no_seller_part(setup_bom):
    """
    Test that the method handles parts without a seller_part correctly.
    """
    bom = setup_bom
    child_part_1 = bom.parts[2]

    # Remove the seller_part
    child_part_1.seller_part = None

    # Call the method
    bom.update_as_weighted_bom(child_part_1)

    # Assert that the cost is 0 since there is no seller_part
    assert child_part_1.childs_cost == Money(0, "USD")

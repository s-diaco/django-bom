from djmoney.money import Money
from decimal import Decimal
from .part_bom import PartBom, PartIndentedBomItem


class PartBomWeighted(PartBom):
    """
    Part BoM with weighted items. This class is used to calculate the cost of a
    part BoM with weighted items. It is a subclass of PartBom and adds the
    functionality to calculate the cost of a part BoM with weighted items.
    """

    def __init__(self, bom_unit_cost=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if bom_unit_cost is None:
            bom_unit_cost = Money(0, self._currency)
        self.bom_unit_cost = bom_unit_cost

    # TODO: simplify this method
    def update_as_weighted_bom(self, part):
        """
        Update "childs_cost" and "childs_quantity" for parent "PartBomItem"s
        all the way up to the root node of the tree and calculate unit_cost.

        :param part: BoM item whose parents will be updated
        :type part: PartBomWeightedItem
        """
        if not part.indent_level:
            # If the part is the root, calculate its unit cost directly
            if part.seller_part and part.seller_part.unit_cost is not None:
                self.unit_cost = part.seller_part.unit_cost
            return

        def calculate_parent_values(parent_part, subpart_list):
            """
            Calculate and update the parent's cost, quantity, and product quantity
            based on its children.
            """
            parent_part.childs_quantity = sum(child.quantity for child in subpart_list)

            if parent_part.part_revision.material in ["with_loi"]:
                parent_part.childs_product_quantity = sum(
                    child.sintered_quantity for child in subpart_list
                )
            else:
                parent_part.childs_product_quantity = sum(
                    child.quantity for child in subpart_list
                )

            parent_part.childs_cost = sum(
                (
                    child.childs_cost / child.childs_product_quantity * child.quantity
                    if child.childs_product_quantity
                    else 0
                )
                for child in subpart_list
            )

            parent_part.childs_cost += sum(
                (
                    child.seller_part.unit_cost * child.quantity
                    if child.seller_part and child.seller_part.unit_cost is not None
                    else 0
                )
                for child in subpart_list
            )

        def update_parent(child_part):
            """
            Recursively update the parent parts up to the root.
            """
            parent_part = self.parts[child_part.parent_id]
            subpart_list = [
                child
                for child in self.parts.values()
                if child.parent_id == child_part.parent_id
            ]

            # Calculate and update parent values
            calculate_parent_values(parent_part, subpart_list)

            # Update cost_effect_in_bom for child_part
            if parent_part.childs_cost:
                if (
                    child_part.seller_part
                    and child_part.seller_part.unit_cost is not None
                ):
                    child_part.cost_effect_in_bom = (
                        (child_part.seller_part.unit_cost + child_part.childs_cost)
                        * child_part.quantity
                        / parent_part.childs_cost
                    )
                else:
                    child_part.cost_effect_in_bom = (
                        child_part.childs_cost
                        * child_part.quantity
                        / parent_part.childs_product_quantity
                    )

            if parent_part.indent_level:
                update_parent(parent_part)
            else:
                # If the parent is the root, calculate the unit cost
                if (
                    self.part_revision.part.number_item
                    == parent_part.part_revision.part.number_item
                ):
                    self.unit_cost = parent_part.childs_unit_cost + (
                        parent_part.seller_part.unit_cost
                        if parent_part.seller_part and parent_part.seller_part.unit_cost
                        else 0
                    )
                    if parent_part.childs_quantity:
                        self.bom_unit_cost = (
                            parent_part.childs_cost
                            / parent_part.childs_product_quantity
                        )

        # Start updating from the given part
        update_parent(part)

    def update_bom_for_part(self, bom_part):
        if bom_part.do_not_load:
            bom_part.order_quantity = 0
            bom_part.order_cost = 0
            return

        self.update_as_weighted_bom(bom_part)
        if bom_part.seller_part:
            try:
                bom_part.order_quantity = bom_part.seller_part.order_quantity(
                    bom_part.total_extended_quantity
                )
                bom_part.order_cost = (
                    bom_part.total_extended_quantity * bom_part.seller_part.unit_cost
                )
            except AttributeError:
                pass
        else:
            self.missing_item_costs += 1


class PartBomWeightedItem(PartIndentedBomItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.childs_quantity = 0
        self.childs_product_quantity = 0
        self.childs_cost = Money(0, self._currency)
        self.cost_effect_in_bom = 0

        # Set residue quantity
        if not self.part_revision.tolerance:
            self.part_revision.tolerance = 0
        # TODO: fix: tolerance should be a float. it is a string
        # in the database
        self.sintered_quantity = self.quantity * (
            1 - (float(self.part_revision.tolerance) / 100)
        )

    @property
    def childs_unit_cost(self):
        """
        Get the unit cost of the child parts as a property.
        :return: unit cost of the child parts
        :rtype: Money
        """
        return (
            self.childs_cost / self.childs_product_quantity
            if self.childs_quantity
            else 0
        )

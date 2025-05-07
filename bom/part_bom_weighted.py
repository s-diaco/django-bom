from djmoney.money import Money
from decimal import Decimal
from .part_bom import PartBom, PartIndentedBomItem


class PartBomWeighted(PartBom):
    """
    Part BOM with weighted items. This class is used to calculate the cost of a
    part BOM with weighted items. It is a subclass of PartBom and adds the
    functionality to calculate the cost of a part BOM with weighted items.
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
        one by one all the way up to the root node of the tree and
        calculate unit_cost

        :param part: BOM item whom parents will be updated
        :type part: PartBomWeightedItem
        """

        if part.indent_level:

            def update_parent(child_part):
                parent_part = self.parts[child_part.parent_id]
                parent_part.childs_cost = 0
                parent_part.childs_quantity = 0
                parent_part.childs_product_quantity = 0
                # Update the parent part's cost and quantity based on its children
                subpart_list = [
                    x
                    for x in self.parts.values()
                    if x.parent_id == child_part.parent_id
                ]
                for child in subpart_list:
                    parent_part.childs_quantity += child.quantity
                    parent_part.childs_product_quantity += child.product_quantity
                    product_child_qty = (
                        child.childs_product_quantity
                        if child.part_revision.material in ["with_loi"]
                        else child.childs_quantity
                    )
                    if product_child_qty:
                        parent_part.childs_cost += (
                            child.childs_cost
                            / Decimal(product_child_qty)
                            * Decimal(child.quantity)
                        )
                    if child.seller_part and child.seller_part.unit_cost is not None:
                        parent_part.childs_cost += (
                            child.seller_part.unit_cost * child.quantity
                        )
                parent_part.unit_cost = parent_part.childs_cost / Decimal(
                    parent_part.childs_product_quantity
                    if parent_part.part_revision.material in ["with_loi"]
                    else parent_part.childs_quantity
                )
                if parent_part.seller_part and parent_part.seller_part.unit_cost:
                    parent_part.unit_cost += parent_part.seller_part.unit_cost
                if parent_part.indent_level:
                    update_parent(
                        child_part=parent_part,
                    )
                else:
                    # "part" is root
                    if (
                        self.part_revision.part.number_item
                        == parent_part.part_revision.part.number_item
                    ):
                        if parent_part.childs_quantity:
                            self.bom_unit_cost = parent_part.childs_cost / Decimal(
                                parent_part.childs_product_quantity
                                if parent_part.part_revision.material in ["with_loi"]
                                else parent_part.childs_quantity
                            )
                        self.unit_cost = parent_part.unit_cost

            update_parent(child_part=part)
        else:
            # TODO: Fix double calc
            # "part" is root
            if (part.seller_part) and (part.seller_part.unit_cost is not None):
                self.unit_cost = part.seller_part.unit_cost

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

        # Set residue quantity
        if not self.part_revision.tolerance:
            self.part_revision.tolerance = 0
        # TODO: fix: tolerance should be a float. it is a string
        # in the database
        self.product_quantity = self.quantity * (
            1 - (float(self.part_revision.tolerance) / 100)
        )

    @property
    def childs_unit_cost(self):
        """
        Get the unit cost of the child parts as a property.
        :return: unit cost of the child parts
        :rtype: Money
        """
        product_qty = (
            self.childs_quantity
            if self.part_revision.material not in ["with_loi"]
            else self.childs_product_quantity
        )
        return self.childs_cost / product_qty if self.childs_quantity else 0

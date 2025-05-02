from djmoney.money import Money
from .part_bom import PartBom, PartIndentedBomItem


class PartBomWeighted(PartBom):
    """
    Part BOM with weighted items. This class is used to calculate the cost of a
    part BOM with weighted items. It is a subclass of PartBom and adds the
    functionality to calculate the cost of a part BOM with weighted items.
    """

    def update_as_weighted_bom_2(self, part):
        """
        Update "childs_cost" and "childs_quantity" for parent "PartBomItem"s
        all the way up to the root node of the tree and calculate unit_cost.

        :param part: BOM item whose parents will be updated
        :type part: PartBomWeightedItem
        """
        if not part.indent_level:
            # If the part is the root, calculate its unit cost directly
            if part.seller_part and part.seller_part.unit_cost is not None:
                self.unit_cost += part.seller_part.unit_cost
            return

        def calculate_cost_and_quantity(child, parent, old_cost_per_qty=0):
            """
            Helper function to calculate and update the parent's cost and quantity
            based on the child's values.
            """
            # Revert the parent's previous cost contribution from the child
            if child.childs_quantity:
                cost_to_subtract = old_cost_per_qty
                if child.seller_part:
                    cost_to_subtract += child.seller_part.unit_cost
                cost_to_subtract *= (
                    child.residue_quantity
                    if parent.part_revision.material in ["with_loi"]
                    else child.quantity
                )
                parent.childs_cost -= cost_to_subtract

            # Update parent's quantity and cost with the child's new values
            parent.childs_quantity += child.quantity
            parent.childs_residue_quantity += child.residue_quantity

            cost_to_add = child.childs_cost
            if child.seller_part:
                cost_to_add += child.seller_part.unit_cost
            cost_to_add *= (
                child.residue_quantity
                if parent.part_revision.material in ["with_loi"]
                else child.quantity
            )
            parent.childs_cost += cost_to_add

        def update_parent(child):
            """
            Recursively update the parent parts up to the root.
            """
            parent = self.parts[child.parent_id]
            old_cost_per_qty = (
                parent.childs_cost / parent.childs_residue_quantity
                if parent.part_revision.material in ["with_loi"]
                and parent.childs_quantity
                else (
                    parent.childs_cost / parent.childs_quantity
                    if parent.childs_quantity
                    else 0
                )
            )

            calculate_cost_and_quantity(child, parent, old_cost_per_qty)

            if parent.indent_level:
                update_parent(parent)
            else:
                # If the parent is the root, calculate its unit cost
                self.unit_cost = (
                    parent.childs_cost / parent.childs_residue_quantity
                    if parent.part_revision.material in ["with_loi"]
                    and parent.childs_quantity
                    else (
                        parent.childs_cost / parent.childs_quantity
                        if parent.childs_quantity
                        else 0
                    )
                )
                if parent.seller_part and parent.seller_part.unit_cost is not None:
                    self.unit_cost += parent.seller_part.unit_cost

        # Start updating from the given part
        update_parent(part)

    # TODO: simplify this method using the above one
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
                parent_part.childs_residue_quantity = 0
                # Update the parent part's cost and quantity based on its children
                subpart_list = [
                    x
                    for x in self.parts.values()
                    if x.parent_id == child_part.parent_id
                ]
                for child in subpart_list:
                    parent_part.childs_quantity += child.quantity
                    parent_part.childs_residue_quantity += child.residue_quantity
                    child_product_qty = (
                        child.residue_quantity
                        if parent_part.part_revision.material in ["with_loi"]
                        else child.quantity
                    )
                    parent_part.childs_cost += (
                        child.childs_cost / child_product_qty * child.quantity
                    )
                    if child.seller_part and child.seller_part.unit_cost is not None:
                        parent_part.childs_cost += (
                            child.seller_part.unit_cost * child.quantity
                        )
                parent_part.unit_cost = parent_part.childs_cost / (
                    parent_part.childs_residue_quantity
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
                    if parent_part.bom_id == self.part_revision.assembly_id:
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
        self.childs_residue_quantity = 0
        self.childs_cost = Money(0, self._currency)

        # Set residue quantity
        if not self.part_revision.tolerance:
            self.part_revision.tolerance = 0
        # TODO: fix: tolerance should be a float. it is a string
        # in the database
        self.residue_quantity = self.quantity * (
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
            else self.childs_residue_quantity
        )
        return self.childs_cost / product_qty if self.childs_quantity else 0

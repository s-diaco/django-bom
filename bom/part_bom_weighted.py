from djmoney.money import Money
from .part_bom import PartBom, PartIndentedBomItem


class PartBomWeighted(PartBom):

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

            def update_parent(child_part, childs_old_cost_per_qty=0):
                parent_part = self.parts[child_part.parent_id]
                parents_old_cost_per_qty = 0
                if parent_part.childs_quantity:
                    if parent_part.part_revision.material in ["with_loi"]:
                        parents_old_cost_per_qty = (
                            parent_part.childs_cost
                            / parent_part.childs_residue_quantity
                        )
                    else:
                        parents_old_cost_per_qty = (
                            parent_part.childs_cost / parent_part.childs_quantity
                        )
                # Revert last calculation to add the new one later
                if child_part.childs_quantity:
                    value_to_sub = childs_old_cost_per_qty
                    if child_part.seller_part:
                        value_to_sub += child_part.seller_part.unit_cost
                    if parent_part.part_revision.material in ["with_loi"]:
                        value_to_sub *= child_part.residue_quantity
                    else:
                        value_to_sub *= child_part.quantity
                    parent_part.childs_cost -= value_to_sub
                # If its the first time for child_item to be sent for parent update
                else:
                    parent_part.childs_quantity += child_part.quantity
                    parent_part.childs_residue_quantity += child_part.residue_quantity
                cost_to_add = child_part.childs_cost
                if child_part.seller_part:
                    cost_to_add += child_part.seller_part.unit_cost
                if child_part.childs_quantity:
                    if child_part.part_revision.material in ["with_loi"]:
                        cost_to_add = (
                            cost_to_add
                            / child_part.childs_residue_quantity
                            * child_part.quantity
                        )
                    else:
                        cost_to_add = (
                            cost_to_add
                            / child_part.childs_quantity
                            * child_part.quantity
                        )
                else:
                    cost_to_add *= child_part.quantity
                parent_part.childs_cost += cost_to_add
                if parent_part.indent_level:
                    update_parent(
                        child_part=parent_part,
                        childs_old_cost_per_qty=parents_old_cost_per_qty,
                    )
                # "parent_part" is the root part
                else:
                    if parent_part.childs_quantity:
                        if parent_part.part_revision.material in ["with_loi"]:
                            self.unit_cost = (
                                parent_part.childs_cost
                                / parent_part.childs_residue_quantity
                            )
                        else:
                            self.unit_cost = (
                                parent_part.childs_cost / parent_part.childs_quantity
                            )
                    if (parent_part.seller_part) and (
                        parent_part.seller_part.unit_cost is not None
                    ):
                        self.unit_cost += parent_part.seller_part.unit_cost

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

    def get_childs_unit_cost(self):
        """
        Get the unit cost of the child parts
        :return: unit cost of the child parts
        :rtype: Money
        """
        product_qty = (
            self.childs_quantity
            if self.part_revision.material not in ["with_loi"]
            else self.childs_residue_quantity
        )
        return self.childs_cost / product_qty if self.childs_quantity else 0

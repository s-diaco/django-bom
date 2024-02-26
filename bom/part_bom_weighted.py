from djmoney.money import Money
from .part_bom import PartBom, PartIndentedBomItem


class PartBomWeighted(PartBom):

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
                    parents_old_cost_per_qty = (
                        parent_part.childs_cost / parent_part.childs_quantity
                    )
                # Revert last calculation to add the new one later
                if child_part.childs_quantity:
                    value_to_sub = childs_old_cost_per_qty
                    if child_part.seller_part:
                        if (
                            parent_part.part_revision.material in ["with_loi"]
                            and child_part.part_revision.tolerance.isnumeric()
                        ):
                            value_to_sub += child_part.seller_part.unit_cost / (
                                1 - float(child_part.part_revision.tolerance) / 100
                            )
                        else:
                            value_to_sub += child_part.seller_part.unit_cost
                    value_to_sub *= child_part.quantity
                    parent_part.childs_cost -= value_to_sub
                # If its the first time for child_item to be sent for parent update
                else:
                    parent_part.childs_quantity += child_part.quantity
                cost_to_add = child_part.childs_cost
                if child_part.seller_part:
                    if (
                        parent_part.part_revision.material in ["with_loi"]
                        and child_part.part_revision.tolerance.isnumeric()
                    ):
                        cost_to_add += child_part.seller_part.unit_cost / (
                            1 - float(child_part.part_revision.tolerance) / 100
                        )
                    else:
                        cost_to_add += child_part.seller_part.unit_cost
                if child_part.childs_quantity:
                    cost_to_add = (
                        cost_to_add / child_part.childs_quantity * child_part.quantity
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
                    self.unit_cost = (
                        parent_part.childs_cost / parent_part.childs_quantity
                    )
                    if (parent_part.seller_part) and (
                        parent_part.seller_part.unit_cost is not None
                    ):
                        self.unit_cost += parent_part.seller_part.unit_cost

            update_parent(child_part=part)

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
        self.childs_cost = Money(0, self._currency)

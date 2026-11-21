"""Part.latest(): Active first, then usable cost > 0, then highest id."""

from django.test import TestCase
from djmoney.money import Money

from bom.constants import CONFIGURATION_TYPE_RELEASED, CONFIGURATION_TYPE_WORKING
from bom.helpers import (
    create_a_fake_seller_part,
    create_some_fake_manufacturers,
    create_some_fake_part_classes,
    create_some_fake_sellers,
    create_user_and_organization,
)
from bom.list_queries import latest_part_revision_ids
from bom.models import ManufacturerPart, Part, PartRevision, Subpart
from bom.part_bom import PartBom


class PartLatestTests(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        self.part_class = create_some_fake_part_classes(self.organization)[0]
        self.seller = create_some_fake_sellers(self.organization)[0]
        self.manufacturer = create_some_fake_manufacturers(self.organization)[0]
        self.currency = self.organization.currency

    def _make_part(self, number, material="no_bom"):
        part = Part.objects.create(
            organization=self.organization,
            number_class=self.part_class,
            number_item=number,
        )
        mp = ManufacturerPart.objects.create(
            part=part,
            manufacturer=self.manufacturer,
            manufacturer_part_number=number,
        )
        part.primary_manufacturer_part = mp
        part.save()
        return part, mp

    def _make_rev(self, part, revision, material, configuration=CONFIGURATION_TYPE_WORKING):
        return PartRevision.objects.create(
            part=part,
            revision=revision,
            description=f"{part.number_item}-{revision}",
            material=material,
            configuration=configuration,
        )

    def _add_child(self, parent_rev, child_rev, qty=1):
        subpart = Subpart.objects.create(part_revision=child_rev, count=qty)
        parent_rev.assembly.subparts.add(subpart)

    def test_skips_inactive_preferring_older_active(self):
        part, _mp = self._make_part("SKIP1")
        active = self._make_rev(part, "1", "no_bom")
        inactive = self._make_rev(
            part, "2", "no_bom", configuration=CONFIGURATION_TYPE_RELEASED
        )
        self.assertGreater(inactive.id, active.id)
        self.assertEqual(part.latest().id, active.id)

    def test_prefers_cost_over_newer_unpriced_active(self):
        raw, raw_mp = self._make_part("RAWC")
        raw_rev = self._make_rev(raw, "1", "no_bom")
        create_a_fake_seller_part(
            self.seller,
            raw_mp,
            1,
            1,
            Money(10, self.currency),
            1,
            Money(0, self.currency),
        )

        product, _mp = self._make_part("PRDC", material="no_loi")
        priced = self._make_rev(product, "1", "no_loi")
        self._add_child(priced, raw_rev, 1)
        unpriced = self._make_rev(product, "2", "no_loi")
        self.assertGreater(unpriced.id, priced.id)
        self.assertFalse(
            PartBom.cost_is_missing_or_zero(priced.bom_unit_cost),
            priced.bom_unit_cost,
        )
        self.assertTrue(
            PartBom.cost_is_missing_or_zero(unpriced.bom_unit_cost),
            unpriced.bom_unit_cost,
        )
        self.assertEqual(product.latest().id, priced.id)

    def test_zero_or_missing_cost_ranks_after_positive(self):
        raw, raw_mp = self._make_part("RAW0")
        raw_rev = self._make_rev(raw, "1", "no_bom")
        create_a_fake_seller_part(
            self.seller,
            raw_mp,
            1,
            1,
            Money(0, self.currency),
            1,
            Money(0, self.currency),
        )
        self.assertTrue(
            PartBom.seller_part_missing_price(raw.optimal_seller())
        )

        priced_raw, priced_mp = self._make_part("RAWP")
        priced_raw_rev = self._make_rev(priced_raw, "1", "no_bom")
        create_a_fake_seller_part(
            self.seller,
            priced_mp,
            1,
            1,
            Money(5, self.currency),
            1,
            Money(0, self.currency),
        )

        product, _mp = self._make_part("PRD0", material="no_loi")
        zero_cost = self._make_rev(product, "1", "no_loi")
        self._add_child(zero_cost, raw_rev, 1)
        positive = self._make_rev(product, "2", "no_loi")
        self._add_child(positive, priced_raw_rev, 1)
        # Newer empty Active would win on id alone; zero-cost child still missing.
        empty_newer = self._make_rev(product, "3", "no_loi")
        self.assertGreater(empty_newer.id, positive.id)
        self.assertTrue(PartBom.cost_is_missing_or_zero(zero_cost.bom_unit_cost))
        self.assertFalse(PartBom.cost_is_missing_or_zero(positive.bom_unit_cost))
        self.assertTrue(PartBom.cost_is_missing_or_zero(empty_newer.bom_unit_cost))
        self.assertEqual(product.latest().id, positive.id)

    def test_no_active_falls_back_among_inactive_preferring_cost(self):
        raw, raw_mp = self._make_part("RAWF")
        raw_rev = self._make_rev(raw, "1", "no_bom")
        create_a_fake_seller_part(
            self.seller,
            raw_mp,
            1,
            1,
            Money(8, self.currency),
            1,
            Money(0, self.currency),
        )

        product, _mp = self._make_part("PRDF", material="no_loi")
        priced = self._make_rev(
            product, "1", "no_loi", configuration=CONFIGURATION_TYPE_RELEASED
        )
        self._add_child(priced, raw_rev, 1)
        empty = self._make_rev(
            product, "2", "no_loi", configuration=CONFIGURATION_TYPE_RELEASED
        )
        self.assertGreater(empty.id, priced.id)
        self.assertIsNone(
            product.revisions()
            .filter(configuration=CONFIGURATION_TYPE_WORKING)
            .first()
        )
        self.assertEqual(product.latest().id, priced.id)

    def test_no_active_falls_back_to_highest_id_when_costs_tie(self):
        part, _mp = self._make_part("INAC")
        older = self._make_rev(
            part, "1", "no_bom", configuration=CONFIGURATION_TYPE_RELEASED
        )
        newer = self._make_rev(
            part, "2", "no_bom", configuration=CONFIGURATION_TYPE_RELEASED
        )
        self.assertGreater(newer.id, older.id)
        self.assertEqual(part.latest().id, newer.id)

    def test_latest_part_revision_ids_matches_latest(self):
        part, _mp = self._make_part("LIST1")
        active = self._make_rev(part, "1", "no_bom")
        self._make_rev(
            part, "2", "no_bom", configuration=CONFIGURATION_TYPE_RELEASED
        )
        ids = latest_part_revision_ids([part.id])
        self.assertEqual(ids, [active.id])
        self.assertEqual(part.latest().id, active.id)

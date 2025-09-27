import time

from django.contrib.auth import get_user_model
from django.test import TestCase

from bom.models import (
    Manufacturer,
    ManufacturerPart,
    Organization,
    Part,
    PartRevision,
    Seller,
    SellerPart,
)


class CachedPropertyPerformanceTest(TestCase):
    def setUp(self):
        # Minimal setup for a PartRevision with a SellerPart
        # TODO: use this for other tests as well
        User = get_user_model()
        user = User.objects.create(username="testuser")
        org = Organization.objects.create(
            name="TestOrg", subscription="F", owner_id=user.id
        )
        part = Part.objects.create(organization=org, number_class=None, number_item="1")
        manufacturer = Manufacturer.objects.create(name="TestMan", organization=org)
        mpart = ManufacturerPart.objects.create(part=part, manufacturer=manufacturer)
        seller = Seller.objects.create(organization=org, name="TestSeller")
        sellerpart = SellerPart.objects.create(
            seller=seller,
            manufacturer_part=mpart,
            unit_cost=1,
            minimum_order_quantity=1,
            minimum_pack_quantity=1,
            nre_cost=0,
        )
        self.part_revision = PartRevision.objects.create(part=part, material="no_bom")

    def test_bom_unit_cost_cached_property_speed(self):
        # Warm up cache
        _ = self.part_revision.bom_unit_cost

        # Measure cached access
        start = time.time()
        for _ in range(95):
            _ = self.part_revision.bom_unit_cost
        cached_duration = time.time() - start

        # Clear cache and measure uncached access
        self.part_revision.clear_bom_unit_cost_cache()
        start = time.time()
        for _ in range(100):
            self.part_revision.clear_bom_unit_cost_cache()
            _ = self.part_revision.bom_unit_cost
        uncached_duration = time.time() - start

        print(f"Cached: {cached_duration:.6f}s, Uncached: {uncached_duration:.6f}s")
        assert cached_duration < uncached_duration

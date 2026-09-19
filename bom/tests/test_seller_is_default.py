from django.test import SimpleTestCase

from bom.constants import DEFAULT_SELLER_NAME
from bom.models import Seller


class SellerIsDefaultTest(SimpleTestCase):
    def test_default_seller_name_is_default(self):
        seller = Seller(name=DEFAULT_SELLER_NAME)
        self.assertTrue(seller.is_default)

    def test_default_seller_name_case_insensitive(self):
        seller = Seller(name=DEFAULT_SELLER_NAME.upper())
        self.assertTrue(seller.is_default)

    def test_normal_seller_is_not_default(self):
        seller = Seller(name="Acme Supply")
        self.assertFalse(seller.is_default)

    def test_empty_name_is_not_default(self):
        seller = Seller(name="")
        self.assertFalse(seller.is_default)

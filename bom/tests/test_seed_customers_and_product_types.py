from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from bom.helpers import create_user_and_organization
from bom.models import Customer, ProductType

FIXTURE_CSV = Path(__file__).resolve().parents[1] / "data" / "customers.csv"


@override_settings(BOM_CONFIG=settings.BOM_CONFIG_DEFAULT)
class SeedCustomersAndProductTypesTests(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        # Simulate legacy display names for the three built-in codes.
        for code, old_name in (
            ("no_loi", "Without loss (LOI) (compound, ink, …)"),
            ("with_loi", "With loss (LOI) (Frit)"),
            ("no_bom", "Raw materials"),
        ):
            ProductType.objects.filter(
                organization=self.organization, code=code
            ).update(name=old_name)
        ProductType.objects.filter(
            organization=self.organization, code__in=("ink", "powder")
        ).delete()
        self.organization.invalidate_product_type_cache()

    def test_requires_organization_id(self):
        with self.assertRaises(CommandError):
            call_command("seed_customers_and_product_types", stdout=StringIO())

    def test_dry_run_does_not_write(self):
        out = StringIO()
        call_command(
            "seed_customers_and_product_types",
            organization_id=self.organization.id,
            customers_csv=str(FIXTURE_CSV),
            stdout=out,
        )
        text = out.getvalue()
        self.assertIn("DRY RUN", text)
        self.assertEqual(
            ProductType.objects.get(
                organization=self.organization, code="no_loi"
            ).name,
            "Without loss (LOI) (compound, ink, …)",
        )
        self.assertFalse(
            ProductType.objects.filter(
                organization=self.organization, code="ink"
            ).exists()
        )
        self.assertEqual(
            Customer.objects.filter(organization=self.organization).count(), 0
        )

    def test_execute_renames_creates_and_upserts(self):
        Customer.objects.create(
            organization=self.organization, name="کاشی الوند"
        )
        out = StringIO()
        call_command(
            "seed_customers_and_product_types",
            organization_id=self.organization.id,
            customers_csv=str(FIXTURE_CSV),
            execute=True,
            stdout=out,
        )
        names = dict(
            ProductType.objects.filter(organization=self.organization).values_list(
                "code", "name"
            )
        )
        self.assertEqual(names["no_loi"], "Compound")
        self.assertEqual(names["with_loi"], "Frit")
        self.assertEqual(names["no_bom"], "Raw Material")
        ink = ProductType.objects.get(organization=self.organization, code="ink")
        powder = ProductType.objects.get(
            organization=self.organization, code="powder"
        )
        self.assertTrue(ink.has_bom)
        self.assertFalse(ink.apply_loi)
        self.assertTrue(powder.has_bom)
        self.assertFalse(powder.apply_loi)
        self.assertEqual(ink.overhead.amount, 0)
        self.assertEqual(
            Customer.objects.filter(organization=self.organization).count(),
            160,  # unique non-empty company_name values in bom/data/customers.csv
        )
        self.assertEqual(
            Customer.objects.filter(
                organization=self.organization, name="کاشی الوند"
            ).count(),
            1,
        )
        self.assertIn("created", out.getvalue().lower())

        # Idempotent second run.
        out2 = StringIO()
        call_command(
            "seed_customers_and_product_types",
            organization_id=self.organization.id,
            customers_csv=str(FIXTURE_CSV),
            execute=True,
            stdout=out2,
        )
        self.assertIn("Renamed 0 product type(s)", out2.getvalue())
        self.assertIn("created 0 product type(s)", out2.getvalue())
        self.assertIn("created 0 customer(s)", out2.getvalue())

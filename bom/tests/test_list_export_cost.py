"""Self-check: materials-list export price never walks indented BOM."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from bom.helpers import create_a_fake_organization, create_some_fake_parts
from bom.list_queries import list_unit_cost, prepare_part_revs_for_export
from bom.models import PartRevision


class ListExportCostTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="export-cost", password="pass"
        )
        self.organization = create_a_fake_organization(user)
        create_some_fake_parts(organization=self.organization)

    def test_list_unit_cost_without_rollup_never_calls_indented(self):
        part_rev = PartRevision.objects.select_related("part").first()
        with patch.object(
            PartRevision,
            "indented",
            side_effect=AssertionError("rollup_bom=False must skip indented"),
        ):
            list_unit_cost(part_rev, rollup_bom=False)

    def test_prepare_part_revs_for_export_skips_bom_walk(self):
        qs = PartRevision.objects.all()
        with patch.object(
            PartRevision,
            "indented",
            side_effect=AssertionError("export prep must skip indented"),
        ):
            page = prepare_part_revs_for_export(qs)
            costs = [pr.print_unit_cost for pr in page]
        self.assertEqual(len(costs), qs.count())

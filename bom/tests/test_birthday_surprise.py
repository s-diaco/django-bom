from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.admin.sites import AdminSite
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.conf import settings

from bom.admin import UserMetaAdmin, UserMetaAdminForm
from bom.birthday import BirthdayMD, matches_birthday, parse_birthday_input
from bom.context_processors import birthday_surprise
from bom.forms import UserMetaForm
from bom.helpers import create_user_and_organization
from bom.models import UserMeta


class TestParseBirthdayInput(SimpleTestCase):
    def test_gregorian_full_date(self):
        self.assertEqual(parse_birthday_input("1990/03/21"), BirthdayMD(3, 21, False))

    def test_jalali_full_date_keeps_jalali_month_day(self):
        # Year only detects Jalali; month/day stay Jalali (not frozen Gregorian).
        self.assertEqual(parse_birthday_input("1403/01/01"), BirthdayMD(1, 1, True))
        self.assertEqual(parse_birthday_input("1403/08/30"), BirthdayMD(8, 30, True))

    def test_month_day_gregorian(self):
        self.assertEqual(parse_birthday_input("11/21"), BirthdayMD(11, 21, False))

    def test_empty_clears(self):
        self.assertIsNone(parse_birthday_input(""))
        self.assertIsNone(parse_birthday_input("  "))


class TestBirthdayMatch(SimpleTestCase):
    def test_match_month_day(self):
        self.assertTrue(matches_birthday(11, 21, date(2026, 11, 21)))
        self.assertFalse(matches_birthday(11, 21, date(2026, 11, 22)))

    def test_jalali_month_day_matches_tehran_today(self):
        # 2026-11-21 Asia/Tehran == Jalali 1405/08/30
        self.assertTrue(
            matches_birthday(8, 30, date(2026, 11, 21), jalali=True)
        )
        self.assertFalse(
            matches_birthday(8, 30, date(2026, 11, 20), jalali=True)
        )

    def test_unset_never_matches(self):
        self.assertFalse(matches_birthday(None, None, date(2026, 11, 21)))
        self.assertFalse(matches_birthday(11, None, date(2026, 11, 21)))


@override_settings(BOM_CONFIG=settings.BOM_CONFIG_DEFAULT)
class TestBirthdayAdminAndUi(TestCase):
    def setUp(self):
        self.user, self.organization = create_user_and_organization()
        self.profile = self.user.bom_profile()
        self.client = Client()
        self.client.force_login(self.user)
        self.factory = RequestFactory()

    def test_usermeta_form_excludes_birthday(self):
        form = UserMetaForm(instance=self.profile, organization=self.organization)
        self.assertNotIn("birthday_month", form.fields)
        self.assertNotIn("birthday_day", form.fields)
        self.assertNotIn("birthday", form.fields)

    def test_settings_page_hides_birthday(self):
        response = self.client.get(reverse("bom:settings"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertNotIn("birthday", html.lower())
        self.assertNotIn("birthday_month", html)
        self.assertNotIn("name=\"birthday\"", html)

    def test_admin_form_sets_from_jalali(self):
        form = UserMetaAdminForm(
            data={
                "organization": self.organization.pk,
                "role": self.profile.role,
                "calendar": self.profile.calendar,
                "language": "fa",
                "birthday": "1403/08/30",
                "systemgroup_username": "",
                "systemgroup_password": "",
            },
            instance=self.profile,
        )
        self.assertTrue(form.is_valid(), form.errors)
        meta = form.save()
        self.assertEqual(meta.birthday_month, 8)
        self.assertEqual(meta.birthday_day, 30)
        self.assertTrue(meta.birthday_jalali)

    def test_admin_form_sets_from_gregorian_md(self):
        form = UserMetaAdminForm(
            data={
                "organization": self.organization.pk,
                "role": self.profile.role,
                "calendar": self.profile.calendar,
                "language": "fa",
                "birthday": "11/21",
                "systemgroup_username": "",
                "systemgroup_password": "",
            },
            instance=self.profile,
        )
        self.assertTrue(form.is_valid(), form.errors)
        meta = form.save()
        self.assertEqual((meta.birthday_month, meta.birthday_day), (11, 21))
        self.assertFalse(meta.birthday_jalali)

    def test_admin_inline_prefixed_birthday_saves(self):
        prefix = "usermeta_set-0"
        form = UserMetaAdminForm(
            data={
                f"{prefix}-organization": self.organization.pk,
                f"{prefix}-role": self.profile.role,
                f"{prefix}-calendar": self.profile.calendar,
                f"{prefix}-language": "fa",
                f"{prefix}-birthday": "1403/08/30",
                f"{prefix}-systemgroup_username": "",
                f"{prefix}-systemgroup_password": "",
            },
            instance=self.profile,
            prefix=prefix,
        )
        self.assertTrue(form.is_valid(), form.errors)
        meta = form.save()
        self.assertEqual((meta.birthday_month, meta.birthday_day), (8, 30))
        self.assertTrue(meta.birthday_jalali)

    def test_usermeta_admin_lists_birthday_field(self):
        admin = UserMetaAdmin(UserMeta, AdminSite())
        self.assertIn("birthday", admin.fields)

    def test_birthday_ui_class_when_today(self):
        with timezone.override("Asia/Tehran"):
            today = timezone.localdate()
            self.profile.birthday_month = today.month
            self.profile.birthday_day = today.day
            self.profile.birthday_jalali = False
            self.profile.save(
                update_fields=["birthday_month", "birthday_day", "birthday_jalali"]
            )
            response = self.client.get(reverse("bom:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_birthday"])
        html = response.content.decode("utf-8")
        self.assertIn("is-birthday", html)
        # Loading mark wrap is the birthday spinner hook; keep surprise (no spoilers).
        self.assertIn("bom-page-loading-mark-wrap", html)
        self.assertNotIn("happy birthday", html.lower())
        self.assertNotIn("تولدت مبارک", html)

    def test_jalali_birthday_ui_class_when_jalali_today(self):
        # 1403/08/30 stores Jalali 8/30; 2026-11-21 is Jalali 1405/08/30.
        self.profile.birthday_month = 8
        self.profile.birthday_day = 30
        self.profile.birthday_jalali = True
        self.profile.save(
            update_fields=["birthday_month", "birthday_day", "birthday_jalali"]
        )
        with patch("bom.birthday.timezone.localdate", return_value=date(2026, 11, 21)):
            response = self.client.get(reverse("bom:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_birthday"])
        self.assertIn("is-birthday", response.content.decode("utf-8"))

    def test_non_birthday_normal_ui(self):
        with timezone.override("Asia/Tehran"):
            today = timezone.localdate()
            other_day = 1 if today.day != 1 else 2
            self.profile.birthday_month = today.month
            self.profile.birthday_day = other_day
            self.profile.save(update_fields=["birthday_month", "birthday_day"])
            response = self.client.get(reverse("bom:home"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_birthday"])
        self.assertNotIn("is-birthday", response.content.decode("utf-8"))

    def test_context_processor_false_when_unset(self):
        request = self.factory.get("/")
        request.user = self.user
        self.assertEqual(birthday_surprise(request), {"is_birthday": False})

    def test_model_is_birthday_uses_tehran_localdate(self):
        # 2026-11-21 01:30 UTC is still 2026-11-21 in Tehran (UTC+3:30)
        when = datetime(2026, 11, 21, 1, 30, tzinfo=ZoneInfo("UTC"))
        self.profile.birthday_month = 11
        self.profile.birthday_day = 21
        self.profile.save(update_fields=["birthday_month", "birthday_day"])
        with timezone.override("Asia/Tehran"):
            self.assertTrue(self.profile.is_birthday(when))
            self.assertFalse(self.profile.is_birthday(date(2026, 11, 22)))

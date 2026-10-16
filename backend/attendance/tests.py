"""Tests for Update Attendance (attendance/manual_entry.py).

    venv\\Scripts\\python.exe manage.py test attendance --settings=hris.test_settings
"""

import json
from datetime import date, datetime, timedelta
from unittest import mock

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase

from users.models import Employees

from .models import Attendance, AttendanceManualEdit

DAY = date(2026, 10, 14)


def bearer(user, superuser=None):
    payload = {"user_id": user.pk, "erpid": 1,
               "is_superuser": user.is_superuser if superuser is None else superuser}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return {"HTTP_AUTHORIZATION": "Bearer " + token}


def punch(hris_id, hhmm, status, uid=1):
    hour, minute = map(int, hhmm.split(":"))
    return Attendance.objects.create(
        uid=uid, user_id=hris_id, status=status, punch=0, lateintime="",
        timestamp=datetime(DAY.year, DAY.month, DAY.day, hour, minute),
    )


@mock.patch("attendance.manual_entry._has_menu_right", return_value=False)
class ManualEntryTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("root.admin", "root@ismo.gov.pk", "x",
                                              is_superuser=True, first_name="Root", last_name="Admin")
        self.staff = User.objects.create_user("plain.user", "plain@ismo.gov.pk", "x")
        Employees.objects.create(erp_id=575, hris_id=15549, name="Muhammad Adil", cnic="", gender="M",
                                 section_id=7, location_id=1, grade_id=7, designation_id=1,
                                 position="", flag=1)

    def day(self, headers=None, **params):
        query = {"erp_id": 575, "date": DAY.isoformat(), **params}
        return self.client.get("/api/attendance/manual-entry/", query,
                               **(bearer(self.admin) if headers is None else headers))

    def save(self, headers=None, **fields):
        body = {"erp_id": 575, "date": DAY.isoformat(), "reason": "Biometric device was down", **fields}
        return self.client.post("/api/attendance/manual-entry/save/", data=json.dumps(body),
                                content_type="application/json",
                                **(bearer(self.admin) if headers is None else headers))

    def times(self):
        body = self.day().json()
        return body["check_in"], body["check_out"]

    # ---- access -------------------------------------------------------------
    def test_needs_an_administrator(self, rights):
        self.assertEqual(self.day(headers={}).status_code, 403)
        self.assertEqual(self.day(headers=bearer(self.staff)).status_code, 403)
        self.assertEqual(self.save(headers=bearer(self.staff), check_in="08:15").status_code, 403)
        self.assertEqual(Attendance.objects.count(), 0)
        rights.return_value = True  # granted the page in Assign Rights
        self.assertEqual(self.day(headers=bearer(self.staff)).status_code, 200)

    # ---- inserting ------------------------------------------------------------
    def test_insert_both_for_a_day_with_no_punches(self, _rights):
        response = self.save(check_in="08:15", check_out="16:20")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.times(), ("08:15", "16:20"))
        check_in = Attendance.objects.get(status="Checked In")
        self.assertEqual((check_in.user_id, check_in.punch, check_in.lateintime), (15549, 0, "on time"))
        check_out = Attendance.objects.get(status="Checked Out")
        self.assertEqual(check_out.punch, 1)
        self.assertNotEqual(check_in.uid, check_out.uid)

    def test_late_and_early_marks_follow_the_device_rules(self, _rights):
        self.save(check_in="09:05", check_out="15:30")
        self.assertEqual(Attendance.objects.get(status="Checked In").lateintime, "late")
        self.assertTrue(Attendance.objects.filter(status="Early Checked Out").exists())

    def test_insert_only_the_missing_check_out(self, _rights):
        punch(15549, "08:10", "Checked In")
        self.save(check_out="16:05")
        self.assertEqual(self.times(), ("08:10", "16:05"))
        self.assertEqual(Attendance.objects.filter(status="Checked In").count(), 1)

    # ---- correcting -------------------------------------------------------------
    def test_update_moves_existing_punches_instead_of_adding(self, _rights):
        punch(15549, "09:40", "Checked In")
        punch(15549, "13:00", "Early Checked Out")
        self.save(check_in="08:20", check_out="16:30")
        self.assertEqual(self.times(), ("08:20", "16:30"))
        self.assertEqual(Attendance.objects.count(), 2)
        self.assertEqual(Attendance.objects.get(timestamp__hour=16).status, "Checked Out")

    def test_only_first_check_in_and_last_check_out_change(self, _rights):
        punch(15549, "08:40", "Checked In")
        punch(15549, "12:00", "Checked In")         # back from lunch
        punch(15549, "12:55", "Early Checked Out")  # out for lunch
        punch(15549, "15:10", "Early Checked Out")
        self.save(check_in="08:25", check_out="16:10")
        self.assertEqual(self.times(), ("08:25", "16:10"))
        self.assertTrue(Attendance.objects.filter(timestamp__hour=12, timestamp__minute=0).exists())
        self.assertTrue(Attendance.objects.filter(timestamp__hour=12, timestamp__minute=55).exists())

    def test_a_time_another_punch_would_overrule_is_refused(self, _rights):
        punch(15549, "08:40", "Checked In")
        punch(15549, "09:00", "Checked In")
        punch(15549, "17:00", "Checked Out")
        punch(15549, "17:30", "Checked Out")
        late_in = self.save(check_in="09:30")
        self.assertIn("09:00 is earlier", late_in.json()["errors"]["check_in"])
        # 17:30 is the last check-out; moving it before the other one (17:00)
        # would leave 17:00 as the last, so it is refused.
        early_out = self.save(check_out="16:50")
        self.assertIn("17:00 is later", early_out.json()["errors"]["check_out"])
        self.assertEqual(self.times(), ("08:40", "17:30"))

    # ---- checks -------------------------------------------------------------------
    def test_validation(self, _rights):
        def error(**fields):
            return self.save(**fields).json().get("errors", {})
        self.assertIn("check_in", error())  # nothing to change
        self.assertIn("check_in", error(check_in="8.15"))
        self.assertIn("check_out", error(check_in="16:00", check_out="08:00"))
        self.assertIn("reason", error(check_in="08:15", reason=""))
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.assertIn("date", error(check_in="08:15", date=tomorrow))
        self.assertIn("erp_id", error(check_in="08:15", erp_id=999999))
        punch(15549, "16:00", "Checked Out")
        self.assertIn("check_in", error(check_in="16:30"))  # after the existing check-out
        self.assertEqual(AttendanceManualEdit.objects.count(), 0)

    # ---- audit ----------------------------------------------------------------------
    def test_every_change_is_recorded(self, _rights):
        punch(15549, "09:40", "Checked In")
        self.save(check_in="08:20", check_out="16:30", reason="Forgot to punch, confirmed by head")
        edit = AttendanceManualEdit.objects.get()
        self.assertEqual((edit.erp_id, edit.work_date), (575, DAY))
        self.assertEqual((edit.old_check_in, edit.new_check_in), ("09:40", "08:20"))
        self.assertEqual((edit.old_check_out, edit.new_check_out), ("", "16:30"))
        self.assertEqual((edit.changed_by, edit.changed_by_name), (self.admin.pk, "Root Admin"))
        history = self.day().json()["history"]
        self.assertEqual(history[0]["reason"], "Forgot to punch, confirmed by head")

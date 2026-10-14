"""Tests for the password policy and the account endpoints that set passwords.

    venv\\Scripts\\python.exe manage.py test users --settings=hris.test_settings

The Assign Rights lookup reads SQL Server, so it is stubbed here.
"""

import json
from unittest import mock

import jwt
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.test import TestCase

from addtouser.models import CustomUser

from .password_policy import generate_password, password_problems

STRONG = "Vr7#kq!Tz2@wLm"
STRONG_2 = "Nx4$hp&Qc9!eRb"


def bearer(user, superuser=None):
    payload = {
        "user_id": user.pk,
        "erpid": 1,
        "is_superuser": user.is_superuser if superuser is None else superuser,
    }
    return {"HTTP_AUTHORIZATION": "Bearer " + jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")}


def post(client, url, body=None, headers=None):
    return client.post(url, data=json.dumps(body or {}), content_type="application/json",
                       **(headers or {}))


# ---------------------------------------------------------------------------
# The policy itself
# ---------------------------------------------------------------------------

class PolicyTests(TestCase):
    def test_strong_password_passes(self):
        self.assertEqual(password_problems(STRONG), [])

    def test_each_rule(self):
        cases = {
            "Ab1!xyzw": "at least 12",
            "vr7#kq!tz2@wlm": "uppercase",
            "VR7#KQ!TZ2@WLM": "lowercase",
            "Vr#kq!Tz@wLmPq": "number",
            "Vr7kqTz2wLmPq9": "special",
            "Vr7#kq !Tz2@wLm": "spaces",
            "Vr7#kq!Tz2@wLmmm": "repeat",
            "Vr7#kq!Tz2@abcd": "sequences",
            "Vr7#kq!Tz2@1234": "sequences",
            "Vr7#kq!Tz2@qwer": "sequences",
            "A1!" + "x" * 130: "more than 128",
        }
        for password, expected in cases.items():
            problems = " | ".join(password_problems(password))
            self.assertIn(expected, problems, password)

    def test_common_passwords_are_refused(self):
        # From the shared short list, and from Django's list of 20,000.
        for password in ("password123", "ismo@123"):
            self.assertTrue(any("too common" in p for p in password_problems(password.lower())),
                            password)
        self.assertTrue(any("too common" in p for p in password_problems("sunshine1")))

    def test_personal_details_are_refused(self):
        details = dict(username="baseerkhan", email="baseer@ismo.gov.pk",
                       first_name="Baseer", last_name="Khan", erp_id="546")
        for password in ("Baseer#2026xQ!", "Zx!9Khan#Lp2w", "Zx!9q#Lp546wT", "Zx!9BaseerKHN#"):
            self.assertTrue(any("name, username, email or ERP ID" in p
                                for p in password_problems(password, **details)), password)
        # The email's domain is not personal - everyone at ISMO shares it.
        self.assertEqual(password_problems("Ismo.gov#Zq7wR!x", email="baseer@ismo.gov.pk"), [])

    def test_must_differ_from_current(self):
        self.assertIn("Choose a password different from the current one",
                      password_problems(STRONG, current_password=STRONG))

    def test_generated_passwords_meet_the_policy(self):
        for _ in range(25):
            password = generate_password(username="someone", email="someone@ismo.gov.pk")
            self.assertEqual(password_problems(password, username="someone"), [])
            self.assertEqual(len(password), 16)


# ---------------------------------------------------------------------------
# The endpoints
# ---------------------------------------------------------------------------

@mock.patch("users.views._has_menu_right", return_value=False)
class AccountEndpointTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_user("root.admin", "root@ismo.gov.pk", STRONG,
                                             is_superuser=True)
        self.hr = User.objects.create_user("hr.admin", "hr@ismo.gov.pk", STRONG)
        self.staff = User.objects.create_user("plain.user", "plain@ismo.gov.pk", STRONG)
        CustomUser.objects.create(authid=self.staff.pk, erpid=700)

    def new_user(self, **changes):
        body = {
            "username": "new.person", "first_name": "New", "last_name": "Person",
            "email": "new.person@ismo.gov.pk", "erpid": "901",
            "password": STRONG_2, "verify_password": STRONG_2,
        }
        body.update(changes)
        return body

    # ---- create user ----------------------------------------------------------
    def test_create_user_needs_an_administrator(self, _rights):
        self.assertEqual(post(self.client, "/api/users/create_user/", self.new_user()).status_code, 403)
        response = post(self.client, "/api/users/create_user/", self.new_user(), bearer(self.staff))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="new.person").exists())

    def test_create_user_enforces_the_policy(self, _rights):
        body = self.new_user(password="weakpass", verify_password="weakpass")
        response = post(self.client, "/api/users/create_user/", body, bearer(self.root))
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.json()["password_errors"])
        body = self.new_user(password="New#Person2026x", verify_password="New#Person2026x")
        self.assertEqual(post(self.client, "/api/users/create_user/", body, bearer(self.root)).status_code, 400)

    def test_create_user_with_a_strong_password(self, _rights):
        response = post(self.client, "/api/users/create_user/", self.new_user(), bearer(self.root))
        self.assertEqual(response.status_code, 200, response.content)
        created = User.objects.get(username="new.person")
        self.assertTrue(created.check_password(STRONG_2))
        self.assertNotEqual(created.password, STRONG_2)  # stored hashed

    def test_page_grant_lets_hr_create_but_not_superusers(self, rights):
        rights.return_value = True
        response = post(self.client, "/api/users/create_user/", self.new_user(is_superuser=True),
                        bearer(self.hr))
        self.assertEqual(response.status_code, 403)
        response = post(self.client, "/api/users/create_user/", self.new_user(), bearer(self.hr))
        self.assertEqual(response.status_code, 200)
        response = post(self.client, "/api/users/create_user/",
                        self.new_user(username="boss2", erpid="902", is_superuser=True),
                        bearer(self.root))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.get(username="boss2").is_superuser)

    # ---- sign up ----------------------------------------------------------------
    def test_signup_never_makes_a_superuser(self, _rights):
        response = post(self.client, "/api/users/signup_user/", self.new_user(is_superuser=True))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(User.objects.get(username="new.person").is_superuser)

    def test_signup_enforces_the_policy(self, _rights):
        body = self.new_user(password="password123", verify_password="password123")
        response = post(self.client, "/api/users/signup_user/", body)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="new.person").exists())

    # ---- change password ----------------------------------------------------------
    def test_change_password_needs_a_session(self, _rights):
        body = {"user_id": self.staff.pk, "old_password": STRONG,
                "new_password1": STRONG_2, "new_password2": STRONG_2}
        self.assertEqual(post(self.client, "/api/users/change-password/", body).status_code, 401)

    def test_change_password_rules(self, _rights):
        url, me = "/api/users/change-password/", bearer(self.staff)
        wrong = {"old_password": "Wrong#Pass9xQ", "new_password1": STRONG_2, "new_password2": STRONG_2}
        self.assertEqual(post(self.client, url, wrong, me).status_code, 400)
        weak = {"old_password": STRONG, "new_password1": "short1!A", "new_password2": "short1!A"}
        self.assertIn("password_errors", post(self.client, url, weak, me).json())
        same = {"old_password": STRONG, "new_password1": STRONG, "new_password2": STRONG}
        self.assertIn("different from the current", post(self.client, url, same, me).json()["error"])
        personal = {"old_password": STRONG, "new_password1": "Plain#User9xQw!",
                    "new_password2": "Plain#User9xQw!"}
        self.assertEqual(post(self.client, url, personal, me).status_code, 400)
        mismatch = {"old_password": STRONG, "new_password1": STRONG_2, "new_password2": STRONG_2 + "x"}
        self.assertEqual(post(self.client, url, mismatch, me).status_code, 400)

        good = {"old_password": STRONG, "new_password1": STRONG_2, "new_password2": STRONG_2}
        self.assertEqual(post(self.client, url, good, me).status_code, 200)
        self.assertIsNotNone(authenticate(username="plain.user", password=STRONG_2))

    def test_change_password_only_changes_your_own_account(self, _rights):
        body = {"user_id": self.root.pk, "old_password": STRONG,
                "new_password1": STRONG_2, "new_password2": STRONG_2}
        post(self.client, "/api/users/change-password/", body, bearer(self.staff))
        self.root.refresh_from_db()
        self.assertTrue(self.root.check_password(STRONG))  # untouched
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password(STRONG_2))

    # ---- reset password -------------------------------------------------------------
    def test_reset_needs_an_administrator(self, _rights):
        url = f"/api/users/reset_password/{self.staff.pk}/"
        self.assertEqual(post(self.client, url).status_code, 403)
        self.assertEqual(post(self.client, url, {}, bearer(self.staff)).status_code, 403)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password(STRONG))

    def test_reset_generates_a_policy_password(self, _rights):
        response = post(self.client, f"/api/users/reset_password/{self.staff.pk}/", {}, bearer(self.root))
        self.assertEqual(response.status_code, 200)
        new_password = response.json()["password"]
        self.assertEqual(password_problems(new_password), [])
        self.assertNotEqual(new_password, self.staff.email)  # no longer the email address
        self.assertIsNotNone(authenticate(username="plain.user", password=new_password))

    def test_reset_to_a_chosen_password(self, _rights):
        url = f"/api/users/reset_password/{self.staff.pk}/"
        self.assertEqual(post(self.client, url, {"password": "weak"}, bearer(self.root)).status_code, 400)
        response = post(self.client, url, {"password": STRONG_2}, bearer(self.root))
        self.assertEqual(response.json()["password"], STRONG_2)
        self.assertIsNotNone(authenticate(username="plain.user", password=STRONG_2))

    def test_only_a_superuser_resets_a_superuser(self, rights):
        rights.return_value = True
        url = f"/api/users/reset_password/{self.root.pk}/"
        self.assertEqual(post(self.client, url, {}, bearer(self.hr)).status_code, 403)

    # ---- delete user ----------------------------------------------------------------
    def test_delete_needs_an_administrator_and_not_yourself(self, _rights):
        url = f"/api/users/delete_user/{self.staff.pk}/"
        self.assertEqual(post(self.client, url).status_code, 403)
        self.assertEqual(post(self.client, url, {}, bearer(self.staff)).status_code, 403)
        own = f"/api/users/delete_user/{self.root.pk}/"
        self.assertEqual(post(self.client, own, {}, bearer(self.root)).status_code, 400)
        self.assertEqual(post(self.client, url, {}, bearer(self.root)).status_code, 200)
        self.assertFalse(User.objects.filter(pk=self.staff.pk).exists())


# ---------------------------------------------------------------------------
# Locking after three wrong passwords
# ---------------------------------------------------------------------------

from notifications.models import Notification

from .lockout import MAX_FAILED_ATTEMPTS
from .models import AccountLockout


@mock.patch("users.views._has_menu_right", return_value=False)
class LockoutTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_user("root.admin", "root@ismo.gov.pk", STRONG,
                                             is_superuser=True)
        CustomUser.objects.create(authid=self.root.pk, erpid=1)
        self.user = User.objects.create_user("plain.user", "plain@ismo.gov.pk", STRONG)
        CustomUser.objects.create(authid=self.user.pk, erpid=700)

    def login(self, password, email="plain@ismo.gov.pk"):
        return post(self.client, "/api/users/login/", {"email": email, "password": password})

    def test_three_wrong_passwords_lock_the_account(self, _rights):
        first = self.login("Wrong#Pass1xQ")
        self.assertEqual(first.status_code, 401)
        self.assertEqual(first.json()["attempts_left"], 2)
        self.assertIn("2 attempts left", first.json()["error"])
        second = self.login("Wrong#Pass2xQ")
        self.assertEqual(second.json()["attempts_left"], 1)
        self.assertIn("1 attempt left", second.json()["error"])
        third = self.login("Wrong#Pass3xQ")
        self.assertEqual(third.status_code, 423)
        self.assertTrue(third.json()["locked"])
        self.assertTrue(AccountLockout.objects.get(user=self.user).is_locked)
        self.assertEqual(MAX_FAILED_ATTEMPTS, 3)

    def test_locked_account_refuses_the_right_password(self, _rights):
        for _ in range(3):
            self.login("Wrong#Pass1xQ")
        response = self.login(STRONG)
        self.assertEqual(response.status_code, 423)
        self.assertNotIn("user", response.json())

    def test_success_clears_the_count(self, _rights):
        self.login("Wrong#Pass1xQ")
        self.login("Wrong#Pass2xQ")
        self.assertEqual(self.login(STRONG).status_code, 200)
        self.assertEqual(AccountLockout.objects.get(user=self.user).failed_attempts, 0)
        # Two more misses do not lock: the count started again.
        self.login("Wrong#Pass1xQ")
        self.assertEqual(self.login("Wrong#Pass2xQ").status_code, 401)

    def test_user_is_notified_of_the_lock(self, _rights):
        for _ in range(3):
            self.login("Wrong#Pass1xQ")
        note = Notification.objects.get(recipient_erp_id=700)
        self.assertEqual((note.category, note.event), ("account", "locked"))
        self.assertIn("3 failed sign-in attempts", note.message)

    def test_unknown_email_is_not_counted(self, _rights):
        self.assertEqual(self.login(STRONG, email="nobody@ismo.gov.pk").status_code, 401)
        self.assertFalse(AccountLockout.objects.exclude(failed_attempts=0).exists())

    def test_admin_unlocks_and_user_is_told(self, _rights):
        for _ in range(3):
            self.login("Wrong#Pass1xQ")
        status = self.client.get("/api/users/account_status/", **bearer(self.root)).json()
        self.assertTrue(status[str(self.user.pk)]["is_locked"])
        self.assertEqual(status[str(self.user.pk)]["locked_reason"], "3 failed sign-in attempts")

        response = post(self.client, f"/api/users/unlock_user/{self.user.pk}/", {}, bearer(self.root))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.login(STRONG).status_code, 200)
        self.assertTrue(Notification.objects.filter(recipient_erp_id=700, event="unlocked").exists())

    def test_admin_locks_by_hand(self, _rights):
        response = post(self.client, f"/api/users/lock_user/{self.user.pk}/",
                        {"reason": "Left the organisation"}, bearer(self.root))
        self.assertEqual(response.status_code, 200)
        refused = self.login(STRONG)
        self.assertEqual(refused.status_code, 423)
        self.assertIn("locked by the system administrator", refused.json()["error"])
        record = AccountLockout.objects.get(user=self.user)
        self.assertEqual(record.locked_reason, "Left the organisation")
        self.assertEqual(record.locked_by, self.root.pk)

    def test_lock_controls_need_an_administrator(self, rights):
        for url in (f"/api/users/lock_user/{self.root.pk}/", f"/api/users/unlock_user/{self.root.pk}/"):
            self.assertEqual(post(self.client, url).status_code, 403)
            self.assertEqual(post(self.client, url, {}, bearer(self.user)).status_code, 403)
        self.assertEqual(self.client.get("/api/users/account_status/", **bearer(self.user)).status_code, 403)
        # Nobody locks their own account, and only a superuser locks a superuser.
        own = post(self.client, f"/api/users/lock_user/{self.root.pk}/", {}, bearer(self.root))
        self.assertEqual(own.status_code, 400)
        rights.return_value = True
        hr = User.objects.create_user("hr.admin", "hr@ismo.gov.pk", STRONG)
        response = post(self.client, f"/api/users/lock_user/{self.root.pk}/", {}, bearer(hr))
        self.assertEqual(response.status_code, 400)  # superusers are exempt

    def test_open_session_ends_when_locked(self, _rights):
        self.assertEqual(self.client.get("/api/users/session_check/", **bearer(self.user)).status_code, 200)
        post(self.client, f"/api/users/lock_user/{self.user.pk}/", {}, bearer(self.root))
        response = self.client.get("/api/users/session_check/", **bearer(self.user))
        self.assertEqual(response.status_code, 423)
        self.assertEqual(self.client.get("/api/users/session_check/").status_code, 401)

    def test_sign_in_problems_answer_instead_of_crashing(self, _rights):
        # No employee record behind the account: a clear refusal, not a 500.
        loner = User.objects.create_user("loner", "loner@ismo.gov.pk", STRONG)
        response = self.login(STRONG, email="loner@ismo.gov.pk")
        self.assertEqual(response.status_code, 403)
        # Two accounts on one email.
        User.objects.create_user("twin", "plain@ismo.gov.pk", STRONG)
        self.assertEqual(self.login(STRONG).status_code, 409)


@mock.patch("users.views._has_menu_right", return_value=False)
class SuperuserExemptionTests(TestCase):
    """Superusers are outside the lockout policy altogether."""

    def setUp(self):
        self.root = User.objects.create_user("root.admin", "root@ismo.gov.pk", STRONG,
                                             is_superuser=True)
        CustomUser.objects.create(authid=self.root.pk, erpid=1)
        self.other_root = User.objects.create_user("root.two", "root2@ismo.gov.pk", STRONG,
                                                   is_superuser=True)

    def login(self, password):
        return post(self.client, "/api/users/login/",
                    {"email": "root@ismo.gov.pk", "password": password})

    def test_wrong_passwords_never_lock_a_superuser(self, _rights):
        for attempt in range(6):
            response = self.login(f"Wrong#Pass{attempt}xQ")
            self.assertEqual(response.status_code, 401)
            self.assertNotIn("attempts_left", response.json())
            self.assertNotIn("locked", response.json())
        self.assertEqual(self.login(STRONG).status_code, 200)
        self.assertFalse(AccountLockout.objects.filter(user=self.root, is_locked=True).exists())
        self.assertFalse(AccountLockout.objects.filter(user=self.root).exclude(failed_attempts=0).exists())

    def test_superuser_cannot_be_locked_by_hand(self, _rights):
        response = post(self.client, f"/api/users/lock_user/{self.other_root.pk}/",
                        {"reason": "test"}, bearer(self.root))
        self.assertEqual(response.status_code, 400)
        self.assertIn("exempt", response.json()["error"])
        self.assertFalse(AccountLockout.objects.filter(user=self.other_root, is_locked=True).exists())

    def test_old_lock_does_not_stop_a_promoted_superuser(self, _rights):
        # Locked while an ordinary user, then made a superuser.
        AccountLockout.objects.create(user=self.root, is_locked=True, failed_attempts=3,
                                      locked_reason="3 failed sign-in attempts")
        self.assertEqual(self.login(STRONG).status_code, 200)
        self.assertEqual(
            self.client.get("/api/users/session_check/", **bearer(self.root)).status_code, 200
        )

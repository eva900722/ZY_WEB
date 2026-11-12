import json
from datetime import timedelta

from django.test import Client, TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.api import tests as api_tests
from apps.audit.models import AuditLog
from apps.notifications.models import Delivery


class CompanyAccountManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        api_tests.ApiMigrationTests.setUpTestData.__func__(cls)
        cls.peer = User.objects.create_user(
            username="peer.manager", role="company_admin", company=cls.company
        )

    def setUp(self):
        self.client.force_login(self.manager)

    def post(self, path, data):
        return self.client.post(
            "/api/" + path, json.dumps(data), content_type="application/json"
        )

    def test_create_forces_own_company_reporter_and_generates_temporary_password(self):
        for role in ("it_admin", "company_admin", "reporter"):
            response = self.post(
                "users/",
                {
                    "username": "Company." + role,
                    "display_name": "員工",
                    "role": role,
                    "company": self.foreign_company.pk,
                    "is_superuser": True,
                    "is_staff": True,
                },
            )
            self.assertEqual(response.status_code, 201, response.content)
            user = User.objects.get(pk=response.json()["user"]["id"])
            raw = response.json()["temporary_password"]
            self.assertEqual(user.role, "reporter")
            self.assertEqual(user.company_id, self.company.pk)
            self.assertFalse(user.is_superuser)
            self.assertFalse(user.is_staff)
            self.assertTrue(user.check_password(raw))
            self.assertTrue(user.must_change_password)
            self.assertLessEqual(
                user.temporary_expires_at, timezone.now() + timedelta(hours=24)
            )
            self.assertIn("no-store", response["Cache-Control"])
            detail = self.client.get(f"/api/users/{user.pk}/")
            self.assertNotIn(raw, detail.content.decode())
            self.assertTrue(
                AuditLog.objects.filter(
                    actor=self.manager, action="account.created", target=str(user.pk)
                ).exists()
            )
            self.assertNotIn(raw, str(list(AuditLog.objects.values("details"))))
        self.assertFalse(Delivery.objects.exists())
        duplicate = self.post(
            "users/",
            {"username": self.foreign.username.upper(), "display_name": "重複"},
        )
        self.assertEqual(duplicate.status_code, 400)
        invalid = self.post("users/", {"username": "!bad", "display_name": "錯誤"})
        self.assertEqual(invalid.status_code, 400)

    def test_scope_blocks_other_companies_managers_and_staff(self):
        ids = {x["id"] for x in self.client.get("/api/users/").json()["items"]}
        self.assertEqual(ids, {self.reporter.pk, self.other.pk})
        for target in (self.foreign, self.admin, self.manager, self.peer):
            self.assertEqual(
                self.client.get(f"/api/users/{target.pk}/").status_code, 404
            )
            self.assertEqual(
                self.post(
                    f"users/{target.pk}/", {"display_name": "forged"}
                ).status_code,
                404,
            )
            for action in ("temporary", "enable", "disable", "delete"):
                self.assertEqual(
                    self.post(
                        f"users/{target.pk}/action/", {"action": action}
                    ).status_code,
                    404,
                )
        self.foreign.refresh_from_db()
        self.assertTrue(self.foreign.check_password(api_tests.PASSWORD))
        self.assertTrue(self.foreign.is_active)
        self.assertIsNone(self.foreign.deleted_at)

    def test_edit_cannot_change_username_role_company_or_historical_snapshot(self):
        snapshot = dict(self.ticket.snapshot)
        response = self.post(
            f"users/{self.reporter.pk}/",
            {
                "username": "forged",
                "display_name": "新姓名",
                "role": "it_admin",
                "company": self.foreign_company.pk,
                "phone": "123",
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.reporter.refresh_from_db()
        self.assertEqual(self.reporter.role, "reporter")
        self.assertEqual(self.reporter.company_id, self.company.pk)
        self.assertEqual(self.reporter.username, "apireporter")
        self.assertEqual(self.reporter.display_name, "新姓名")
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.snapshot, snapshot)

    def test_reset_revokes_session_and_requires_password_change(self):
        old = Client()
        old.force_login(self.reporter)
        response = self.post(
            f"users/{self.reporter.pk}/action/", {"action": "temporary"}
        )
        self.assertEqual(response.status_code, 200)
        raw = response.json()["temporary_password"]
        self.assertEqual(old.get("/api/tickets/").status_code, 401)
        self.client.logout()
        self.assertEqual(
            self.post(
                "auth/login/", {"username": self.reporter.username, "password": raw}
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get("/api/tickets/").json()["code"], "password_change_required"
        )
        self.assertEqual(
            self.post(
                "auth/password/",
                {
                    "old_password": raw,
                    "new_password1": api_tests.NEW_PASSWORD,
                    "new_password2": api_tests.NEW_PASSWORD,
                },
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get("/api/tickets/").status_code, 200)
        self.client.logout()
        self.assertEqual(
            self.post(
                "auth/login/", {"username": self.reporter.username, "password": raw}
            ).status_code,
            400,
        )

    def test_disable_enable_reset_delete_preserves_history(self):
        snapshot = dict(self.ticket.snapshot)
        path = f"users/{self.reporter.pk}/action/"
        self.assertEqual(self.post(path, {"action": "disable"}).status_code, 200)
        self.assertEqual(self.post(path, {"action": "temporary"}).status_code, 400)
        self.assertEqual(self.post(path, {"action": "enable"}).status_code, 200)
        self.reporter.refresh_from_db()
        self.assertFalse(self.reporter.has_usable_password())
        response = self.post(path, {"action": "temporary"})
        self.assertEqual(response.status_code, 200)
        self.reporter.refresh_from_db()
        self.assertTrue(
            self.reporter.check_password(response.json()["temporary_password"])
        )
        self.assertEqual(self.post(path, {"action": "delete"}).status_code, 200)
        self.reporter.refresh_from_db()
        self.assertIsNotNone(self.reporter.deleted_at)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.reporter_id, self.reporter.pk)
        self.assertEqual(self.ticket.snapshot, snapshot)
        self.assertTrue(self.ticket.status_history.exists())
        self.assertEqual(self.post(path, {"action": "enable"}).status_code, 404)
        for action in ("disable", "enable", "temporary_password", "delete"):
            self.assertTrue(
                AuditLog.objects.filter(
                    actor=self.manager,
                    action="account." + action,
                    target=str(self.reporter.pk),
                ).exists()
            )

    def test_reporter_and_csrf_blocked_and_legacy_routes_scoped(self):
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.manager)
        self.assertEqual(
            csrf.post("/api/users/", {}, content_type="application/json").status_code,
            403,
        )
        self.assertEqual(
            csrf.post(
                f"/api/users/{self.reporter.pk}/action/", {"action": "temporary"}
            ).status_code,
            403,
        )
        response = self.client.post(
            "/accounts/users/new/",
            {
                "username": "legacy.worker",
                "display_name": "舊入口員工",
                "role": "it_admin",
                "company": self.foreign_company.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        legacy = User.objects.get(username="legacy.worker")
        self.assertEqual(
            (legacy.role, legacy.company_id), ("reporter", self.company.pk)
        )
        self.assertEqual(
            self.client.post(f"/accounts/users/{legacy.pk}/disable/").status_code, 302
        )
        legacy.refresh_from_db()
        self.assertFalse(legacy.is_active)
        for target in (self.foreign, self.admin, self.peer):
            self.assertEqual(
                self.client.post(f"/accounts/users/{target.pk}/temporary/").status_code,
                404,
            )
        self.client.force_login(self.reporter)
        self.assertEqual(
            self.post(
                "users/", {"username": "forbidden", "display_name": "forbidden"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                f"users/{self.other.pk}/action/", {"action": "temporary"}
            ).status_code,
            403,
        )

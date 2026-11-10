"""Targeted regressions for the Vue API migration, using the isolated MySQL test database."""

import json
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from django.db import connection
from apps.accounts.models import User
from apps.accounts.services import temporary_password, issue_token
from apps.companies.models import Company
from apps.forms.models import FormVersion
from apps.forms.services import publish
from apps.tickets.models import Ticket, Entry
from apps.tickets.services import create_ticket
from apps.notifications.models import Delivery
from apps.audit.models import AuditLog

PASSWORD = "Vue-Api-Test!839261"
NEW_PASSWORD = "Changed-Vue-Test!53729"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ApiMigrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="API測試揚發", code="apiyf")
        cls.foreign_company = Company.objects.create(name="API測試萬陽", code="apiwy")

        def user(name, role, company=None):
            return User.objects.create_user(
                username=name,
                display_name=name,
                password=PASSWORD,
                role=role,
                company=company,
                must_change_password=False,
            )

        cls.admin = user("apiadmin", "it_admin")
        cls.reporter = user("apireporter", "reporter", cls.company)
        cls.other = user("apiother", "reporter", cls.company)
        cls.manager = user("apimanager", "company_admin", cls.company)
        cls.foreign = user("apiforeign", "reporter", cls.foreign_company)
        cls.engineer = user("apiengineer", "engineer")
        cls.engineer2 = user("apiengineer2", "engineer")
        cls.version = FormVersion.objects.create(
            company=cls.company,
            number=1,
            fields=[],
            published_at=timezone.now(),
            created_by=cls.admin,
        )
        vb = FormVersion.objects.create(
            company=cls.foreign_company,
            number=1,
            fields=[],
            published_at=timezone.now(),
            created_by=cls.admin,
        )
        cls.ticket = create_ticket(
            cls.reporter,
            cls.company,
            cls.reporter,
            cls.version,
            {"title": "VueAPI報修", "description": "初始問題"},
            {},
        )
        cls.other_ticket = create_ticket(
            cls.other,
            cls.company,
            cls.other,
            cls.version,
            {"title": "其他人案件", "description": "問題"},
            {},
        )
        cls.foreign_ticket = create_ticket(
            cls.foreign,
            cls.foreign_company,
            cls.foreign,
            vb,
            {"title": "外公司機密", "description": "問題"},
            {},
        )

    def as_user(self, user):
        self.client.force_login(user)

    def post(self, url, data):
        return self.client.post(
            "/api/" + url, data=json.dumps(data), content_type="application/json"
        )

    def test_mysql_isolation(self):
        self.assertEqual(connection.vendor, "mysql")
        self.assertFalse(connection.mysql_is_mariadb)
        self.assertTrue(connection.settings_dict["NAME"].startswith("test_"))

    def test_anonymous_session_and_private_api_401(self):
        r = self.client.get("/api/auth/session/")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["user"])
        self.assertIn("csrf_token", r.json())
        self.assertIn("no-store", r["Cache-Control"])
        r = self.client.get("/api/tickets/")
        self.assertEqual(r.status_code, 401)
        self.assertIn("message", r.json())

    def test_anonymous_login_requires_csrf(self):
        c = Client(enforce_csrf_checks=True)
        r = c.post(
            "/api/auth/login/",
            json.dumps({"username": self.reporter.username, "password": PASSWORD}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 403)
        s = c.get("/api/auth/session/").json()
        r = c.post(
            "/api/auth/login/",
            json.dumps({"username": self.reporter.username, "password": PASSWORD}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=s["csrf_token"],
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["user"]["id"], self.reporter.pk)

    def test_failed_login_json_and_shared_lockout(self):
        for _ in range(5):
            self.assertEqual(
                self.post(
                    "auth/login/",
                    {"username": self.reporter.username, "password": "bad"},
                ).status_code,
                400,
            )
        self.assertEqual(
            self.post(
                "auth/login/",
                {"username": self.reporter.username, "password": PASSWORD},
            ).status_code,
            400,
        )

    def test_logout_and_password_change(self):
        self.as_user(self.reporter)
        r = self.post(
            "auth/password/",
            {
                "old_password": PASSWORD,
                "new_password1": NEW_PASSWORD,
                "new_password2": NEW_PASSWORD,
            },
        )
        self.assertEqual(r.status_code, 200)
        self.reporter.refresh_from_db()
        self.assertTrue(self.reporter.check_password(NEW_PASSWORD))
        self.assertEqual(self.post("auth/logout/", {}).status_code, 200)
        self.assertEqual(self.client.get("/api/tickets/").status_code, 401)

    def test_temporary_password_gate_returns_json(self):
        raw = temporary_password(self.admin, self.reporter)
        self.post("auth/login/", {"username": self.reporter.username, "password": raw})
        r = self.client.get("/api/tickets/")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], "password_change_required")
        self.assertEqual(self.client.get("/api/auth/session/").status_code, 200)
        r = self.post(
            "auth/password/",
            {
                "old_password": raw,
                "new_password1": NEW_PASSWORD,
                "new_password2": NEW_PASSWORD,
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/tickets/").status_code, 200)

    def test_disabled_session_and_reset_revoked(self):
        self.as_user(self.reporter)
        User.objects.filter(pk=self.reporter.pk).update(is_active=False)
        self.assertEqual(self.client.get("/api/tickets/").status_code, 401)

    def test_reporter_manager_and_engineer_scopes(self):
        for user, count in [
            (self.reporter, 1),
            (self.manager, 2),
            (self.engineer, 0),
            (self.admin, 3),
        ]:
            self.as_user(user)
            r = self.client.get("/api/tickets/")
            self.assertEqual(r.json()["total"], count)

    def test_cross_company_detail_and_export_denied(self):
        self.as_user(self.manager)
        self.assertEqual(
            self.client.get(f"/api/tickets/{self.foreign_ticket.pk}/").status_code, 404
        )
        self.assertEqual(
            self.client.get(f"/reports/xlsx/{self.foreign_ticket.pk}/").status_code, 404
        )
        self.assertEqual(
            self.client.get(
                "/api/tickets/?company=" + str(self.foreign_company.pk)
            ).json()["total"],
            0,
        )

    def test_internal_notes_not_serialized_to_customer(self):
        Entry.objects.create(
            ticket=self.ticket, author=self.admin, body="INTERNAL_SECRET", internal=True
        )
        self.as_user(self.reporter)
        r = self.client.get(f"/api/tickets/{self.ticket.pk}/")
        self.assertNotIn("INTERNAL_SECRET", r.content.decode())
        self.as_user(self.admin)
        r = self.client.get(f"/api/tickets/{self.ticket.pk}/")
        self.assertIn("INTERNAL_SECRET", r.content.decode())

    def test_metadata_does_not_expose_foreign_reporters(self):
        self.as_user(self.reporter)
        r = self.client.get(
            "/api/tickets/meta/?company=" + str(self.foreign_company.pk)
        )
        self.assertEqual(r.json()["company"], self.company.pk)
        self.assertEqual(len(r.json()["reporters"]), 1)
        self.as_user(self.engineer)
        self.assertEqual(self.client.get("/api/tickets/meta/").status_code, 403)

    def test_create_ticket_ignores_forged_company_and_reporter(self):
        self.as_user(self.reporter)
        r = self.post(
            "tickets/",
            {
                "title": "新案件",
                "description": "說明",
                "reporter": self.foreign.pk,
                "company": self.foreign_company.pk,
                "form_version": self.version.pk,
            },
        )
        self.assertEqual(r.status_code, 201)
        t = Ticket.objects.get(pk=r.json()["id"])
        self.assertEqual(t.company, self.company)
        self.assertEqual(t.reporter, self.reporter)

    def test_form_errors_have_json_fields(self):
        self.as_user(self.reporter)
        r = self.post(
            "tickets/", {"company": self.company.pk, "form_version": self.version.pk}
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("title", r.json()["fields"])

    def test_old_schema_rejected_without_creating_ticket(self):
        v = FormVersion.objects.create(
            company=self.company, number=2, fields=[], created_by=self.admin
        )
        publish(self.admin, v, True)
        self.as_user(self.reporter)
        r = self.post(
            "tickets/",
            {
                "title": "舊版案件",
                "description": "保留",
                "form_version": self.version.pk,
            },
        )
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["code"], "form_changed")
        self.assertEqual(Ticket.objects.count(), 3)

    def test_schema_status_and_unmapped_values(self):
        v = FormVersion.objects.create(
            company=self.company, number=2, fields=[], created_by=self.admin
        )
        publish(self.admin, v, True)
        self.as_user(self.reporter)
        r = self.client.get(f"/api/tickets/meta/?version={self.version.pk}")
        self.assertFalse(r.json()["accepted"])
        r = self.post(
            "tickets/",
            {
                "title": "新版案件",
                "description": "內容",
                "form_version": v.pk,
                "unmapped": [["舊欄位", "保留值"]],
            },
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(
            Ticket.objects.get(pk=r.json()["id"]).answers["_unmapped"],
            [["舊欄位", "保留值"]],
        )

    def test_assignment_and_reassignment_revoke_access(self):
        self.as_user(self.admin)
        r = self.post(
            f"tickets/{self.ticket.pk}/",
            {
                "action": "assign",
                "revision": 1,
                "engineer": self.engineer.pk,
                "reason": "派工",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.as_user(self.engineer)
        self.assertEqual(
            self.client.get(f"/api/tickets/{self.ticket.pk}/").status_code, 200
        )
        self.as_user(self.admin)
        r = self.post(
            f"tickets/{self.ticket.pk}/",
            {
                "action": "assign",
                "revision": 2,
                "engineer": self.engineer2.pk,
                "reason": "改派",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.as_user(self.engineer)
        self.assertEqual(
            self.client.get(f"/api/tickets/{self.ticket.pk}/").status_code, 404
        )
        self.assertEqual(self.client.get("/api/notifications/").json()["total"], 0)

    def test_reporter_cannot_assign_or_post_internal_note(self):
        self.as_user(self.reporter)
        for data in [
            {
                "action": "assign",
                "revision": 1,
                "engineer": self.engineer.pk,
                "reason": "錯誤",
            },
            {"action": "entry", "revision": 1, "body": "秘密", "internal": True},
        ]:
            self.assertEqual(
                self.post(f"tickets/{self.ticket.pk}/", data).status_code, 403
            )

    def test_stale_revision_conflict_preserves_record(self):
        self.as_user(self.reporter)
        data = {"action": "entry", "revision": 1, "body": "補充", "internal": False}
        self.assertEqual(self.post(f"tickets/{self.ticket.pk}/", data).status_code, 200)
        self.assertEqual(self.post(f"tickets/{self.ticket.pk}/", data).status_code, 409)
        self.assertEqual(self.ticket.entries.count(), 1)

    def test_company_manager_cannot_create_or_reset_user(self):
        self.as_user(self.manager)
        self.assertEqual(
            self.post("users/", {"username": "unauthorized"}).status_code, 403
        )
        self.assertEqual(
            self.post(
                f"users/{self.reporter.pk}/action/", {"action": "temporary"}
            ).status_code,
            403,
        )

    def test_admin_create_user_returns_temporary_once_no_cache(self):
        self.as_user(self.admin)
        r = self.post(
            "users/",
            {
                "username": "newvue",
                "display_name": "新人",
                "role": "reporter",
                "company": self.company.pk,
            },
        )
        self.assertEqual(r.status_code, 201)
        self.assertIn("temporary_password", r.json())
        self.assertIn("no-store", r["Cache-Control"])
        u = User.objects.get(username="newvue")
        self.assertTrue(u.must_change_password)
        r = self.client.get(f"/api/users/{u.pk}/")
        self.assertNotIn("temporary_password", r.json())

    def test_last_admin_cannot_disable(self):
        self.as_user(self.admin)
        self.assertEqual(
            self.post(
                f"users/{self.admin.pk}/action/", {"action": "disable"}
            ).status_code,
            400,
        )

    def test_company_creation_publishes_default_form(self):
        self.as_user(self.admin)
        r = self.post(
            "companies/",
            {
                "name": "新公司",
                "code": "newapi",
                "contact": "",
                "is_active": True,
                "locations": "一樓\n二樓",
                "emails": "",
            },
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(
            FormVersion.objects.filter(company_id=r.json()["id"]).count(), 1
        )

    def test_versions_admin_only_and_immutable(self):
        self.as_user(self.manager)
        self.assertEqual(self.client.get("/api/versions/").status_code, 403)
        self.as_user(self.admin)
        r = self.post("versions/", {"company": self.company.pk, "fields": []})
        self.assertEqual(r.status_code, 200)
        vid = r.json()["id"]
        self.assertEqual(
            self.post(
                f"versions/{vid}/",
                {"company": self.company.pk, "action": "publish", "policy": "grace"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.post(
                f"versions/{vid}/", {"company": self.company.pk, "fields": []}
            ).status_code,
            400,
        )

    def test_audit_only_admin(self):
        self.as_user(self.reporter)
        self.assertEqual(self.client.get("/api/audit/").status_code, 403)
        self.as_user(self.admin)
        self.assertEqual(self.client.get("/api/audit/").status_code, 200)

    def test_forgot_no_email_generic(self):
        before = Delivery.objects.count()
        r = self.post("auth/forgot/", {"username": self.reporter.username})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Delivery.objects.count(), before)

    def test_email_token_verification_one_time(self):
        self.reporter.email = "vue@example.invalid"
        self.reporter.save()
        raw = issue_token(self.reporter, "verify")
        self.assertEqual(
            self.client.get(f"/api/auth/token/{raw}/").json()["purpose"], "verify"
        )
        self.assertEqual(self.post(f"auth/token/{raw}/", {}).status_code, 200)
        self.assertEqual(self.post(f"auth/token/{raw}/", {}).status_code, 400)

    def test_token_path_redacted_in_denial_log(self):
        self.as_user(self.admin)
        self.client.get("/api/auth/token/secret-should-not-be-logged/unknown/")
        self.assertNotIn(
            "secret-should-not-be-logged", str(list(AuditLog.objects.values()))
        )

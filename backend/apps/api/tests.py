"""Targeted regressions for the Vue API migration, using the isolated MySQL test database."""

import json
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from django.db import connection
from apps.accounts.models import User
from apps.accounts.services import temporary_password, digest
from apps.companies.models import Company
from apps.forms.models import FormVersion
from apps.forms.services import publish
from apps.tickets.models import Ticket, Entry
from apps.tickets.services import create_ticket
from apps.notifications.models import Delivery
from apps.audit.models import AuditLog
from common.permissions import tickets_for

PASSWORD = "Vue-Api-Test!839261"
NEW_PASSWORD = "Changed-Vue-Test!53729"


def legacy_token(user, purpose):
    import secrets
    from datetime import timedelta
    from apps.accounts.models import ActionToken
    raw = secrets.token_urlsafe(32)
    ActionToken.objects.create(user=user, purpose=purpose, digest=digest(raw), email=user.email, expires_at=timezone.now() + timedelta(minutes=30))
    return raw


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
        cls.engineer = user("apiengineer", "it_admin")
        cls.engineer2 = user("apiengineer2", "it_admin")
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
            (self.engineer, 3),
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
        self.assertEqual(self.client.get("/api/tickets/meta/").status_code, 200)

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

    def test_takeover_and_handover_keep_shared_staff_access(self):
        self.as_user(self.admin)
        url = f"tickets/{self.ticket.pk}/"
        self.assertEqual(self.post(url, {"action": "assign", "revision": 1, "engineer": self.engineer.pk, "reason": "不可先派工"}).status_code, 409)
        self.assertEqual(self.post(url, {"action": "claim", "revision": 1}).status_code, 200)
        self.assertEqual(self.post(url, {"action": "assign", "revision": 2, "engineer": self.engineer.pk, "reason": "交接"}).status_code, 200)
        self.as_user(self.engineer2)
        self.assertEqual(self.client.get("/api/" + url).status_code, 200)
        self.assertEqual(self.post(url, {"action": "entry", "revision": 3, "body": "同事協助", "internal": True}).status_code, 200)
        self.assertEqual(self.client.get("/api/audit/").status_code, 200)

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

    def test_company_manager_can_create_and_reset_reporter(self):
        self.as_user(self.manager)
        self.assertEqual(
            self.post("users/", {"username": "companyworker", "display_name": "本公司員工"}).status_code, 201
        )
        self.assertEqual(
            self.post(
                f"users/{self.reporter.pk}/action/", {"action": "temporary"}
            ).status_code,
            200,
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
        User.objects.filter(pk__in=[self.engineer.pk, self.engineer2.pk]).update(is_active=False)
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

    def test_old_email_tokens_and_services_are_disabled(self):
        from apps.accounts.services import issue_token, consume_token
        from django.core.exceptions import ValidationError
        self.reporter.email = "old@example.invalid"
        self.reporter.email_verified_at = timezone.now()
        self.reporter.save()
        original_password = self.reporter.password
        before = Delivery.objects.count()
        for purpose in ["verify", "reset"]:
            raw = legacy_token(self.reporter, purpose)
            self.assertEqual(self.client.get(f"/api/auth/token/{raw}/").status_code, 410)
            self.assertEqual(self.post(f"auth/token/{raw}/", {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD}).status_code, 410)
            with self.assertRaises(ValidationError):
                consume_token(raw, NEW_PASSWORD)
            with self.assertRaises(ValidationError):
                issue_token(self.reporter, purpose)
        self.as_user(self.reporter)
        self.assertEqual(self.post("auth/verify/", {}).status_code, 410)
        self.assertEqual(self.client.post("/accounts/verify/").status_code, 410)
        self.assertEqual(self.post("auth/forgot/", {"username": self.reporter.username}).status_code, 200)
        self.assertEqual(Delivery.objects.count(), before)
        self.reporter.refresh_from_db()
        self.assertEqual(self.reporter.password, original_password)

    def test_token_path_redacted_in_denial_log(self):
        self.as_user(self.admin)
        self.client.get("/api/auth/token/secret-should-not-be-logged/unknown/")
        self.assertNotIn(
            "secret-should-not-be-logged", str(list(AuditLog.objects.values()))
        )

    def test_staff_claims_self_and_all_staff_keep_access(self):
        self.as_user(self.engineer)
        url = f"tickets/{self.foreign_ticket.pk}/"
        before = self.client.get("/api/" + url).json()
        self.assertTrue(before["can_claim"])
        self.assertTrue(before["can_comment"])
        response = self.post(url, {"action": "claim", "revision": 1, "engineer": self.engineer2.pk})
        self.assertEqual(response.status_code, 200)
        self.foreign_ticket.refresh_from_db()
        self.assertEqual(self.foreign_ticket.engineer_id, self.engineer.pk)
        self.assertEqual(self.foreign_ticket.status, "processing")
        self.assertEqual(self.foreign_ticket.revision, 2)
        self.assertEqual(self.foreign_ticket.assignments.count(), 1)
        self.assertFalse(response.json()["can_claim"])
        self.as_user(self.engineer2)
        self.assertEqual(self.client.get("/api/" + url).status_code, 200)
        self.assertEqual(self.post(url, {"action": "claim", "revision": 2}).status_code, 409)
        self.assertEqual(self.client.get(f"/reports/xlsx/{self.foreign_ticket.pk}/").status_code, 200)
        self.assertEqual(self.post(url, {"action": "status", "revision": 2, "status": "waiting", "reason": "同事協助追蹤"}).status_code, 200)

    def test_claim_rejects_customer_inactive_and_stale_revision(self):
        url = f"tickets/{self.ticket.pk}/"
        for user in [self.reporter, self.manager]:
            self.as_user(user)
            self.assertEqual(self.post(url, {"action": "claim", "revision": 1}).status_code, 403)
        self.as_user(self.engineer)
        self.assertEqual(self.post(url, {"action": "claim", "revision": 99}).status_code, 409)
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.engineer_id)
        User.objects.filter(pk=self.engineer.pk).update(is_active=False)
        self.assertEqual(self.post(url, {"action": "claim", "revision": 1}).status_code, 401)

    def test_new_company_pending_ticket_notifies_all_active_engineers(self):
        from apps.notifications.models import Notification
        User.objects.filter(pk=self.engineer2.pk).update(is_active=False)
        company = Company.objects.create(name="新增客戶", code="autoclaim")
        reporter = User.objects.create_user(username="newreporter", role="reporter", company=company, must_change_password=False)
        version = FormVersion.objects.create(company=company, number=1, fields=[], published_at=timezone.now(), created_by=self.admin)
        ticket = create_ticket(reporter, company, reporter, version, {"title": "新公司報修", "description": "不需逐一授權"}, {})
        recipients = set(Notification.objects.filter(ticket=ticket).values_list("user_id", flat=True))
        self.assertIn(self.engineer.pk, recipients)
        self.assertIn(self.admin.pk, recipients)
        self.assertNotIn(self.engineer2.pk, recipients)
        self.as_user(self.engineer)
        self.assertTrue(self.client.get(f"/api/tickets/{ticket.pk}/").json()["can_claim"])

    def test_unified_staff_role_choices_and_management(self):
        self.as_user(self.engineer)
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["roles"], [
            {"value": "reporter", "label": "公司報修者"},
            {"value": "company_admin", "label": "公司管理者"},
            {"value": "it_admin", "label": "贊耀公司人員"},
        ])
        self.assertEqual(self.engineer.get_role_display(), "贊耀公司人員")
        self.assertEqual(self.client.get("/api/companies/").status_code, 200)
        response = self.post("users/", {"username": "zynewstaff", "display_name": "同事", "role": "it_admin", "company": ""})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.post("users/", {"username": "oldengineer", "display_name": "舊角色", "role": "engineer", "company": ""}).status_code, 400)

    def test_mark_all_notifications_read_across_pages_with_scope(self):
        from apps.notifications.models import Notification
        from datetime import timedelta
        Notification.objects.all().delete()
        visible = Notification.objects.bulk_create([
            Notification(user=self.reporter, ticket=self.ticket, message=f"通知{i}") for i in range(30)
        ])
        visible = list(Notification.objects.filter(user=self.reporter))
        general = Notification.objects.create(user=self.reporter, message="一般通知")
        hidden = Notification.objects.create(user=self.reporter, ticket=self.foreign_ticket, message="無權查看案件")
        someone_else = Notification.objects.create(user=self.other, ticket=self.other_ticket, message="他人通知")
        old_time = timezone.now() - timedelta(days=1)
        already = Notification.objects.create(user=self.reporter, ticket=self.ticket, message="已讀通知", read_at=old_time)
        self.as_user(self.reporter)
        self.assertEqual(self.client.get("/api/notifications/").json()["pages"], 2)
        self.assertEqual(self.client.get("/api/notifications/read-all/").status_code, 405)
        self.assertEqual(Notification.objects.filter(pk__in=[n.pk for n in visible], read_at__isnull=True).count(), 30)
        response = self.post("notifications/read-all/", {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["updated"], 31)
        self.assertEqual(self.client.get("/api/notifications/").json()["unread"], 0)
        for item in [*visible, general]:
            item.refresh_from_db()
            self.assertIsNotNone(item.read_at)
        for item in [hidden, someone_else]:
            item.refresh_from_db()
            self.assertIsNone(item.read_at)
        already.refresh_from_db()
        self.assertEqual(already.read_at, old_time)
        self.assertEqual(self.post("notifications/read-all/", {}).json()["updated"], 0)
        new = Notification.objects.create(user=self.reporter, ticket=self.ticket, message="稍後新增")
        self.assertIsNone(new.read_at)
        self.assertEqual(self.client.get("/api/notifications/").json()["unread"], 1)

    def test_mark_all_notifications_requires_login_and_csrf(self):
        self.assertEqual(self.post("notifications/read-all/", {}).status_code, 401)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.reporter)
        self.assertEqual(client.post("/api/notifications/read-all/", {}, content_type="application/json").status_code, 403)
        token = client.get("/api/auth/session/").json()["csrf_token"]
        self.assertEqual(client.post("/api/notifications/read-all/", {}, content_type="application/json", HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_mark_all_notifications_for_each_role_only_changes_own(self):
        from apps.notifications.models import Notification
        for user in [self.reporter, self.manager, self.admin, self.engineer]:
            mine = Notification.objects.create(user=user, message="我的一般通知")
            other = Notification.objects.create(user=self.foreign, message="別人的通知")
            self.as_user(user)
            self.assertEqual(self.post("notifications/read-all/", {}).status_code, 200)
            mine.refresh_from_db()
            other.refresh_from_db()
            self.assertIsNotNone(mine.read_at)
            self.assertIsNone(other.read_at)

    def test_profile_edits_only_own_allowed_fields_and_keeps_ticket_snapshot(self):
        from copy import deepcopy
        before = deepcopy(self.ticket.snapshot)
        other_name = self.other.display_name
        self.as_user(self.reporter)
        self.assertEqual(self.client.get("/api/auth/profile/").status_code, 200)
        response = self.post("auth/profile/", {
            "display_name": "我的新姓名", "phone": "02-123#8", "mobile": "0912345678", "email": "new@example.invalid",
            "id": self.other.pk, "username": "forged", "role": "it_admin", "company": self.foreign_company.pk,
            "staff_id": "forged", "department": "forged", "office": "forged", "is_active": False,
        })
        self.assertEqual(response.status_code, 200)
        self.reporter.refresh_from_db()
        self.assertEqual(self.reporter.display_name, "我的新姓名")
        self.assertEqual(self.reporter.phone, "02-123#8")
        self.assertEqual(self.reporter.role, "reporter")
        self.assertEqual(self.reporter.username, "apireporter")
        self.assertEqual(self.reporter.company_id, self.company.pk)
        self.assertEqual(self.reporter.staff_id, "")
        self.assertEqual(self.reporter.department, "")
        self.assertEqual(self.reporter.office, "")
        self.assertTrue(self.reporter.is_active)
        self.other.refresh_from_db()
        self.assertEqual(self.other.display_name, other_name)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.snapshot, before)
        audit = AuditLog.objects.get(action="account.profile_updated")
        self.assertEqual(audit.actor_id, self.reporter.pk)
        self.assertIn("email", audit.details["fields"])
        self.assertNotIn("new@example.invalid", str(audit.details))

    def test_profile_email_change_sends_progress_without_verification(self):
        self.reporter.email = "old@example.invalid"
        self.reporter.save()
        old = legacy_token(self.reporter, "reset")
        self.as_user(self.reporter)
        response = self.post("auth/profile/", {"display_name": self.reporter.display_name, "phone": "", "mobile": "", "email": "new@example.invalid"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(f"/api/auth/token/{old}/").status_code, 410)
        before = Delivery.objects.count()
        self.post("auth/forgot/", {"username": self.reporter.username})
        self.assertEqual(Delivery.objects.count(), before)
        from apps.tickets.services import claim
        claim(self.admin, self.ticket.pk, self.ticket.revision)
        self.assertTrue(Delivery.objects.filter(recipient="new@example.invalid").exists())
        self.assertFalse(Delivery.objects.filter(recipient="old@example.invalid").exists())

    def test_profile_unchanged_email_preserves_verification_and_blank_clears(self):
        self.reporter.email = "same@example.invalid"
        original = self.reporter.email_verified_at = timezone.now()
        self.reporter.save()
        self.as_user(self.reporter)
        data = {"display_name": "另一姓名", "phone": "", "mobile": "", "email": self.reporter.email}
        self.assertEqual(self.post("auth/profile/", data).status_code, 200)
        self.reporter.refresh_from_db()
        self.assertEqual(self.reporter.email_verified_at, original)
        data["email"] = ""
        self.assertEqual(self.post("auth/profile/", data).status_code, 200)
        self.reporter.refresh_from_db()
        self.assertEqual(self.reporter.email, "")
        self.assertIsNone(self.reporter.email_verified_at)

    def test_profile_validation_all_roles_and_noop(self):
        for user in [self.reporter, self.manager, self.admin]:
            self.as_user(user)
            data = {"display_name": user.display_name, "email": "", "phone": "", "mobile": ""}
            self.assertEqual(self.post("auth/profile/", data).status_code, 200)
        self.assertFalse(AuditLog.objects.filter(action="account.profile_updated").exists())
        self.assertEqual(self.post("auth/profile/", {"display_name": "", "email": "bad-address"}).status_code, 400)

    def test_profile_requires_login_csrf_and_forced_password_change(self):
        self.assertEqual(self.client.get("/api/auth/profile/").status_code, 401)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.reporter)
        self.assertEqual(client.post("/api/auth/profile/", {}, content_type="application/json").status_code, 403)
        self.as_user(self.reporter)
        User.objects.filter(pk=self.reporter.pk).update(must_change_password=True)
        for response in [self.client.get("/api/auth/profile/"), self.post("auth/profile/", {"display_name": "繞過"})]:
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["code"], "password_change_required")

    def test_admin_temporary_reset_revokes_old_session_and_forces_password_change(self):
        old_session = Client()
        old_session.force_login(self.reporter)
        self.as_user(self.admin)
        response = self.post(f"users/{self.reporter.pk}/action/", {"action": "temporary"})
        self.assertEqual(response.status_code, 200)
        raw = response.json()["temporary_password"]
        self.assertEqual(old_session.get("/api/tickets/").status_code, 401)
        self.client.logout()
        self.assertEqual(self.post("auth/login/", {"username": self.reporter.username, "password": PASSWORD}).status_code, 400)
        self.assertEqual(self.post("auth/login/", {"username": self.reporter.username, "password": raw}).status_code, 200)
        for url in ["/api/tickets/", "/api/auth/profile/"]:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.post("auth/password/", {"old_password": raw, "new_password1": raw, "new_password2": raw}).status_code, 400)
        self.assertEqual(self.post("auth/password/", {"old_password": raw, "new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD}).status_code, 200)
        self.assertEqual(self.client.get("/api/tickets/").status_code, 200)
        self.client.logout()
        self.assertEqual(self.post("auth/login/", {"username": self.reporter.username, "password": raw}).status_code, 400)
        self.assertEqual(self.post("auth/login/", {"username": self.reporter.username, "password": NEW_PASSWORD}).status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action="account.temporary_password").exists())
        self.assertNotIn(raw, str(list(AuditLog.objects.values())))

    def test_expired_temporary_password_cannot_login(self):
        from datetime import timedelta
        raw = temporary_password(self.admin, self.reporter)
        User.objects.filter(pk=self.reporter.pk).update(temporary_expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.post("auth/login/", {"username": self.reporter.username, "password": raw}).status_code, 400)

import asyncore
import json
import smtpd
import threading
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.api import tests as api_tests
from apps.audit.models import AuditLog
from apps.notifications.configuration import decrypt_password, mail_connection
from apps.notifications.models import Delivery, SystemSettings
from apps.notifications.services import deliver_batch

KEY = Fernet.generate_key().decode()


@override_settings(
    SETTINGS_ENCRYPTION_KEY=KEY,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class SystemSettingsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        api_tests.ApiMigrationTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.client.force_login(self.admin)

    def post(self, path, data):
        return self.client.post(
            "/api/" + path, json.dumps(data), content_type="application/json"
        )

    def smtp(self, **changes):
        return (
            {
                "section": "mail",
                "revision": 0,
                "smtp_host": "msr.hinet.net",
                "smtp_port": 587,
                "smtp_security": "starttls",
                "smtp_auth": True,
                "smtp_username": "sender@example.com",
                "smtp_password": "Dummy-smtp-secret!",
                "sender_email": "sender@example.com",
                "sender_name": "測試寄件者",
            }
            | changes
        )

    def test_permissions_csrf_and_temporary_password_gate(self):
        self.client.logout()
        self.assertEqual(self.client.get("/api/system-settings/").status_code, 401)
        for user in (self.reporter, self.manager):
            self.client.force_login(user)
            for path in ("system-settings/", "system-settings/test-mail/"):
                self.assertEqual(self.post(path, {}).status_code, 403)
                self.assertEqual(self.client.get("/api/" + path).status_code, 403)
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.admin)
        self.assertEqual(
            c.post(
                "/api/system-settings/", {}, content_type="application/json"
            ).status_code,
            403,
        )
        self.admin.must_change_password = True
        self.admin.save()
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get("/api/system-settings/").json()["code"],
            "password_change_required",
        )

    def test_encrypted_secret_masked_preserved_changed_and_audited(self):
        response = self.post("system-settings/", self.smtp())
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn("Dummy-smtp-secret!", response.content.decode())
        obj = SystemSettings.objects.get()
        encrypted = obj.smtp_password_encrypted
        self.assertNotIn("Dummy-smtp-secret!", encrypted)
        self.assertEqual(decrypt_password(encrypted), "Dummy-smtp-secret!")
        self.assertTrue(response.json()["password_set"])
        response = self.post(
            "system-settings/", self.smtp(revision=1, smtp_password="")
        )
        self.assertEqual(response.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(obj.smtp_password_encrypted, encrypted)
        response = self.post(
            "system-settings/", self.smtp(revision=2, smtp_password="Replaced-secret!")
        )
        self.assertEqual(response.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(
            decrypt_password(obj.smtp_password_encrypted), "Replaced-secret!"
        )
        self.assertNotIn(
            "Dummy-smtp-secret!", str(list(AuditLog.objects.values("details")))
        )
        self.assertNotIn(
            "Replaced-secret!", str(list(AuditLog.objects.values("details")))
        )

    def test_validation_revision_and_no_partial_save(self):
        for changes in (
            {"smtp_port": 0},
            {"smtp_security": "FTP"},
            {"sender_email": "bad"},
            {"smtp_username": ""},
            {"sender_name": "x\r\nBcc: victim@example.com"},
        ):
            self.assertEqual(
                self.post("system-settings/", self.smtp(**changes)).status_code, 400
            )
        self.assertFalse(SystemSettings.objects.exists())
        self.assertEqual(self.post("system-settings/", self.smtp()).status_code, 200)
        self.assertEqual(
            self.post(
                "system-settings/", self.smtp(smtp_host="changed.example.com")
            ).status_code,
            409,
        )
        self.assertEqual(SystemSettings.objects.get().smtp_host, "msr.hinet.net")
        with override_settings(SETTINGS_ENCRYPTION_KEY=""):
            self.assertEqual(
                self.post("system-settings/", self.smtp(revision=1)).status_code, 400
            )
        self.assertEqual(SystemSettings.objects.get().revision, 1)

    def test_basic_public_fields_and_environment_fallback(self):
        with override_settings(
            EMAIL_HOST="env.example.com", EMAIL_HOST_PASSWORD="environment-secret"
        ):
            response = self.client.get("/api/system-settings/").json()
            self.assertEqual(response["smtp_host"], "env.example.com")
            self.assertTrue(response["password_set"])
        response = self.post(
            "system-settings/",
            {
                "section": "basic",
                "revision": 0,
                "platform_name": "測試服務平台",
                "company_name": "測試公司",
                "contact_phone": "02-12345678",
                "contact_email": "help@example.com",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SystemSettings.objects.get().smtp_override)
        self.client.logout()
        public = self.client.get("/api/auth/session/").json()["platform"]
        self.assertEqual(public["platform_name"], "測試服務平台")
        self.assertEqual(
            set(public),
            {"platform_name", "company_name", "contact_phone", "contact_email"},
        )
        with patch("apps.notifications.configuration.get_connection") as connection:
            mail_connection()
            connection.assert_called_once_with()

    def test_connection_uses_current_tls_ssl_and_authenticated_settings(self):
        self.post("system-settings/", self.smtp())
        for security, tls, ssl in (
            ("starttls", True, False),
            ("ssl", False, True),
            ("none", False, False),
        ):
            SystemSettings.objects.update(smtp_security=security)
            with patch("apps.notifications.configuration.get_connection") as factory:
                mail_connection()
                self.assertEqual(factory.call_args.kwargs["use_tls"], tls)
                self.assertEqual(factory.call_args.kwargs["use_ssl"], ssl)
                self.assertEqual(
                    factory.call_args.kwargs["password"], "Dummy-smtp-secret!"
                )
        with (
            override_settings(SETTINGS_ENCRYPTION_KEY=Fernet.generate_key().decode()),
            self.assertRaisesMessage(Exception, "無法解密"),
        ):
            mail_connection()

    def test_test_message_queue_status_and_worker_retry_sanitizes_failure(self):
        self.assertEqual(
            self.post(
                "system-settings/test-mail/", {"recipient": "x@example.com"}
            ).status_code,
            400,
        )
        self.post("system-settings/", self.smtp())
        self.assertEqual(
            self.post("system-settings/test-mail/", {"recipient": "bad"}).status_code,
            400,
        )
        response = self.post(
            "system-settings/test-mail/", {"recipient": "x@example.com"}
        )
        self.assertEqual(response.status_code, 201)
        pk = response.json()["id"]
        with patch(
            "apps.notifications.services.send_mail",
            side_effect=RuntimeError("sensitive credentials"),
        ):
            self.assertEqual(deliver_batch(), 1)
        item = Delivery.objects.get(pk=pk)
        self.assertEqual(item.status, "pending")
        self.assertEqual(item.last_error, "RuntimeError")
        self.assertGreater(item.next_attempt_at, timezone.now())
        Delivery.objects.filter(pk=pk).update(
            attempts=4, next_attempt_at=timezone.now()
        )
        with patch(
            "apps.notifications.services.send_mail",
            side_effect=RuntimeError("sensitive credentials"),
        ):
            deliver_batch()
        status = self.client.get(f"/api/system-settings/test-mail/{pk}/").json()
        self.assertEqual(status["status"], "failed")
        self.assertNotIn("sensitive", str(status))
        normal = Delivery.objects.create(
            recipient="normal@example.com",
            subject="normal",
            body="body",
            next_attempt_at=timezone.now(),
        )
        self.assertEqual(
            self.client.get(f"/api/system-settings/test-mail/{normal.pk}/").status_code,
            404,
        )

    def test_existing_outbox_still_sends_without_ui_override(self):
        item = Delivery.objects.create(
            recipient="legacy@example.com",
            subject="legacy",
            body="body",
            next_attempt_at=timezone.now(),
        )
        deliver_batch()
        item.refresh_from_db()
        self.assertEqual(item.status, "sent")
        self.assertEqual(mail.outbox[-1].to, ["legacy@example.com"])

    def test_real_local_smtp_transport(self):
        received = []
        sockets = {}

        class Server(smtpd.SMTPServer):
            def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
                received.append((mailfrom, rcpttos, data))

        server = Server(("127.0.0.1", 0), None, map=sockets)
        stop = threading.Event()

        def run():
            while not stop.is_set():
                asyncore.loop(timeout=0.05, count=1, map=sockets)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        try:
            response = self.post(
                "system-settings/",
                self.smtp(
                    smtp_host="127.0.0.1",
                    smtp_port=server.socket.getsockname()[1],
                    smtp_security="none",
                    smtp_auth=False,
                    smtp_password="",
                ),
            )
            self.assertEqual(response.status_code, 200, response.content)
            response = self.post(
                "system-settings/test-mail/", {"recipient": "local@example.com"}
            )
            deliver_batch()
            item = Delivery.objects.get(pk=response.json()["id"])
            self.assertEqual(item.status, "sent", item.last_error)
            self.assertEqual(received[0][0], "sender@example.com")
            self.assertEqual(received[0][1], ["local@example.com"])
        finally:
            stop.set()
            thread.join(timeout=2)
            for channel in list(sockets.values()):
                channel.close()

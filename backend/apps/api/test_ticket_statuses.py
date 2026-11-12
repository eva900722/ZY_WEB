import json
from io import BytesIO

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from openpyxl import load_workbook
from pypdf import PdfReader

from apps.api import tests as api_tests
from apps.audit.models import AuditLog
from apps.notifications.models import Delivery
from apps.tickets.models import StatusHistory, Ticket
from apps.tickets.services import claim, update_status


class TicketStatusTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        api_tests.ApiMigrationTests.setUpTestData.__func__(cls)
        cls.cases = {}
        for status in Ticket.Status.values:
            cls.cases[status] = Ticket.objects.create(
                number="STATUS-" + status,
                company=cls.company,
                reporter=cls.reporter,
                created_by=cls.reporter,
                form_version=cls.version,
                status=status,
                title="status fixture",
                description="status fixture",
                engineer=cls.engineer,
            )

    def post(self, path, data):
        return self.client.post(
            "/api/" + path, json.dumps(data), content_type="application/json"
        )

    def test_counts_choices_filter_and_detail_match_for_all_roles(self):
        for user, processing in (
            (self.reporter, 4),
            (self.manager, 5),
            (self.admin, 5),
        ):
            self.client.force_login(user)
            data = self.client.get("/api/tickets/").json()
            expected = {"processing": processing, "completed": 1, "cancelled": 1}
            if user.role == "it_admin":
                expected["waiting"] = 1
            self.assertEqual(data["counts"], expected)
            self.assertEqual(
                [x["value"] for x in data["statuses"]],
                ["processing", "waiting", "completed", "cancelled"]
                if user.role == "it_admin"
                else ["processing", "completed", "cancelled"],
            )
            filtered = self.client.get("/api/tickets/?status=processing").json()
            self.assertEqual(filtered["total"], processing)
            self.assertTrue(
                all(
                    x["status"] == "processing" and x["status_label"] == "處理中"
                    for x in filtered["items"]
                )
            )
            waiting = self.client.get(
                f"/api/tickets/{self.cases['waiting'].pk}/"
            ).json()
            self.assertEqual(
                waiting["status"],
                "waiting" if user.role == "it_admin" else "processing",
            )
            self.assertEqual(
                waiting["status_label"],
                "待客戶回覆" if user.role == "it_admin" else "處理中",
            )
            self.assertEqual(
                self.client.get("/api/tickets/?status=waiting").json()["total"],
                1 if user.role == "it_admin" else 0,
            )
            for obsolete in ("unassigned", "closed"):
                self.assertEqual(
                    self.client.get("/api/tickets/?status=" + obsolete).json()["total"],
                    0,
                )
        self.client.force_login(self.foreign)
        self.assertEqual(
            self.client.get("/api/tickets/?status=processing").json()["total"], 1
        )
        self.assertEqual(
            self.client.get(f"/api/tickets/{self.ticket.pk}/").status_code, 404
        )

    def test_default_claim_completion_and_removed_transitions(self):
        self.assertEqual(self.ticket.status, "assigned")
        self.assertIsNone(self.ticket.engineer_id)
        self.client.force_login(self.admin)
        detail = self.client.get(f"/api/tickets/{self.ticket.pk}/").json()
        self.assertTrue(detail["can_claim"])
        self.assertEqual([x["value"] for x in detail["transitions"]], ["cancelled"])
        self.assertEqual(detail["status_label"], "處理中")
        ticket = claim(self.admin, self.ticket.pk, self.ticket.revision)
        self.assertEqual(ticket.status, "processing")
        ticket = update_status(
            self.admin, ticket.pk, ticket.revision, "completed", "完成"
        )
        for status in ("closed", "unassigned"):
            response = self.post(
                f"tickets/{ticket.pk}/",
                {
                    "action": "status",
                    "revision": ticket.revision,
                    "status": status,
                    "reason": "obsolete",
                },
            )
            self.assertEqual(response.status_code, 400)
        for user in (self.reporter, self.manager):
            self.client.force_login(user)
            self.assertEqual(
                self.client.get(f"/api/tickets/{ticket.pk}/").json()["transitions"], []
            )
        self.assertFalse({"closed", "unassigned"}.intersection(Ticket.Status.values))

    def test_exports_share_role_status_names_and_filtering(self):
        for user, expected in (
            (self.reporter, "處理中"),
            (self.manager, "處理中"),
            (self.admin, "待客戶回覆"),
        ):
            self.client.force_login(user)
            for kind in ("xlsx", "pdf"):
                response = self.client.get(
                    f"/reports/{kind}/{self.cases['waiting'].pk}/"
                )
                self.assertEqual(response.status_code, 200)
                if kind == "xlsx":
                    rows = list(load_workbook(BytesIO(response.content)).active.values)
                    text = rows[1][rows[0].index("狀態")]
                else:
                    text = "".join(
                        p.extract_text()
                        for p in PdfReader(BytesIO(response.content)).pages
                    )
                self.assertIn(expected, text)
                if user.role != "it_admin":
                    self.assertNotIn("待客戶回覆", text)
            response = self.client.get("/reports/xlsx/?status=processing")
            sheet = load_workbook(BytesIO(response.content)).active
            expected_count = 4 if user.role == "reporter" else 5
            self.assertEqual(sheet.max_row, expected_count + 1)
            self.assertNotIn("待客戶回覆", str(list(sheet.values)))

    def test_completed_owner_can_be_disabled_but_pending_owner_cannot(self):
        self.client.force_login(self.admin)
        path = f"users/{self.engineer.pk}/action/"
        self.assertEqual(self.post(path, {"action": "disable"}).status_code, 400)
        Ticket.objects.filter(engineer=self.engineer).exclude(
            status__in=["completed", "cancelled"]
        ).update(engineer=None)
        self.assertEqual(self.post(path, {"action": "disable"}).status_code, 200)


class TicketStatusMigrationTests(TransactionTestCase):
    def test_old_statuses_migrate_without_changing_identity_or_history(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([("tickets", "0003_pending_takeover_label")])
            api_tests.ApiMigrationTests.setUpTestData.__func__(type(self))
            Ticket.objects.filter(pk=self.ticket.pk).update(status="unassigned")
            Ticket.objects.filter(pk=self.other_ticket.pk).update(status="closed")
            history = StatusHistory.objects.create(
                ticket=self.other_ticket,
                actor=self.admin,
                previous="completed",
                current="closed",
            )
            before = list(
                Ticket.objects.order_by("pk").values_list(
                    "id", "number", "snapshot", "engineer_id", "updated_at"
                )
            )
            deliveries = Delivery.objects.count()
            MigrationExecutor(connection).migrate(leaves)
            self.ticket.refresh_from_db()
            self.other_ticket.refresh_from_db()
            self.assertEqual(self.ticket.status, "assigned")
            self.assertEqual(self.other_ticket.status, "completed")
            self.assertEqual(self.ticket.revision, 2)
            history.refresh_from_db()
            self.assertEqual(history.current, "closed")
            self.assertEqual(
                before,
                list(
                    Ticket.objects.order_by("pk").values_list(
                        "id", "number", "snapshot", "engineer_id", "updated_at"
                    )
                ),
            )
            self.assertEqual(Delivery.objects.count(), deliveries)
            self.assertEqual(
                AuditLog.objects.filter(action="ticket.status_migrated").count(), 2
            )
            self.assertFalse(
                Ticket.objects.filter(status__in=["unassigned", "closed"]).exists()
            )
        finally:
            MigrationExecutor(connection).migrate(leaves)

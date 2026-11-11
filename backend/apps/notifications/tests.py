"""Only takeover and completion enqueue email; in-app events remain unchanged."""
from django.test import TestCase
from apps.api import tests as api_tests
from apps.accounts.models import User
from apps.companies.models import Recipient
from apps.tickets.services import create_ticket, claim, assign, update_status, add_entry
from django.core.exceptions import ValidationError
from .models import Delivery, Notification


class EmailEventPolicyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        api_tests.ApiMigrationTests.setUpTestData.__func__(cls)

    def setUp(self):
        for user, email in [(self.reporter, "reporter@example.invalid"), (self.manager, "shared@example.invalid"), (self.admin, "shared@example.invalid")]:
            user.email = email
            user.email_verified_at = None
            user.save()
        self.engineer.email = "nextowner@example.invalid"
        self.engineer.save()
        Recipient.objects.create(company=self.company, email="extra@example.invalid", events=["created", "assigned", "updated", "completed"])
        Recipient.objects.create(company=self.company, email="disabled@example.invalid", events=["assigned", "completed"], is_active=False)
        self.ticket = create_ticket(self.reporter, self.company, self.reporter, self.version, {"title": "寄信規則", "description": "假資料"}, {})

    def test_created_notifies_in_app_but_never_emails(self):
        self.assertTrue(Notification.objects.filter(ticket=self.ticket, user=self.admin).exists())
        self.assertTrue(Notification.objects.filter(ticket=self.ticket, user=self.reporter).exists())
        self.assertEqual(Delivery.objects.count(), 0)

    def test_takeover_and_completion_email_deduplicated_recipients(self):
        ticket = claim(self.admin, self.ticket.pk, 1)
        expected = {"reporter@example.invalid", "shared@example.invalid", "extra@example.invalid"}
        self.assertEqual(set(Delivery.objects.values_list("recipient", flat=True)), expected)
        self.assertEqual(Delivery.objects.count(), 3)
        self.assertEqual(ticket.status, "processing")
        count = Notification.objects.count()
        with self.assertRaises(ValidationError):
            claim(self.engineer, ticket.pk, ticket.revision)
        self.assertEqual(Delivery.objects.count(), 3)
        ticket = update_status(self.admin, ticket.pk, ticket.revision, "completed", "已修復")
        self.assertEqual(Delivery.objects.count(), 6)
        self.assertGreater(Notification.objects.count(), count)
        for email in expected:
            self.assertEqual(Delivery.objects.filter(recipient=email).count(), 2)

    def test_other_actions_never_email_even_when_ticket_is_processing(self):
        ticket = claim(self.admin, self.ticket.pk, 1)
        Delivery.objects.all().delete()
        before = Notification.objects.count()
        entry = add_entry(self.admin, ticket.pk, ticket.revision, "補充資訊", False)
        ticket = entry.ticket
        self.assertGreater(Notification.objects.count(), before)
        entry = add_entry(self.admin, ticket.pk, ticket.revision, "內部備註", True)
        ticket = entry.ticket
        ticket = assign(self.admin, ticket.pk, ticket.revision, self.engineer, "交接")
        ticket = update_status(self.engineer, ticket.pk, ticket.revision, "waiting", "等候回覆")
        ticket = update_status(self.engineer, ticket.pk, ticket.revision, "processing", "恢復處理")
        ticket = update_status(self.engineer, ticket.pk, ticket.revision, "cancelled", "取消")
        ticket = update_status(self.engineer, ticket.pk, ticket.revision, "processing", "重開")
        self.assertEqual(Delivery.objects.count(), 0)
        ticket = update_status(self.engineer, ticket.pk, ticket.revision, "completed", "完成")
        self.assertTrue(Delivery.objects.exists())
        Delivery.objects.all().delete()
        ticket = update_status(self.engineer, ticket.pk, ticket.revision, "closed", "結案")
        ticket = update_status(self.engineer, ticket.pk, ticket.revision, "processing", "再次處理")
        self.assertEqual(Delivery.objects.count(), 0)

    def test_blank_emails_do_not_block_takeover_or_completion(self):
        User.objects.filter(pk__in=[self.reporter.pk, self.manager.pk, self.admin.pk]).update(email="")
        self.company.recipients.all().delete()
        ticket = claim(self.admin, self.ticket.pk, 1)
        update_status(self.admin, ticket.pk, ticket.revision, "completed", "完成")
        self.assertEqual(Delivery.objects.count(), 0)
        self.assertTrue(Notification.objects.filter(ticket=ticket).exists())

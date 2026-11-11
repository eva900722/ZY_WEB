"""Daily numbering and real MySQL concurrency regressions (test database only)."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase
from django.db import connections
from django.utils import timezone
from apps.accounts.models import User
from apps.companies.models import Company
from apps.forms.models import FormVersion
from apps.notifications.models import Notification
from .models import Ticket, DailyTicketCounter
from .services import create_ticket, update_status

DAY = date(2026, 11, 11)


def setup_company(code):
    company = Company.objects.create(name=code, code=code)
    reporter = User.objects.create_user(username=code + "reporter", role="reporter", company=company)
    version = FormVersion.objects.create(company=company, number=1, fields=[], published_at=timezone.now(), created_by=reporter)
    return company, reporter, version


def submit(company, reporter, version):
    return create_ticket(reporter, company, reporter, version, {"title": "每日單號測試", "description": "測試資料"}, {})


class DailyNumberTests(TestCase):
    def setUp(self):
        self.company, self.reporter, self.version = setup_company("yf")
        self.clock = patch("apps.tickets.services.timezone.localdate", return_value=DAY)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def create(self):
        return submit(self.company, self.reporter, self.version)

    def test_sequence_and_company_and_day_are_independent(self):
        self.assertEqual(self.create().number, "YF20261111-001")
        self.assertEqual(self.create().number, "YF20261111-002")
        self.assertEqual(submit(*setup_company("wy")).number, "WY20261111-001")
        with patch("apps.tickets.services.timezone.localdate", return_value=date(2026, 11, 12)):
            self.assertEqual(self.create().number, "YF20261112-001")
        self.assertEqual(self.create().number, "YF20261111-003")

    def test_cancellation_and_removed_ticket_do_not_recycle_numbers(self):
        self.create()
        second = self.create()
        admin = User.objects.create_user(username="numberadmin", role="it_admin")
        update_status(admin, second.pk, second.revision, "cancelled", "重複報修")
        self.assertEqual(self.create().number, "YF20261111-003")
        # Simulate a future controlled physical purge in the test database only.
        second.entries.all().delete()
        second.status_history.all().delete()
        Notification.objects.filter(ticket=second).delete()
        second.delete()
        self.assertEqual(self.create().number, "YF20261111-004")

    def test_over_999_and_company_code_change_keep_existing_numbers(self):
        first = self.create()
        DailyTicketCounter.objects.filter(company=self.company, date=DAY).update(last_number=999)
        self.assertEqual(self.create().number, "YF20261111-1000")
        Company.objects.filter(pk=self.company.pk).update(code="newyf")
        self.assertEqual(self.create().number, "NEWYF20261111-1001")
        first.refresh_from_db()
        self.assertEqual(first.number, "YF20261111-001")

    def test_legacy_random_number_unchanged(self):
        old = Ticket.objects.create(number="YF20261111-ABCDEF0123456789", company=self.company, reporter=self.reporter, created_by=self.reporter, form_version=self.version, title="舊案件", description="保留原單號")
        self.assertEqual(self.create().number, "YF20261111-001")
        old.refresh_from_db()
        self.assertEqual(old.number, "YF20261111-ABCDEF0123456789")

    def test_failed_submission_rolls_back_ticket_and_counter(self):
        with patch("apps.tickets.services.event", side_effect=RuntimeError("test rollback")):
            with self.assertRaises(RuntimeError):
                self.create()
        self.assertFalse(Ticket.objects.exists())
        self.assertFalse(DailyTicketCounter.objects.exists())
        self.assertEqual(self.create().number, "YF20261111-001")


class DailyNumberConcurrencyTests(TransactionTestCase):
    def test_simultaneous_first_and_existing_counter_have_no_duplicates(self):
        company, reporter, version = setup_company("race")
        for start in [1, 5]:
            barrier = Barrier(4)
            def run(index):
                try:
                    barrier.wait(timeout=10)
                    return submit(company, reporter, version).number
                finally:
                    connections.close_all()
            with patch("apps.tickets.services.timezone.localdate", return_value=DAY):
                with ThreadPoolExecutor(max_workers=4) as pool:
                    numbers = list(pool.map(run, range(4)))
            self.assertEqual(sorted(numbers), [f"RACE20261111-{n:03d}" for n in range(start, start + 4)])
        self.assertEqual(Ticket.objects.count(), 8)
        self.assertEqual(DailyTicketCounter.objects.get(company=company, date=DAY).last_number, 8)

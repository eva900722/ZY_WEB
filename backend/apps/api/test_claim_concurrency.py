"""Real MySQL row-lock regression: a pending ticket has exactly one winner."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TransactionTestCase
from django.db import connections
from django.core.exceptions import ValidationError
from apps.accounts.models import User
from apps.companies.models import Company
from apps.forms.models import FormVersion
from apps.tickets.models import Ticket
from apps.tickets.services import claim, assign


class ClaimConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="raceadmin", role="it_admin")
        self.engineers = [User.objects.create_user(username=f"race{i}", role="it_admin") for i in range(2)]
        company = Company.objects.create(name="領單測試", code="claimrace")
        reporter = User.objects.create_user(username="racereporter", role="reporter", company=company)
        version = FormVersion.objects.create(company=company, number=1, fields=[], created_by=self.admin)
        self.ticket = Ticket.objects.create(number="CLAIM-RACE", title="競爭測試", description="test", company=company, reporter=reporter, created_by=reporter, form_version=version)

    def race(self, operation):
        barrier = Barrier(2)
        def run(index):
            try:
                barrier.wait(timeout=10)
                operation(index)
                return "success"
            except ValidationError:
                return "conflict"
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertCountEqual(results, ["success", "conflict"])
        self.ticket.refresh_from_db()
        self.assertIsNotNone(self.ticket.engineer_id)
        self.assertEqual(self.ticket.status, "processing")
        self.assertEqual(self.ticket.revision, 2)
        self.assertEqual(self.ticket.assignments.count(), 1)

    def test_two_engineers_have_one_claim_winner(self):
        self.race(lambda i: claim(self.engineers[i], self.ticket.pk, 1))

    def test_owner_change_and_staff_claim_do_not_overwrite(self):
        self.test_two_engineers_have_one_claim_winner()
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            claim(self.admin, self.ticket.pk, 2)
        assign(self.admin, self.ticket.pk, 2, self.engineers[1], "交接")
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.engineer_id, self.engineers[1].pk)
        self.assertEqual(self.ticket.revision, 3)

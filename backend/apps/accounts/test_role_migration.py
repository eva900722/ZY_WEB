"""Verify existing engineer identity and ticket ownership survive role conversion."""
from django.test import TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class StaffRoleMigrationTests(TransactionTestCase):
    def test_engineer_converted_without_recreating_account_or_ticket(self):
        executor = MigrationExecutor(connection)
        executor.migrate([("accounts", "0001_initial")])
        old_apps = executor.loader.project_state([("accounts", "0001_initial")]).apps
        old_user = old_apps.get_model("accounts", "User")
        user = old_user.objects.create(username="migrateengineer", role="engineer", display_name="原工程師", password="preserved-password-hash", must_change_password=False)
        # All ownership foreign keys keep the same primary key after conversion.
        from apps.companies.models import Company
        from apps.forms.models import FormVersion
        from apps.tickets.models import Ticket
        company = Company.objects.create(code="migration", name="測試客戶")
        reporter = old_user.objects.create(username="migratereporter", role="reporter", company_id=company.pk)
        version = FormVersion.objects.create(company=company, number=1, fields=[], created_by_id=user.pk)
        ticket = Ticket.objects.create(number="UNCHANGED-001", company=company, reporter_id=reporter.pk, created_by_id=reporter.pk, form_version=version, engineer_id=user.pk, status="processing", title="原案件", description="保持資料")
        executor = MigrationExecutor(connection)
        executor.migrate([("accounts", "0002_unified_zy_staff")])
        from apps.accounts.models import User
        converted = User.objects.get(pk=user.pk)
        self.assertEqual(converted.role, "it_admin")
        self.assertEqual(converted.password, "preserved-password-hash")
        self.assertEqual(converted.display_name, "原工程師")
        self.assertFalse(converted.must_change_password)
        ticket.refresh_from_db()
        self.assertEqual(ticket.engineer_id, user.pk)
        self.assertEqual(ticket.number, "UNCHANGED-001")
        self.assertEqual(User.objects.get(pk=reporter.pk).role, "reporter")

    def tearDown(self):
        MigrationExecutor(connection).migrate([("accounts", "0002_unified_zy_staff")])
        super().tearDown()

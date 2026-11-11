"""Regression tests for horizontal report exports, using test_zy_web only."""
from datetime import datetime, timezone as dt_timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from django.test import TestCase
from openpyxl import load_workbook
from pypdf import PdfReader
from apps.api import tests as api_tests
from apps.tickets.models import Entry
from apps.reports.views import table_data


class ReportExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        api_tests.ApiMigrationTests.setUpTestData.__func__(cls)

    def download(self, kind, user=None, query="", pk=None):
        self.client.force_login(user or self.reporter)
        path = f"/reports/{kind}/" + (f"{pk}/" if pk else "")
        with patch("apps.reports.views.timezone.now", return_value=datetime(2026, 11, 11, 7, 21, tzinfo=dt_timezone.utc)):
            return self.client.get(path + query)

    def test_excel_one_ticket_per_row_ui_headers_and_literal_values(self):
        self.ticket.title = "=1+1"
        self.ticket.save()
        Entry.objects.create(ticket=self.ticket, author=self.reporter, body="FIRST")
        Entry.objects.create(ticket=self.ticket, author=self.reporter, body="SECOND")
        Entry.objects.create(ticket=self.ticket, author=self.admin, body="HIDDEN_NOTE", internal=True)
        response = self.download("xlsx", self.manager)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="1151111_1521.xlsx"')
        sheet = load_workbook(BytesIO(response.content)).active
        self.assertEqual(sheet.max_row, 3)
        headers = [c.value for c in sheet[1]]
        self.assertEqual(headers[:8], ["單號", "公司", "報修人", "問題摘要", "狀態", "負責人", "建立時間", "更新時間"])
        self.assertNotIn("欄位", headers)
        self.assertNotIn("內部備註", headers)
        records = {row[0].value: row for row in list(sheet)[1:]}
        title = records[self.ticket.number][headers.index("問題摘要")]
        self.assertEqual(title.value, "=1+1")
        self.assertEqual(title.data_type, "s")
        notes = records[self.ticket.number][headers.index("處理紀錄")].value
        self.assertIn("FIRST", notes)
        self.assertIn("SECOND", notes)
        self.assertNotIn("HIDDEN_NOTE", str(list(sheet.values)))
        self.assertEqual(sheet.freeze_panes, "B2")
        self.assertEqual(sheet.print_title_rows, "$1:$1")

    def test_dynamic_columns_and_missing_values_align(self):
        self.version.fields = [{"key": "device", "label": "設備類型", "type": "text"}]
        # A fixture-only update avoids the published-version mutation service.
        type(self.version).objects.filter(pk=self.version.pk).update(fields=self.version.fields)
        self.ticket.form_version = self.version
        self.ticket.answers = {"device": "印表機"}
        self.ticket.save()
        headers, rows = table_data(self.admin, [self.ticket, self.other_ticket])
        self.assertEqual(rows[0][headers.index("設備類型")], "印表機")
        self.assertEqual(rows[1][headers.index("設備類型")], "")
        self.assertTrue(all(len(row) == len(headers) for row in rows))

    def test_pdf_landscape_repeated_headers_and_private_content(self):
        Entry.objects.create(ticket=self.ticket, author=self.admin, body="PRIVATE_ADMIN_NOTE", internal=True)
        response = self.download("pdf", pk=self.ticket.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="1151111_1521.pdf"')
        reader = PdfReader(BytesIO(response.content))
        self.assertTrue(all(p.mediabox.width > p.mediabox.height for p in reader.pages))
        text = "".join(p.extract_text() for p in reader.pages)
        self.assertIn("問題摘要", text)
        self.assertIn("負責人", text)
        self.assertNotIn("PRIVATE_ADMIN_NOTE", text)
        self.assertTrue(all("單號" in p.extract_text() for p in reader.pages))
        # Render only fake test data; diagnostic artifacts are ignored by git.
        import pymupdf as fitz
        target = Path(__file__).resolve().parents[3] / ".tools/report-qa"
        target.mkdir(parents=True, exist_ok=True)
        doc = fitz.open(stream=response.content, filetype="pdf")
        for index in [0, len(doc) - 1]:
            doc[index].get_pixmap(matrix=fitz.Matrix(1, 1)).save(str(target / f"table-{index}.png"))

    def test_long_pdf_rows_split_without_losing_last_text(self):
        self.ticket.description = "長文字測試" * 2500 + "LAST_TEXT_MARKER"
        self.ticket.save()
        response = self.download("pdf", pk=self.ticket.pk)
        reader = PdfReader(BytesIO(response.content))
        text = "".join(p.extract_text() for p in reader.pages)
        self.assertIn("LAST_TEXT_MARKER", text)
        self.assertTrue(all("單號" in p.extract_text() for p in reader.pages))

    def test_filters_empty_exports_and_foreign_access_unchanged(self):
        response = self.download("xlsx", self.manager, "?q=VueAPI")
        self.assertEqual(load_workbook(BytesIO(response.content)).active.max_row, 2)
        for kind in ["pdf", "xlsx"]:
            self.assertEqual(self.download(kind, pk=self.foreign_ticket.pk).status_code, 404)
            response = self.download(kind, query="?q=NO_MATCH_9283")
            self.assertEqual(response.status_code, 200)
            if kind == "xlsx":
                self.assertEqual(load_workbook(BytesIO(response.content)).active.max_row, 1)

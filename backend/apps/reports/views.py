from io import BytesIO
from xml.sax.saxutils import escape
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone
from openpyxl import Workbook
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, LongTable, TableStyle
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib import colors
from openpyxl.utils import get_column_letter
from zoneinfo import ZoneInfo
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pathlib import Path
import os
from common.permissions import entries_for, attachments_for
from apps.tickets.views import filtered
from apps.tickets.statuses import status_label
from apps.audit.services import log


def text_rows(user, ticket):
    rows = [
        ("單號", ticket.number),
        ("公司", ticket.company.name),
        ("報修人", ticket.snapshot.get("display_name", "")),
        ("狀態", status_label(user, ticket.status)),
        ("負責人", str(ticket.engineer) if ticket.engineer_id else "尚未接手"),
        ("問題摘要", ticket.title),
        ("問題描述", ticket.description),
    ]
    rows += [
        (
            {
                "staff_id": "工號",
                "department": "部門",
                "office": "辦公室",
                "phone": "電話／分機",
                "mobile": "手機",
                "email": "Email",
            }[k],
            str(ticket.snapshot.get(k, "")),
        )
        for k in ["staff_id", "department", "office", "phone", "mobile", "email"]
    ]
    rows += [
        ("AnyDesk ID", ticket.anydesk),
        ("表單版本", str(ticket.form_version.number)),
        ("建立時間", timezone.localtime(ticket.created_at).strftime("%Y-%m-%d %H:%M")),
        ("更新時間", timezone.localtime(ticket.updated_at).strftime("%Y-%m-%d %H:%M")),
    ]
    fixed_labels = {label for label, _ in rows} | {"處理紀錄", "內部備註", "附件"}
    rows += [
        (
            f["label"] + ("（報修欄位）" if f["label"] in fixed_labels else ""),
            str(ticket.answers.get(f["key"], "")),
        )
        for f in ticket.form_version.fields
    ]
    rows += [
        (
            "內部備註" if e.internal else "處理紀錄",
            f"{e.author}｜{timezone.localtime(e.created_at):%Y-%m-%d %H:%M}｜{e.body}",
        )
        for e in entries_for(user, ticket)
    ]
    rows += [("舊版保留：" + x[0], x[1]) for x in ticket.answers.get("_unmapped", [])]
    rows += [("附件", a.name) for a in attachments_for(user, ticket)]
    return rows


def table_data(user, tickets):
    # UI labels; every ticket occupies one row. Repeated entries/files share a cell.
    headers = ["單號", "公司", "報修人", "問題摘要", "狀態", "負責人", "建立時間", "更新時間",
               "問題描述", "工號", "部門", "辦公室", "電話／分機", "手機", "Email", "AnyDesk ID", "表單版本"]
    records = []
    for ticket in tickets:
        record = {}
        for label, value in text_rows(user, ticket):
            if label not in headers:
                headers.append(label)
            record[label] = record[label] + "\n" + value if label in record else value
        records.append(record)
    return headers, [[record.get(label, "") for label in headers] for record in records]


def pdf_table(headers, rows, style, width):
    # Use horizontal column groups instead of shrinking a wide report to unreadable text.
    # The ticket number is repeated for matching the same row across column groups.
    story = []
    for start in range(1, len(headers), 6):
        columns = [0] + list(range(start, min(start + 6, len(headers))))
        if story:
            story.append(PageBreak())
        story.extend([Paragraph("資訊管家｜維修紀錄", style), Spacer(1, 8)])
        def cell(value):
            return Paragraph(escape(str(value)).replace("\n", "<br/>"), style)
        data = [[cell(headers[i]) for i in columns]]
        data.extend([[cell(row[i]) for i in columns] for row in rows])
        table = LongTable(data, colWidths=[width / len(columns)] * len(columns),
                          repeatRows=1, splitByRow=1, splitInRow=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#deeee9")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f8f7")]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b6c7c1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
    return story


@login_required
def export(request, kind, pk=None):
    if kind not in ["pdf", "xlsx"]:
        raise Http404
    qs = filtered(request.user, request.GET)
    tickets = [get_object_or_404(qs, pk=pk)] if pk else list(qs[:1000])
    headers, rows = table_data(request.user, tickets)
    now = timezone.localtime(timezone.now(), ZoneInfo("Asia/Taipei"))
    filename = f"{now.year - 1911:03d}{now:%m%d_%H%M}.{kind}"
    out = BytesIO()
    if kind == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = "維修紀錄"
        ws.append(headers)
        for row in rows:
            ws.append(row)
        # Keep formulas as literal text, including dynamic column titles.
        from openpyxl.styles import Alignment, Font, PatternFill
        for row in ws:
            for cell in row:
                cell.data_type = "s"
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = ws.dimensions
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A3
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.print_title_rows = "1:1"
        for index, label in enumerate(headers, 1):
            ws.column_dimensions[get_column_letter(index)].width = (
                42 if label in ["單號", "問題摘要", "問題描述", "處理紀錄", "內部備註"] else 24
            )
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="DEEEE9")
        wb.save(out)
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        if "ZYChinese" not in pdfmetrics.getRegisteredFontNames():
            candidates = [
                os.getenv("PDF_FONT_PATH", ""),
                r"C:\Windows\Fonts\msjh.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            ]
            font = next((x for x in candidates if x and Path(x).is_file()), None)
            if not font:
                raise RuntimeError("請安裝中文字型或設定 PDF_FONT_PATH")
            pdfmetrics.registerFont(TTFont("ZYChinese", font, subfontIndex=0))
        style = ParagraphStyle(
            "Chinese", fontName="ZYChinese", fontSize=10, leading=16, wordWrap="CJK"
        )
        doc = SimpleDocTemplate(out, pagesize=landscape(A3), leftMargin=28, rightMargin=28,
                                topMargin=28, bottomMargin=28,
                                title="資訊管家維修紀錄", author="ZY_WEB")
        doc.build(pdf_table(headers, rows, style, doc.width))
        mime = "application/pdf"
    log(
        request.user,
        "report.export",
        str(pk or "list"),
        details={"format": kind, "count": len(tickets), "limit": 1000},
        request=request,
    )
    response = HttpResponse(out.getvalue(), content_type=mime)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    return response

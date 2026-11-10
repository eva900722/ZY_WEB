from io import BytesIO
from xml.sax.saxutils import escape
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone
from openpyxl import Workbook
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pathlib import Path
import os
from common.permissions import entries_for, attachments_for
from apps.tickets.views import filtered
from apps.audit.services import log


def text_rows(user, ticket):
    rows = [
        ("單號", ticket.number),
        ("公司", ticket.company.name),
        ("報修人", ticket.snapshot.get("display_name", "")),
        ("狀態", ticket.get_status_display()),
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
        ("建立時間", timezone.localtime(ticket.created_at).isoformat()),
    ]
    rows += [
        (f["label"], str(ticket.answers.get(f["key"], "")))
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


@login_required
def export(request, kind, pk=None):
    if kind not in ["pdf", "xlsx"]:
        raise Http404
    qs = filtered(request.user, request.GET)
    tickets = [get_object_or_404(qs, pk=pk)] if pk else list(qs[:1000])
    out = BytesIO()
    if kind == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = "維修紀錄"
        ws.append(["單號", "欄位", "內容"])
        for t in tickets:
            for label, value in text_rows(request.user, t):
                ws.append([t.number, label, value])
                # Explicit string cells prevent spreadsheet formula execution.
                for cell in ws[ws.max_row]:
                    cell.data_type = "s"
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        ws.column_dimensions["A"].width = 42
        ws.column_dimensions["B"].width = 24
        ws.column_dimensions["C"].width = 90
        from openpyxl.styles import Alignment, Font

        for cell in ws[1]:
            cell.font = Font(bold=True)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
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
        story = [Paragraph("資訊管家｜維修紀錄", style), Spacer(1, 12)]
        for i, t in enumerate(tickets):
            if i:
                story.append(PageBreak())
            for label, value in text_rows(request.user, t):
                # Avoid one oversized paragraph for long records.
                raw = label + "：" + value
                for start in range(0, len(raw), 1500):
                    story.append(
                        Paragraph(
                            escape(raw[start : start + 1500]).replace("\n", "<br/>"),
                            style,
                        )
                    )
                story.append(Spacer(1, 6))
        SimpleDocTemplate(out, title="資訊管家維修紀錄", author="ZY_WEB").build(story)
        mime = "application/pdf"
    log(
        request.user,
        "report.export",
        str(pk or "list"),
        details={"format": kind, "count": len(tickets), "limit": 1000},
        request=request,
    )
    response = HttpResponse(out.getvalue(), content_type=mime)
    response["Content-Disposition"] = f'attachment; filename="maintenance.{kind}"'
    response["Cache-Control"] = "private, no-store"
    return response

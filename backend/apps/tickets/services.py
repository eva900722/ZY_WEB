import uuid
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.companies.models import Company
from apps.accounts.models import User
from apps.forms.models import FormVersion
from apps.forms.services import accepted
from apps.audit.services import log
from apps.notifications.services import event
from common.permissions import tickets_for, require
from .models import Ticket, Entry, StatusHistory, AssignmentHistory


def locked_ticket(user, pk, revision):
    ticket = tickets_for(user).select_for_update(of=("self",)).filter(pk=pk).first()
    if not ticket:
        raise PermissionDenied
    if ticket.revision != revision:
        raise ValidationError(
            "案件已被其他人更新，請重新載入後再送出；原輸入仍保留於此頁。"
        )
    return ticket


@transaction.atomic
def create_ticket(user, company, reporter, version, cleaned, answers):
    company = Company.objects.select_for_update().get(pk=company.pk)
    if not company.is_active:
        raise ValidationError("公司已停用")
    if user.role == "engineer":
        raise PermissionDenied
    if user.role != "it_admin" and company.pk != user.company_id:
        raise PermissionDenied
    if (
        reporter.company_id != company.pk
        or reporter.role not in ["reporter", "company_admin"]
        or not reporter.is_active
        or reporter.deleted_at
    ):
        raise ValidationError("報修人不屬於此公司或帳號不可用")
    if user.role == "reporter" and reporter.pk != user.pk:
        raise PermissionDenied
    version = FormVersion.objects.get(pk=version.pk, company=company)
    if not accepted(version):
        raise ValidationError("表單版本已停止接受，請保留內容並切換新版")
    number = f"{company.code.upper()}{timezone.localdate():%Y%m%d}-{uuid.uuid4().hex[:16].upper()}"
    snapshot = {
        k: getattr(reporter, k)
        for k in [
            "display_name",
            "staff_id",
            "department",
            "office",
            "phone",
            "mobile",
            "email",
        ]
    }
    snapshot["office"] = cleaned.get("office") or reporter.office
    t = Ticket.objects.create(
        number=number,
        company=company,
        reporter=reporter,
        created_by=user,
        form_version=version,
        title=cleaned["title"],
        description=cleaned["description"],
        anydesk=cleaned.get("anydesk", ""),
        snapshot=snapshot,
        answers=answers,
    )
    StatusHistory.objects.create(ticket=t, actor=user, previous="", current=t.status)
    log(user, "ticket.created", t.number, company=company)
    event(t, "created", f"案件 {t.number} 已受理，等待派工。")
    return t


@transaction.atomic
def assign(user, pk, revision, engineer, reason):
    require(user, "it_admin")
    t = locked_ticket(user, pk, revision)
    engineer = User.objects.select_for_update().get(pk=engineer.pk)
    if engineer.role != "engineer" or not engineer.is_active or engineer.deleted_at:
        raise ValidationError("工程師不可用")
    if t.status in ["closed", "cancelled"]:
        raise ValidationError("已結案或取消案件需先重新開啟")
    AssignmentHistory.objects.create(
        ticket=t, previous=t.engineer, engineer=engineer, actor=user, reason=reason
    )
    t.engineer = engineer
    if t.status == "unassigned":
        StatusHistory.objects.create(
            ticket=t, actor=user, previous=t.status, current="assigned", reason=reason
        )
        t.status = "assigned"
    t.revision += 1
    t.save()
    log(
        user,
        "ticket.assigned",
        t.number,
        company=t.company,
        details={"engineer_id": engineer.pk, "reason": reason},
    )
    event(t, "assigned", f"案件 {t.number} 已更新負責工程師。")
    return t


@transaction.atomic
def update_status(user, pk, revision, status, reason):
    t = locked_ticket(user, pk, revision)
    transitions = {
        "unassigned": {"cancelled"},
        "assigned": {"processing", "cancelled"},
        "processing": {"waiting", "completed", "cancelled"},
        "waiting": {"processing", "completed", "cancelled"},
        "completed": {"closed", "processing"},
        "closed": {"processing"},
        "cancelled": {"processing"},
    }
    if status not in transitions.get(t.status, set()):
        raise ValidationError("不允許的狀態轉換")
    if user.role in ["reporter", "company_admin"]:
        if not (t.status == "completed" and status == "closed"):
            raise PermissionDenied
    elif user.role == "engineer" and status in ["cancelled", "closed"]:
        raise PermissionDenied
    if t.status in ["closed", "cancelled"] and user.role != "it_admin":
        raise PermissionDenied
    if status in ["processing", "waiting", "completed"] and not t.engineer_id:
        raise ValidationError("請先指派工程師")
    if not reason.strip():
        raise ValidationError("請填寫處理說明")
    old = t.status
    t.status = status
    t.revision += 1
    t.save()
    StatusHistory.objects.create(
        ticket=t, actor=user, previous=old, current=status, reason=reason
    )
    Entry.objects.create(ticket=t, author=user, body=reason, internal=False)
    log(
        user,
        "ticket.status",
        t.number,
        company=t.company,
        details={"from": old, "to": status},
    )
    event(
        t,
        "completed" if status == "completed" else "updated",
        f"案件 {t.number} 狀態：{t.get_status_display()}。",
    )
    return t


@transaction.atomic
def add_entry(user, pk, revision, body, internal):
    t = locked_ticket(user, pk, revision)
    if internal and user.role not in ["engineer", "it_admin"]:
        raise PermissionDenied
    if t.status in ["closed", "cancelled"]:
        raise ValidationError("已結案或取消，請先由管理者重開")
    e = Entry.objects.create(ticket=t, author=user, body=body, internal=internal)
    t.revision += 1
    t.save()
    log(
        user,
        "ticket.internal_entry" if internal else "ticket.entry",
        t.number,
        company=t.company,
    )
    if not internal:
        event(t, "updated", f"案件 {t.number} 有新的補充說明。")
    return e

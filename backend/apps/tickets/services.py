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
from .models import Ticket, Entry, StatusHistory, AssignmentHistory, DailyTicketCounter
from .statuses import allowed_transitions


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
    # The company row is already locked, including the first counter of each day.
    day = timezone.localdate()
    counter, _ = DailyTicketCounter.objects.select_for_update().get_or_create(
        company=company, date=day
    )
    while True:
        counter.last_number += 1
        number = f"{company.code.upper()}{day:%Y%m%d}-{counter.last_number:03d}"
        # Also avoid existing numbers if a company code was reused after a rename.
        if not Ticket.objects.filter(number=number).exists():
            break
    counter.save(update_fields=["last_number"])
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
    event(t, "created", f"案件 {t.number} 已受理，等待接手。")
    return t


@transaction.atomic
def assign(user, pk, revision, engineer, reason):
    require(user, "it_admin")
    t = locked_ticket(user, pk, revision)
    if not t.engineer_id:
        raise ValidationError("請先接手案件，再交接給其他負責人")
    return _assign_ticket(user, t, engineer, reason)


@transaction.atomic
def claim(user, pk, revision):
    require(user, "it_admin")
    if not user.is_active or user.deleted_at:
        raise PermissionDenied
    # Lock by ID so simultaneous claimers see the committed winner, not a stale scope.
    t = Ticket.objects.select_for_update().filter(pk=pk).first()
    if not t:
        raise PermissionDenied
    if t.engineer_id is not None or t.status != "assigned":
        raise ValidationError("此案件已有人負責或不再待處理，請重新載入。")
    if t.revision != revision:
        raise ValidationError("案件已更新，請重新載入後再領單。")
    return _assign_ticket(user, t, user, "接手處理", start_processing=True)


def _assign_ticket(user, t, engineer, reason, start_processing=False):
    engineer = User.objects.select_for_update().get(pk=engineer.pk)
    if engineer.role != "it_admin" or not engineer.is_active or engineer.deleted_at:
        raise ValidationError("負責人不可用")
    if t.status == "cancelled":
        raise ValidationError("已取消案件需先重新開啟")
    AssignmentHistory.objects.create(
        ticket=t, previous=t.engineer, engineer=engineer, actor=user, reason=reason
    )
    t.engineer = engineer
    if t.status == "assigned" and start_processing:
        StatusHistory.objects.create(
            ticket=t, actor=user, previous=t.status, current="processing", reason=reason
        )
        t.status = "processing"
    t.revision += 1
    t.save()
    log(
        user,
        "ticket.assigned",
        t.number,
        company=t.company,
        details={"engineer_id": engineer.pk, "reason": reason},
    )
    event(t, "assigned", f"案件 {t.number} 已更新負責人。", send_email=start_processing)
    return t


@transaction.atomic
def update_status(user, pk, revision, status, reason):
    t = locked_ticket(user, pk, revision)
    if user.role != "it_admin":
        raise PermissionDenied
    if status not in allowed_transitions(user, t):
        raise ValidationError("不允許的狀態轉換")
    if status in ["processing", "waiting", "completed"] and not t.engineer_id:
        raise ValidationError("請先接手案件")
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
        send_email=status == "completed",
    )
    return t


@transaction.atomic
def add_entry(user, pk, revision, body, internal):
    t = locked_ticket(user, pk, revision)
    if internal and user.role != "it_admin":
        raise PermissionDenied
    if t.status == "cancelled":
        raise ValidationError("已取消，請先由贊耀公司人員重開")
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

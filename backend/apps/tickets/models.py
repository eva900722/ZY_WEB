from django.db import models
import uuid


class DailyTicketCounter(models.Model):
    company = models.ForeignKey("companies.Company", on_delete=models.PROTECT)
    date = models.DateField()
    last_number = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["company", "date"], name="unique_company_ticket_date")
        ]


class Ticket(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "assigned", "待處理"
        PROCESSING = "processing", "處理中"
        WAITING = "waiting", "待客戶回覆"
        COMPLETED = "completed", "已完成"
        CANCELLED = "cancelled", "已取消"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    number = models.CharField(max_length=80, unique=True)
    company = models.ForeignKey("companies.Company", on_delete=models.PROTECT)
    reporter = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="reported_tickets"
    )
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="created_tickets"
    )
    engineer = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assigned_tickets",
    )
    form_version = models.ForeignKey(
        "form_definitions.FormVersion", on_delete=models.PROTECT
    )
    title = models.CharField("問題摘要", max_length=200)
    description = models.TextField("問題描述")
    anydesk = models.CharField("AnyDesk ID", max_length=50, blank=True)
    snapshot = models.JSONField(default=dict)
    answers = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ASSIGNED
    )
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "status", "created_at"]),
            models.Index(fields=["engineer", "status"]),
        ]


class Entry(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name="entries")
    author = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    body = models.TextField()
    internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class AssignmentHistory(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.PROTECT, related_name="assignments"
    )
    previous = models.ForeignKey(
        "accounts.User", null=True, on_delete=models.PROTECT, related_name="+"
    )
    engineer = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="+"
    )
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="+"
    )
    reason = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)


class StatusHistory(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.PROTECT, related_name="status_history"
    )
    actor = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    previous = models.CharField(max_length=20, blank=True)
    current = models.CharField(max_length=20)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

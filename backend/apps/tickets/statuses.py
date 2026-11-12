"""Shared status presentation, filtering and available transitions."""

from django.db.models import Count

LABELS = {
    "processing": "處理中",
    "waiting": "待客戶回覆",
    "completed": "已完成",
    "cancelled": "已取消",
}
TRANSITIONS = {
    "assigned": ("processing", "cancelled"),
    "processing": ("waiting", "completed", "cancelled"),
    "waiting": ("processing", "completed", "cancelled"),
    "completed": ("processing",),
    "cancelled": ("processing",),
}


def visible_status(user, status):
    if status == "assigned" or (status == "waiting" and user.role != "it_admin"):
        return "processing"
    return status


def status_label(user, status):
    return LABELS[visible_status(user, status)]


def status_choices(user):
    return [
        (value, label)
        for value, label in LABELS.items()
        if value != "waiting" or user.role == "it_admin"
    ]


def filter_statuses(user, value):
    return [raw for raw in TRANSITIONS if visible_status(user, raw) == value]


def status_counts(user, queryset):
    counts = {value: 0 for value, _ in status_choices(user)}
    for row in queryset.values("status").annotate(n=Count("id")):
        key = visible_status(user, row["status"])
        if key in counts:
            counts[key] += row["n"]
    return counts


def allowed_transitions(user, ticket):
    if user.role != "it_admin":
        return []
    if ticket.status == "assigned" and ticket.engineer_id is None:
        return ["cancelled"]
    return list(TRANSITIONS.get(ticket.status, ()))

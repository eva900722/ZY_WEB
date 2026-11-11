from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from .models import Notification, Delivery
from apps.accounts.models import User


def event(ticket, event_name, message, *, send_email=False):
    ids = {ticket.reporter_id}
    if ticket.engineer_id:
        ids.add(ticket.engineer_id)
    ids.update(
        User.objects.filter(
            role="company_admin",
            company=ticket.company,
            is_active=True,
            deleted_at__isnull=True,
        ).values_list("pk", flat=True)
    )
    if event_name == "created":
        ids.update(
            User.objects.filter(
                role="it_admin", is_active=True, deleted_at__isnull=True
            ).values_list("pk", flat=True)
        )
    emails = set()
    for user in User.objects.filter(
        pk__in=ids, is_active=True, deleted_at__isnull=True
    ):
        Notification.objects.create(user=user, ticket=ticket, message=message)
        if user.email:
            emails.add(user.email)
    if not send_email:
        return
    for recipient in ticket.company.recipients.filter(is_active=True):
        if event_name in recipient.events:
            emails.add(recipient.email)
    for email in emails:
        Delivery.objects.create(
            recipient=email,
            subject=f"資訊管家｜{ticket.number}",
            body=message + "\n請登入系統查看可見的案件詳情。",
            next_attempt_at=timezone.now(),
        )


def deliver_batch(limit=50):
    # A locked row prevents concurrent workers from claiming the same delivery.
    # SMTP may accept a message immediately before a process crash: delivery is at-least-once.
    from datetime import timedelta

    count = 0
    for _ in range(limit):
        with transaction.atomic():
            item = (
                Delivery.objects.select_for_update(skip_locked=True)
                .filter(status="pending", next_attempt_at__lte=timezone.now())
                .order_by("pk")
                .first()
            )
            if not item:
                break
            item.attempts += 1
            try:
                send_mail(
                    item.subject, item.body, None, [item.recipient], fail_silently=False
                )
                item.status = "sent"
                item.sent_at = timezone.now()
                item.last_error = ""
            except Exception as exc:
                item.last_error = type(exc).__name__
                item.status = "failed" if item.attempts >= 5 else "pending"
                item.next_attempt_at = timezone.now() + timedelta(
                    minutes=2**item.attempts
                )
            item.save()
            count += 1
    return count

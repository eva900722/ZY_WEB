from django.core.exceptions import PermissionDenied
from apps.tickets.models import Ticket
from apps.accounts.models import User
from apps.audit.services import log


def require(user, *roles):
    if user.role not in roles:
        log(user, "permission.denied", result="denied")
        raise PermissionDenied


def tickets_for(user):
    qs = Ticket.objects.select_related(
        "company", "reporter", "engineer", "form_version"
    )
    if user.role == User.Role.IT_ADMIN:
        return qs
    if user.role == User.Role.ENGINEER:
        return qs.filter(engineer=user)
    if user.role == User.Role.COMPANY_ADMIN:
        return qs.filter(company_id=user.company_id)
    return qs.filter(company_id=user.company_id, reporter=user)


def internal_allowed(user):
    return user.role in [User.Role.IT_ADMIN, User.Role.ENGINEER]


def entries_for(user, ticket):
    q = ticket.entries.select_related("author").order_by("created_at", "pk")
    return q if internal_allowed(user) else q.filter(internal=False)


def attachments_for(user, ticket):
    q = ticket.attachments.all()
    return q if internal_allowed(user) else q.filter(internal=False)

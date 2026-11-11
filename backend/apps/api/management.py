from django.db import transaction
from django.db.models import Q
from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django import forms
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from common.permissions import require, tickets_for
from apps.accounts.models import User
from apps.accounts.forms import UserForm
from apps.accounts.views import managed_users
from apps.accounts.services import temporary_password
from apps.companies.models import Company, Location, Recipient
from apps.companies.views import CompanyForm
from apps.forms.models import FormVersion
from apps.forms.services import publish, validate_fields
from apps.audit.models import AuditLog
from apps.audit.services import log
from .helpers import valid, page, user_data


def company_data(c):
    return {
        "id": c.pk,
        "name": c.name,
        "code": c.code,
        "contact": c.contact,
        "is_active": c.is_active,
        "locations": "\n".join(c.locations.values_list("name", flat=True)),
        "emails": "\n".join(
            c.recipients.filter(is_active=True).values_list("email", flat=True)
        ),
    }


@api_view(["GET", "POST"])
def companies(request, pk=None):
    require(request.user, "it_admin")
    obj = get_object_or_404(Company, pk=pk) if pk else None
    if request.method == "GET":
        return Response(
            company_data(obj)
            if obj
            else {
                "items": [
                    company_data(c) for c in Company.objects.all().order_by("name")
                ]
            }
        )
    form = CompanyForm(request.data, instance=obj)
    data = valid(form)
    with transaction.atomic():
        if obj:
            Company.objects.select_for_update().get(pk=obj.pk)
        company = form.save()
        for name in data["locations"].splitlines():
            if name.strip():
                Location.objects.get_or_create(company=company, name=name.strip())
        company.recipients.update(is_active=False)
        for email in data["emails"]:
            recipient, _ = Recipient.objects.get_or_create(
                company=company,
                email=email,
                defaults={"events": ["created", "assigned", "updated", "completed"]},
            )
            recipient.is_active = True
            recipient.save()
        if not obj:
            v = FormVersion.objects.create(
                company=company, number=1, fields=[], created_by=request.user
            )
            publish(request.user, v)
        if not company.is_active:
            for session in Session.objects.filter(expire_date__gt=timezone.now()):
                uid = session.get_decoded().get(SESSION_KEY)
                if uid and company.user_set.filter(pk=uid).exists():
                    session.delete()
        log(
            request.user,
            "company.updated" if obj else "company.created",
            company.pk,
            company=company,
        )
    return Response(company_data(company), status=200 if obj else 201)


@api_view(["GET", "POST"])
def users(request, pk=None):
    require(request.user, "it_admin", "company_admin")
    obj = get_object_or_404(managed_users(request.user), pk=pk) if pk else None
    if request.method == "GET":
        if obj:
            return Response(user_data(obj))
        return Response(
            page(
                managed_users(request.user).order_by("username"), request, user_data, 30
            )
            | {
                "companies": [
                    {"id": c.pk, "name": c.name}
                    for c in Company.objects.filter(is_active=True)
                ]
                if request.user.role == "it_admin"
                else [],
                "roles": [{"value": v, "label": l} for v, l in User.Role.choices]
                if request.user.role == "it_admin"
                else [],
            }
        )
    if not obj:
        require(request.user, "it_admin")
    form = UserForm(request.data, instance=obj, actor=request.user)
    valid(form)
    with transaction.atomic():
        list(User.objects.select_for_update().filter(role="it_admin").order_by("pk"))
        existing = User.objects.select_for_update().get(pk=obj.pk) if obj else None
        if (
            existing
            and existing.role == "it_admin"
            and form.cleaned_data.get("role") != "it_admin"
            and existing.is_active
            and User.objects.filter(
                role="it_admin", is_active=True, deleted_at__isnull=True
            ).count()
            <= 1
        ):
            raise ValidationError({"message": "必須保留至少一位可用贊耀公司人員"})
        user = form.save(commit=False)
        if existing and existing.email != user.email:
            user.email_verified_at = None
        user.save()
        log(
            request.user,
            "account.updated" if obj else "account.created",
            user.pk,
            company=user.company,
        )
        result = {"user": user_data(user)}
        if not obj:
            result["temporary_password"] = temporary_password(request.user, user)
    return Response(result, status=200 if obj else 201)


@api_view(["POST"])
def user_action(request, pk):
    require(request.user, "it_admin")
    action = request.data.get("action")
    with transaction.atomic():
        list(User.objects.select_for_update().filter(role="it_admin").order_by("pk"))
        user = get_object_or_404(
            User.objects.select_for_update(), pk=pk, deleted_at__isnull=True
        )
        if action == "temporary":
            if not user.is_active:
                raise ValidationError({"message": "請先啟用帳號"})
            return Response(
                {
                    "temporary_password": temporary_password(request.user, user),
                    "username": user.username,
                }
            )
        if action not in ["enable", "disable", "delete"]:
            raise ValidationError({"message": "無效操作"})
        if (
            action in ["disable", "delete"]
            and user.role == "it_admin"
            and user.is_active
            and User.objects.filter(
                role="it_admin", is_active=True, deleted_at__isnull=True
            ).count()
            <= 1
        ):
            raise ValidationError({"message": "必須保留至少一位可用贊耀公司人員"})
        if (
            action in ["disable", "delete"]
            and user.assigned_tickets.exclude(
                status__in=["closed", "cancelled"]
            ).exists()
        ):
            raise ValidationError({"message": "此帳號仍有未結案件，請先交接"})
        user.is_active = action == "enable"
        if action == "delete":
            user.deleted_at = timezone.now()
        if action in ["disable", "delete"]:
            user.set_unusable_password()
            user.must_change_password = True
        user.save()
        log(request.user, "account." + action, user.pk, company=user.company)
    return Response({"message": "帳號已更新；重新啟用後請重設臨時密碼"})


def version_data(v):
    return {
        "id": v.pk,
        "company": v.company_id,
        "company_name": v.company.name,
        "number": v.number,
        "fields": v.fields,
        "published_at": v.published_at,
        "accepts_until": v.accepts_until,
    }


@api_view(["GET", "POST"])
def versions(request, pk=None):
    require(request.user, "it_admin")
    obj = get_object_or_404(FormVersion, pk=pk) if pk else None
    if request.method == "GET":
        return Response(
            version_data(obj)
            if obj
            else {
                "items": [
                    version_data(v)
                    for v in FormVersion.objects.select_related("company").order_by(
                        "company__name", "-number"
                    )
                ],
                "companies": [
                    {"id": c.pk, "name": c.name}
                    for c in Company.objects.filter(is_active=True)
                ],
            }
        )
    try:
        cid = int(request.data.get("company", obj.company_id if obj else 0))
    except (ValueError, TypeError):
        raise ValidationError({"message": "公司格式不正確"})
    company = get_object_or_404(Company, pk=cid, is_active=True)
    with transaction.atomic():
        Company.objects.select_for_update().get(pk=company.pk)
        if obj:
            obj = FormVersion.objects.select_for_update().get(pk=obj.pk)
            if obj.company_id != company.pk:
                raise ValidationError({"message": "不可變更草稿所屬公司"})
            if request.data.get("action") == "publish":
                publish(request.user, obj, request.data.get("policy") == "immediate")
                obj.refresh_from_db()
                return Response(version_data(obj))
            if obj.published_at:
                raise ValidationError({"message": "已發布版本請複製建立新版"})
        fields = validate_fields(request.data.get("fields", []))
        if obj:
            obj.fields = fields
            obj.save()
        else:
            last = (
                FormVersion.objects.filter(company=company).order_by("-number").first()
            )
            obj = FormVersion.objects.create(
                company=company,
                number=last.number + 1 if last else 1,
                fields=fields,
                created_by=request.user,
            )
        log(request.user, "form.draft_saved", obj.pk, company=company)
    return Response(version_data(obj))


@api_view(["GET", "POST"])
def notifications(request, pk=None, read_all=False):
    q = (
        request.user.notifications.filter(
            Q(ticket__isnull=True) | Q(ticket__in=tickets_for(request.user))
        )
        .select_related("ticket")
        .order_by("-pk")
    )
    if read_all:
        if request.method != "POST":
            return Response({"message": "請使用POST標記已讀"}, status=405, headers={"Allow": "POST, OPTIONS"})
        updated = q.filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"message": "已全部標記已讀", "updated": updated})
    if request.method == "POST":
        n = get_object_or_404(q, pk=pk)
        n.read_at = timezone.now()
        n.save(update_fields=["read_at"])
        return Response({"message": "已標記已讀"})

    def serialize(n):
        return {
            "id": n.pk,
            "message": n.message,
            "ticket_id": n.ticket_id,
            "read_at": n.read_at,
            "created_at": n.created_at,
        }

    return Response(
        page(q, request, serialize, 25)
        | {"unread": q.filter(read_at__isnull=True).count()}
    )


@api_view(["GET"])
def audit(request):
    require(request.user, "it_admin")
    q = AuditLog.objects.select_related("actor", "company").order_by("-pk")
    for key, lookup in [
        ("actor", "actor__username__icontains"),
        ("company", "company__name__icontains"),
        ("action", "action__icontains"),
        ("target", "target__icontains"),
    ]:
        if request.query_params.get(key):
            q = q.filter(**{lookup: request.query_params[key]})
    for key, lookup in [
        ("start", "created_at__date__gte"),
        ("end", "created_at__date__lte"),
    ]:
        if request.query_params.get(key):
            value = forms.DateField().clean(request.query_params[key])
            q = q.filter(**{lookup: value})
    if request.query_params.get("result") in ["success", "failed", "denied"]:
        q = q.filter(result=request.query_params["result"])

    def serialize(x):
        return {
            "id": x.pk,
            "actor": str(x.actor) if x.actor_id else "未登入",
            "role": x.role,
            "company_name": str(x.company) if x.company_id else "—",
            "action": x.action,
            "target": x.target,
            "details": x.details,
            "result": x.result,
            "created_at": x.created_at,
        }

    return Response(page(q, request, serialize, 40))

from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from apps.accounts.models import User
from apps.companies.models import Company
from apps.forms.models import FormVersion
from apps.forms.services import latest, accepted, dynamic_form
from apps.tickets.models import Ticket
from apps.tickets.forms import TicketForm, EntryForm, AssignmentForm
from apps.tickets.views import filtered
from apps.tickets.services import create_ticket, assign, update_status, add_entry
from apps.attachments.services import validate_uploads, store
from apps.audit.services import log
from common.permissions import (
    tickets_for,
    entries_for,
    attachments_for,
    internal_allowed,
    require,
)
from .helpers import valid, page


def summary(t):
    return {
        "id": t.pk,
        "number": t.number,
        "title": t.title,
        "company_name": t.company.name,
        "status": t.status,
        "status_label": t.get_status_display(),
        "engineer_name": str(t.engineer) if t.engineer_id else "尚未指派",
        "reporter_name": t.snapshot.get("display_name", ""),
        "created_at": t.created_at,
        "updated_at": t.updated_at,
        "revision": t.revision,
    }


def transitions(user, t):
    options = {
        "unassigned": ["cancelled"],
        "assigned": ["processing", "cancelled"],
        "processing": ["waiting", "completed", "cancelled"],
        "waiting": ["processing", "completed", "cancelled"],
        "completed": ["closed", "processing"],
        "closed": ["processing"],
        "cancelled": ["processing"],
    }.get(t.status, [])
    if user.role in ["reporter", "company_admin"]:
        options = ["closed"] if t.status == "completed" else []
    elif user.role == "engineer":
        options = (
            []
            if t.status in ["closed", "cancelled"]
            else [s for s in options if s not in ["closed", "cancelled"]]
        )
    return [{"value": s, "label": Ticket.Status(s).label} for s in options]


@api_view(["GET", "POST"])
def collection(request):
    if request.method == "GET":
        result = page(filtered(request.user, request.query_params), request, summary)
        counts = {s: 0 for s in Ticket.Status.values}
        counts.update(
            {
                x["status"]: x["n"]
                for x in tickets_for(request.user)
                .values("status")
                .annotate(n=Count("id"))
            }
        )
        return Response(
            result
            | {
                "counts": counts,
                "statuses": [
                    {"value": s, "label": label} for s, label in Ticket.Status.choices
                ],
                "companies": [
                    {"id": c.pk, "name": c.name}
                    for c in Company.objects.filter(is_active=True)
                ]
                if request.user.role == "it_admin"
                else [],
            }
        )
    require(request.user, "reporter", "company_admin", "it_admin")
    cid = (
        request.data.get("company")
        if request.user.role == "it_admin"
        else request.user.company_id
    )
    try:
        cid = int(cid)
        vid = int(request.data.get("form_version"))
    except (ValueError, TypeError):
        raise ValidationError({"message": "請選擇公司與有效的表單版本"})
    company = get_object_or_404(Company, pk=cid, is_active=True)
    version = get_object_or_404(
        FormVersion, pk=vid, company=company, published_at__isnull=False
    )
    clean = valid(TicketForm(request.data, user=request.user, company=company))
    dynamic = dynamic_form(version, request.data)
    values = valid(dynamic)
    answers = {k[6:]: str(v) if v is not None else "" for k, v in values.items()}
    import json

    try:
        previous = request.data.get("unmapped", [])
        if isinstance(previous, str):
            previous = json.loads(previous)
        if (
            not isinstance(previous, list)
            or len(previous) > 80
            or any(
                not isinstance(x, list)
                or len(x) != 2
                or any(not isinstance(v, str) or len(v) > 10000 for v in x)
                for x in previous
            )
        ):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValidationError({"message": "保留內容格式不正確"})
    if previous:
        answers["_unmapped"] = previous
    validated = validate_uploads(request.FILES.getlist("attachments"))
    paths = []
    try:
        with transaction.atomic():
            ticket = create_ticket(
                request.user, company, clean["reporter"], version, clean, answers
            )
            paths = store(ticket, request.user, validated)
    except DjangoValidationError as e:
        for p in paths:
            p.unlink(missing_ok=True)
        if not accepted(version):
            return Response(
                {"message": "表單已更新，請保留內容並切換新版", "code": "form_changed"},
                status=409,
            )
        raise
    except Exception:
        for p in paths:
            p.unlink(missing_ok=True)
        raise
    return Response(summary(ticket), status=201)


@api_view(["GET"])
def metadata(request):
    require(request.user, "reporter", "company_admin", "it_admin")
    cid = (
        request.query_params.get("company")
        if request.user.role == "it_admin"
        else request.user.company_id
    )
    companies = Company.objects.filter(is_active=True)
    if request.user.role != "it_admin":
        companies = companies.filter(pk=request.user.company_id)
    options = [{"id": c.pk, "name": c.name} for c in companies]
    if not cid:
        return Response({"companies": options, "version": None, "reporters": []})
    try:
        cid = int(cid)
    except (ValueError, TypeError):
        raise ValidationError({"message": "公司格式不正確"})
    company = get_object_or_404(companies, pk=cid)
    version = latest(company)
    people = User.objects.filter(
        company=company,
        is_active=True,
        deleted_at__isnull=True,
        role__in=["reporter", "company_admin"],
    )
    if request.user.role == "reporter":
        people = people.filter(pk=request.user.pk)
    old_id = request.query_params.get("version", "")
    old = (
        FormVersion.objects.filter(company=company, pk=int(old_id)).first()
        if str(old_id).isdigit()
        else None
    )
    return Response(
        {
            "accepted": bool(accepted(old)) if old else True,
            "companies": options,
            "company": company.pk,
            "locations": list(company.locations.values_list("name", flat=True)),
            "reporters": [{"id": u.pk, "name": str(u)} for u in people],
            "version": {
                "id": version.pk,
                "number": version.number,
                "fields": version.fields,
            }
            if version
            else None,
        }
    )


@api_view(["GET", "POST"])
def detail(request, pk):
    t = get_object_or_404(tickets_for(request.user), pk=pk)
    if request.method == "POST":
        action = request.data.get("action")
        paths = []
        try:
            if action == "assign":
                require(request.user, "it_admin")
                d = valid(AssignmentForm(request.data))
                assign(request.user, pk, d["revision"], d["engineer"], d["reason"])
            elif action == "status":
                from django import forms

                f = forms.Form(request.data)
                f.fields = {
                    "revision": forms.IntegerField(),
                    "status": forms.ChoiceField(
                        choices=[
                            (x["value"], x["label"])
                            for x in transitions(request.user, t)
                        ]
                    ),
                    "reason": forms.CharField(max_length=10000),
                }
                d = valid(f)
                update_status(request.user, pk, d["revision"], d["status"], d["reason"])
            elif action == "entry":
                d = valid(EntryForm(request.data))
                validated = validate_uploads(request.FILES.getlist("attachments"))
                with transaction.atomic():
                    entry = add_entry(
                        request.user, pk, d["revision"], d["body"], d["internal"]
                    )
                    paths = store(entry.ticket, request.user, validated, entry)
            else:
                raise ValidationError({"message": "無效操作"})
        except DjangoValidationError as e:
            for p in paths:
                p.unlink(missing_ok=True)
            return Response(
                {"message": "；".join(e.messages), "code": "conflict"}, status=409
            )
        except Exception:
            for p in paths:
                p.unlink(missing_ok=True)
            raise
        t = get_object_or_404(tickets_for(request.user), pk=pk)
    else:
        log(request.user, "ticket.view", t.number, company=t.company, request=request)
    result = summary(t) | {
        "description": t.description,
        "anydesk": t.anydesk,
        "snapshot": t.snapshot,
        "form_version": t.form_version.number,
        "answers": [
            {"label": f["label"], "value": t.answers.get(f["key"], "")}
            for f in t.form_version.fields
        ]
        + [
            {"label": "舊版保留：" + x[0], "value": x[1]}
            for x in t.answers.get("_unmapped", [])
        ],
        "entries": [
            {
                "id": e.pk,
                "author": str(e.author),
                "body": e.body,
                "internal": e.internal,
                "created_at": e.created_at,
            }
            for e in entries_for(request.user, t)
        ],
        "attachments": [
            {
                "id": a.pk,
                "name": a.name,
                "size": a.size,
                "internal": a.internal,
                "url": f"/attachments/{a.pk}/",
            }
            for a in attachments_for(request.user, t)
        ],
        "transitions": transitions(request.user, t),
        "can_internal": internal_allowed(request.user),
        "can_comment": t.status not in ["closed", "cancelled"],
    }
    result["engineers"] = (
        [
            {"id": u.pk, "name": str(u)}
            for u in User.objects.filter(
                role="engineer", is_active=True, deleted_at__isnull=True
            )
        ]
        if request.user.role == "it_admin"
        else []
    )
    return Response(result)

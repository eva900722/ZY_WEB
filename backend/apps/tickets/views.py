import json
from django import forms
from django.db import transaction
from django.db.models import Q, Count
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import JsonResponse
from apps.companies.models import Company
from apps.forms.models import FormVersion
from apps.forms.services import latest, accepted, dynamic_form
from apps.attachments.services import validate_uploads, store
from apps.audit.services import log
from common.permissions import (
    tickets_for,
    entries_for,
    attachments_for,
    internal_allowed,
    require,
)
from .models import Ticket
from .forms import TicketForm, EntryForm, AssignmentForm, StatusForm
from .services import create_ticket, assign, claim, update_status, add_entry


def filtered(user, params):
    q = tickets_for(user)
    if params.get("q"):
        q = q.filter(Q(number__icontains=params["q"]) | Q(title__icontains=params["q"]))
    if params.get("status") in Ticket.Status.values:
        q = q.filter(status=params["status"])
    if params.get("company", "").isdigit():
        q = q.filter(company_id=params["company"])
    for param, lookup in [
        ("start", "created_at__date__gte"),
        ("end", "created_at__date__lte"),
    ]:
        if params.get(param):
            try:
                date = forms.DateField().clean(params[param])
                q = q.filter(**{lookup: date})
            except ValidationError:
                q = q.none()
    return q.order_by("-created_at")


@login_required
def dashboard(request):
    from django.core.paginator import Paginator

    q = filtered(request.user, request.GET)
    rows = Paginator(q, 25).get_page(request.GET.get("page"))
    counts = {s: 0 for s in Ticket.Status.values}
    counts.update(
        {
            x["status"]: x["n"]
            for x in tickets_for(request.user).values("status").annotate(n=Count("id"))
        }
    )
    return render(
        request,
        "tickets/list.html",
        {
            "rows": rows,
            "title": "案件工作台",
            "statuses": Ticket.Status.choices,
            "counts": counts,
            "companies": Company.objects.all()
            if request.user.role == "it_admin"
            else [],
        },
    )


@login_required
def new(request):
    require(request.user, "reporter", "company_admin", "it_admin")
    if request.user.role == "it_admin":
        cid = request.GET.get("company") or request.POST.get("company")
        if not cid or not str(cid).isdigit():
            return render(
                request,
                "tickets/select_company.html",
                {
                    "companies": Company.objects.filter(is_active=True),
                    "title": "選擇報修公司",
                },
            )
        company = get_object_or_404(Company, pk=cid, is_active=True)
    else:
        company = request.user.company
    current = latest(company)
    if not current:
        return render(
            request,
            "message.html",
            {"title": "公司尚未發布報修表單，請聯絡管理者"},
            status=400,
        )
    vid = request.POST.get("form_version") or current.pk
    if not str(vid).isdigit():
        return render(
            request, "message.html", {"title": "表單版本格式不正確"}, status=400
        )
    version = get_object_or_404(
        FormVersion, pk=vid, company=company, published_at__isnull=False
    )
    data = request.POST.copy() if request.method == "POST" else None
    previous = []
    switched = False
    if data is not None:
        try:
            previous = json.loads(data.get("unmapped", "[]"))
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
            return render(
                request, "message.html", {"title": "舊版保留內容格式不正確"}, status=400
            )
    if data is not None and data.get("switch_version") == "1":
        values = {k[6:]: v for k, v in data.items() if k.startswith("field_")}
        for f in version.fields:
            newfield = next((x for x in current.fields if x["key"] == f["key"]), None)
            if values.get(f["key"]) and (
                not newfield
                or newfield["type"] != f["type"]
                or (
                    newfield["type"] == "select"
                    and values[f["key"]] not in newfield["options"]
                )
            ):
                previous.append((f["label"], values[f["key"]]))
                if newfield:
                    data.pop("field_" + f["key"], None)
        version = current
        switched = True
    form = TicketForm(data, user=request.user, company=company)
    dynamic = dynamic_form(version, data)
    if request.method == "POST" and not switched:
        paths = []
        if form.is_valid() and dynamic.is_valid():
            try:
                validated = validate_uploads(request.FILES.getlist("attachments"))
                with transaction.atomic():
                    answers = {
                        k[6:]: str(v) if v is not None else ""
                        for k, v in dynamic.cleaned_data.items()
                    }
                    if previous:
                        answers["_unmapped"] = previous
                    ticket = create_ticket(
                        request.user,
                        company,
                        form.cleaned_data["reporter"],
                        version,
                        form.cleaned_data,
                        answers,
                    )
                    paths = store(ticket, request.user, validated)
                messages.success(request, "報修已建立")
                return redirect("ticket_detail", pk=ticket.pk)
            except ValidationError as e:
                for p in paths:
                    p.unlink(missing_ok=True)
                form.add_error(None, "；".join(e.messages))
            except Exception:
                for p in paths:
                    p.unlink(missing_ok=True)
                raise
    response = render(
        request,
        "tickets/new.html",
        {
            "form": form,
            "dynamic": dynamic,
            "version": version,
            "current": current,
            "company": company,
            "title": "新增報修",
            "obsolete": not accepted(version),
            "previous": previous,
            "switched": switched,
            "unmapped_json": json.dumps(previous, ensure_ascii=False),
        },
    )
    response["Cache-Control"] = "no-store"
    return response


@login_required
def form_status(request, company_id):
    company = get_object_or_404(Company, is_active=True, pk=company_id)
    if request.user.role != "it_admin" and (
        request.user.company_id != company.pk
    ):
        raise PermissionDenied
    v = latest(company)
    vid = request.GET.get("version", "")
    old = (
        FormVersion.objects.filter(company=company, pk=vid).first()
        if vid.isdigit()
        else None
    )
    return JsonResponse(
        {
            "latest": v.pk if v else None,
            "number": v.number if v else None,
            "accepted": bool(old and accepted(old)),
        }
    )


@login_required
def detail(request, pk):
    ticket = get_object_or_404(tickets_for(request.user), pk=pk)
    ef = EntryForm(initial={"revision": ticket.revision})
    if not internal_allowed(request.user):
        ef.fields.pop("internal")
    af = AssignmentForm(initial={"revision": ticket.revision})
    sf = StatusForm(initial={"revision": ticket.revision})
    transitions = {
        "unassigned": ["cancelled"],
        "assigned": ["processing", "cancelled"],
        "processing": ["waiting", "completed", "cancelled"],
        "waiting": ["processing", "completed", "cancelled"],
        "completed": ["closed", "processing"],
        "closed": ["processing"],
        "cancelled": ["processing"],
    }
    statuses = transitions.get(ticket.status, [])
    if request.user.role in ["reporter", "company_admin"]:
        statuses = ["closed"] if ticket.status == "completed" else []
    sf.fields["status"].choices = [(s, Ticket.Status(s).label) for s in statuses]
    if request.method == "POST":
        action = request.POST.get("action")
        paths = []
        try:
            if action == "assign":
                require(request.user, "it_admin")
                af = AssignmentForm(request.POST)
                if af.is_valid():
                    assign(
                        request.user,
                        pk,
                        af.cleaned_data["revision"],
                        af.cleaned_data["engineer"],
                        af.cleaned_data["reason"],
                    )
                    return redirect("ticket_detail", pk=pk)
            elif action == "claim":
                revision = forms.IntegerField(min_value=1).clean(request.POST.get("revision"))
                claim(request.user, pk, revision)
                return redirect("ticket_detail", pk=pk)
            elif action == "status":
                sf = StatusForm(request.POST)
                sf.fields["status"].choices = [
                    (s, Ticket.Status(s).label) for s in statuses
                ]
                if sf.is_valid():
                    update_status(
                        request.user,
                        pk,
                        sf.cleaned_data["revision"],
                        sf.cleaned_data["status"],
                        sf.cleaned_data["reason"],
                    )
                    return redirect("ticket_detail", pk=pk)
            elif action == "entry":
                ef = EntryForm(request.POST)
                if ef.is_valid():
                    validated = validate_uploads(request.FILES.getlist("attachments"))
                    with transaction.atomic():
                        entry = add_entry(
                            request.user,
                            pk,
                            ef.cleaned_data["revision"],
                            ef.cleaned_data["body"],
                            ef.cleaned_data["internal"],
                        )
                        paths = store(entry.ticket, request.user, validated, entry)
                    return redirect("ticket_detail", pk=pk)
            else:
                raise ValidationError("無效操作")
        except ValidationError as e:
            for p in paths:
                p.unlink(missing_ok=True)
            messages.error(request, "；".join(e.messages))
        except Exception:
            for p in paths:
                p.unlink(missing_ok=True)
            raise
    else:
        log(
            request.user,
            "ticket.view",
            ticket.number,
            company=ticket.company,
            request=request,
        )
    answers = [
        (f["label"], ticket.answers.get(f["key"], ""))
        for f in ticket.form_version.fields
    ] + [("舊版保留：" + x[0], x[1]) for x in ticket.answers.get("_unmapped", [])]
    response = render(
        request,
        "tickets/detail.html",
        {
            "ticket": ticket,
            "entries": entries_for(request.user, ticket),
            "attachments": attachments_for(request.user, ticket),
            "entry_form": ef,
            "assignment_form": af,
            "status_form": sf,
            "can_status": bool(statuses),
            "answers": answers,
            "title": ticket.number,
        },
    )
    response["Cache-Control"] = "private, no-store"
    return response

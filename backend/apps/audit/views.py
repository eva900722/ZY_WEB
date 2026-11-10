from django import forms
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from common.permissions import require
from .models import AuditLog


@login_required
def query(request):
    require(request.user, "it_admin")
    qs = AuditLog.objects.select_related("actor", "company").order_by("-pk")
    for key, lookup in [
        ("actor", "actor__username__icontains"),
        ("company", "company__name__icontains"),
        ("action", "action__icontains"),
        ("target", "target__icontains"),
    ]:
        if request.GET.get(key):
            qs = qs.filter(**{lookup: request.GET[key]})
    if request.GET.get("result") in ["success", "failed", "denied"]:
        qs = qs.filter(result=request.GET["result"])
    for key, lookup in [
        ("start", "created_at__date__gte"),
        ("end", "created_at__date__lte"),
    ]:
        if request.GET.get(key):
            try:
                qs = qs.filter(**{lookup: forms.DateField().clean(request.GET[key])})
            except forms.ValidationError:
                qs = qs.none()
    return render(
        request,
        "audit/list.html",
        {
            "rows": Paginator(qs, 50).get_page(request.GET.get("page")),
            "title": "操作紀錄",
        },
    )

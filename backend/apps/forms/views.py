from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.db import transaction
from .models import FormVersion
from .services import validate_fields, publish
from apps.companies.models import Company
from common.permissions import require
from apps.audit.services import log


class DraftForm(forms.Form):
    company = forms.ModelChoiceField(
        label="公司", queryset=Company.objects.filter(is_active=True)
    )
    fields = forms.JSONField(
        required=False,
        widget=forms.HiddenInput,
        initial=[
            {
                "key": "device",
                "label": "設備類型",
                "type": "select",
                "required": True,
                "options": ["電腦", "印表機", "網路", "其他"],
            }
        ],
    )

    def clean_fields(self):
        return validate_fields(self.cleaned_data["fields"])


@login_required
def versions(request, pk=None):
    require(request.user, "it_admin")
    draft = (
        get_object_or_404(FormVersion, pk=pk, published_at__isnull=True) if pk else None
    )
    copy_id = request.GET.get("copy", "")
    source = (
        FormVersion.objects.filter(pk=copy_id).first() if copy_id.isdigit() else None
    )
    initial = (
        {"company": (draft or source).company_id, "fields": (draft or source).fields}
        if draft or source
        else {}
    )
    form = DraftForm(request.POST or None, initial=initial)
    if draft:
        form.fields["company"].disabled = True
    if request.method == "POST" and form.is_valid():
        company = form.cleaned_data["company"]
        with transaction.atomic():
            Company.objects.select_for_update().get(pk=company.pk)
            if draft:
                v = FormVersion.objects.select_for_update().get(pk=draft.pk)
                if v.published_at:
                    form.add_error(None, "此版本已發布，請建立新版")
                    return render(
                        request,
                        "forms/versions.html",
                        {
                            "form": form,
                            "rows": FormVersion.objects.select_related(
                                "company"
                            ).order_by("-pk"),
                            "title": "表單版本管理",
                        },
                    )
                v.fields = form.cleaned_data["fields"]
                v.save()
            else:
                last = (
                    FormVersion.objects.filter(company=company)
                    .order_by("-number")
                    .first()
                )
                v = FormVersion.objects.create(
                    company=company,
                    number=last.number + 1 if last else 1,
                    fields=form.cleaned_data["fields"],
                    created_by=request.user,
                )
            log(
                request.user,
                "form.draft_updated" if draft else "form.draft_created",
                v.pk,
                company=company,
            )
        messages.success(request, "草稿已儲存，確認後可發布")
        return redirect("versions")
    return render(
        request,
        "forms/versions.html",
        {
            "form": form,
            "rows": FormVersion.objects.select_related("company").order_by(
                "company__name", "-number"
            ),
            "title": "表單版本管理",
            "editing": draft,
        },
    )


@login_required
@require_POST
def publish_view(request, pk):
    require(request.user, "it_admin")
    v = get_object_or_404(FormVersion, pk=pk)
    try:
        publish(request.user, v, request.POST.get("policy") == "immediate")
        messages.success(request, "版本已發布")
    except ValidationError as e:
        messages.error(request, "；".join(e.messages))
    return redirect("versions")

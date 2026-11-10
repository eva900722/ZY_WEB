from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib import messages
from .models import Company, Location, Recipient
from common.permissions import require
from apps.audit.services import log
from apps.forms.models import FormVersion
from apps.forms.services import publish


class CompanyForm(forms.ModelForm):
    locations = forms.CharField(
        label="辦公室／據點（每行一筆）", widget=forms.Textarea, required=False
    )
    emails = forms.CharField(
        label="進度通知收件人（每行一筆）", widget=forms.Textarea, required=False
    )

    class Meta:
        model = Company
        fields = ["name", "code", "contact", "is_active"]

    def clean_emails(self):
        values = [
            x.strip() for x in self.cleaned_data["emails"].splitlines() if x.strip()
        ]
        for value in values:
            forms.EmailField().clean(value)
        return values


@login_required
def companies(request):
    require(request.user, "it_admin")
    return render(
        request,
        "companies/list.html",
        {"rows": Company.objects.all().order_by("name"), "title": "公司管理"},
    )


@login_required
def edit(request, pk=None):
    require(request.user, "it_admin")
    obj = get_object_or_404(Company, pk=pk) if pk else Company()
    initial = (
        {
            "locations": "\n".join(obj.locations.values_list("name", flat=True)),
            "emails": "\n".join(
                obj.recipients.filter(is_active=True).values_list("email", flat=True)
            ),
        }
        if pk
        else {}
    )
    form = CompanyForm(request.POST or None, instance=obj, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            company = form.save()
            for name in form.cleaned_data["locations"].splitlines():
                if name.strip():
                    Location.objects.get_or_create(company=company, name=name.strip())
            company.recipients.update(is_active=False)
            for email in form.cleaned_data["emails"]:
                recipient, _ = Recipient.objects.get_or_create(
                    company=company,
                    email=email,
                    defaults={
                        "events": ["created", "assigned", "updated", "completed"]
                    },
                )
                recipient.is_active = True
                recipient.save()
            if not pk:
                v = FormVersion.objects.create(
                    company=company, number=1, fields=[], created_by=request.user
                )
                publish(request.user, v)
            if not company.is_active:
                # Invalidate password-derived sessions so re-enable cannot revive them.
                from django.contrib.sessions.models import Session
                from django.contrib.auth import SESSION_KEY

                for session in Session.objects.filter(
                    expire_date__gt=__import__(
                        "django.utils.timezone", fromlist=["now"]
                    ).now()
                ):
                    uid = session.get_decoded().get(SESSION_KEY)
                    if uid and company.user_set.filter(pk=uid).exists():
                        session.delete()
            log(
                request.user,
                "company.updated" if pk else "company.created",
                company.pk,
                company=company,
            )
        messages.success(request, "公司資料已儲存")
        return redirect("companies")
    return render(
        request,
        "generic_form.html",
        {"form": form, "title": "修改公司" if pk else "新增公司"},
    )

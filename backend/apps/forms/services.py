import re
from datetime import timedelta
from django import forms
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import FormVersion
from apps.companies.models import Company
from apps.audit.services import log


def validate_fields(fields):
    if not isinstance(fields, list) or len(fields) > 40:
        raise ValidationError("欄位必須為清單，最多40個")
    keys = set()
    for f in fields:
        if (
            not isinstance(f, dict)
            or not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", str(f.get("key", "")))
            or f["key"] in keys
        ):
            raise ValidationError("欄位 key 須唯一，使用小寫英數及底線")
        keys.add(f["key"])
        if (
            f.get("type") not in ["text", "textarea", "number", "date", "select"]
            or not isinstance(f.get("label"), str)
            or not 1 <= len(f["label"]) <= 100
        ):
            raise ValidationError("欄位型態或標籤不正確")
        if not isinstance(f.get("required", False), bool):
            raise ValidationError("required 必須為 true 或 false")
        if f["type"] == "select" and (
            not isinstance(f.get("options"), list)
            or not f["options"]
            or len(f["options"]) > 100
            or any(
                not isinstance(x, str) or not 1 <= len(x) <= 100 for x in f["options"]
            )
        ):
            raise ValidationError("選項格式不正確")
    return fields


def dynamic_form(version, data=None):
    result = forms.Form(data=data)
    if version:
        for f in version.fields:
            kw = {"label": f["label"], "required": f.get("required", False)}
            typ = f["type"]
            if typ == "select":
                field = forms.ChoiceField(
                    choices=[("", "請選擇")] + [(x, x) for x in f["options"]], **kw
                )
            elif typ == "number":
                field = forms.DecimalField(max_digits=16, decimal_places=4, **kw)
            elif typ == "date":
                field = forms.DateField(
                    widget=forms.DateInput(attrs={"type": "date"}), **kw
                )
            else:
                field = forms.CharField(
                    max_length=10000 if typ == "textarea" else 500,
                    widget=forms.Textarea if typ == "textarea" else forms.TextInput,
                    **kw,
                )
            result.fields["field_" + f["key"]] = field
    return result


def latest(company):
    return (
        FormVersion.objects.filter(company=company, published_at__isnull=False)
        .order_by("-number")
        .first()
    )


def accepted(version):
    if not version.published_at:
        return False
    current = latest(version.company)
    return current and (
        current.pk == version.pk
        or (version.accepts_until and version.accepts_until > timezone.now())
    )


@transaction.atomic
def publish(actor, version, immediate=False):
    Company.objects.select_for_update().get(pk=version.company_id)
    version = FormVersion.objects.select_for_update().get(pk=version.pk)
    if version.published_at:
        raise ValidationError("已發布版本不可修改或重新發布")
    validate_fields(version.fields)
    old = latest(version.company)
    if immediate:
        FormVersion.objects.filter(
            company=version.company, published_at__isnull=False
        ).update(accepts_until=timezone.now())
    elif old:
        old.accepts_until = timezone.now() + timedelta(hours=24)
        old.save(update_fields=["accepts_until"])
    version.published_at = timezone.now()
    version.save(update_fields=["published_at"])
    log(
        actor,
        "form.published",
        version.pk,
        company=version.company,
        details={"number": version.number, "stop_old": immediate},
    )

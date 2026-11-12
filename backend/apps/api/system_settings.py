from common.permissions import require
from django import forms
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.audit.services import log
from apps.notifications.configuration import (
    BASIC_FIELDS,
    MAIL_FIELDS,
    decrypt_password,
    encrypt_password,
    settings_data,
)
from apps.notifications.models import Delivery, SystemSettings

from .helpers import valid


class BasicForm(forms.Form):
    platform_name = forms.CharField(max_length=60)
    company_name = forms.CharField(max_length=100)
    contact_phone = forms.CharField(max_length=50, required=False)
    contact_email = forms.EmailField(required=False)


class MailForm(forms.Form):
    smtp_host = forms.RegexField(r"^[a-zA-Z0-9][a-zA-Z0-9.\-]*$", max_length=253)
    smtp_port = forms.IntegerField(min_value=1, max_value=65535)
    smtp_security = forms.ChoiceField(
        choices=[("starttls", "STARTTLS"), ("ssl", "SSL/TLS"), ("none", "無加密")]
    )
    smtp_auth = forms.BooleanField(required=False)
    smtp_username = forms.CharField(max_length=254, required=False)
    smtp_password = forms.CharField(max_length=1024, required=False, strip=False)
    sender_email = forms.EmailField()
    sender_name = forms.CharField(max_length=100, required=False)

    def clean(self):
        data = super().clean()
        if data.get("smtp_auth") and not data.get("smtp_username"):
            self.add_error("smtp_username", "請輸入 SMTP 帳號")
        for field in ("sender_name", "smtp_username"):
            if any(c in data.get(field, "") for c in "\r\n"):
                self.add_error(field, "不得包含換行")
        return data


@api_view(["GET", "POST"])
def configuration(request):
    require(request.user, "it_admin")
    if request.method == "GET":
        return Response(
            settings_data(
                SystemSettings.objects.filter(pk=1).first() or SystemSettings()
            )
        )
    section = request.data.get("section")
    if section not in ("basic", "mail"):
        raise ValidationError({"message": "設定區塊不正確"})
    data = valid((BasicForm if section == "basic" else MailForm)(request.data))
    with transaction.atomic():
        SystemSettings.objects.get_or_create(pk=1)
        obj = SystemSettings.objects.select_for_update().get(pk=1)
        if request.data.get("revision") != obj.revision:
            return Response(
                {"message": "設定已由其他人更新，請重新載入後再修改。"}, status=409
            )
        fields = BASIC_FIELDS if section == "basic" else MAIL_FIELDS
        changed = [field for field in fields if getattr(obj, field) != data[field]]
        if section == "mail":
            password = data["smtp_password"]
            if not password and not obj.smtp_override:
                password = settings.EMAIL_HOST_PASSWORD
            if data["smtp_auth"]:
                if password:
                    obj.smtp_password_encrypted = encrypt_password(password)
                    changed.append("smtp_password")
                elif not decrypt_password(obj.smtp_password_encrypted):
                    raise ValidationError({"message": "請輸入 SMTP 密碼"})
            if not obj.smtp_override:
                changed.append("smtp_override")
            obj.smtp_override = True
        for field in fields:
            setattr(obj, field, data[field])
        obj.revision += 1
        obj.save()
        log(
            request.user,
            "system.settings_updated",
            "system",
            details={"section": section, "fields": changed},
            request=request,
        )
    return Response(settings_data(obj))


class TestMailForm(forms.Form):
    recipient = forms.EmailField()


@api_view(["GET", "POST"])
def test_mail(request, pk=None):
    require(request.user, "it_admin")
    if request.method == "GET":
        if pk is None:
            raise ValidationError({"message": "請指定測試信"})
        item = get_object_or_404(Delivery, pk=pk, is_test=True)
        return Response(
            {
                "id": item.pk,
                "status": item.status,
                "attempts": item.attempts,
                "last_error": item.last_error,
                "sent_at": item.sent_at,
            }
        )
    if pk is not None:
        return Response(status=405)
    data = valid(TestMailForm(request.data))
    obj = SystemSettings.objects.filter(pk=1).first()
    if not obj or not obj.smtp_override:
        raise ValidationError({"message": "請先儲存 SMTP 設定，再寄送測試信。"})
    with transaction.atomic():
        item = Delivery.objects.create(
            is_test=True,
            recipient=data["recipient"],
            subject=f"{obj.platform_name}｜寄信測試",
            body="這是一封系統測試信，用於確認 SMTP 寄信服務。",
            next_attempt_at=timezone.now(),
        )
        log(request.user, "system.test_mail_queued", item.pk, request=request)
    return Response({"id": item.pk, "status": item.status}, status=201)

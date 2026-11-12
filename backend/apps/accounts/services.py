import secrets, hashlib
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import User, ActionToken
from apps.audit.services import log


def digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


@transaction.atomic
def temporary_password(actor, user):
    user = User.objects.select_for_update().get(pk=user.pk)
    raw = secrets.token_urlsafe(15)
    user.set_password(raw)
    user.must_change_password = True
    user.temporary_expires_at = timezone.now() + timedelta(
        hours=settings.TEMP_PASSWORD_HOURS
    )
    user.save()
    ActionToken.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )
    log(actor, "account.temporary_password", user.pk, company=user.company)
    return raw


EMAIL_RECOVERY_DISABLED = "不提供Email驗證或自助重設密碼。報修者請聯絡本公司管理者或贊耀公司人員確認身分並重設臨時密碼，公司管理者請聯絡贊耀公司人員；登入後必須先更換自己的密碼。"


def issue_token(user, purpose):
    raise ValidationError(EMAIL_RECOVERY_DISABLED)


def consume_token(raw, password=None):
    raise ValidationError(EMAIL_RECOVERY_DISABLED)

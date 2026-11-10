import secrets, hashlib
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from .models import User, ActionToken
from apps.audit.services import log
from apps.notifications.models import Delivery


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


@transaction.atomic
def issue_token(user, purpose):
    user = User.objects.select_for_update().get(pk=user.pk)
    ActionToken.objects.filter(user=user, purpose=purpose, used_at__isnull=True).update(
        used_at=timezone.now()
    )
    raw = secrets.token_urlsafe(32)
    ActionToken.objects.create(
        user=user,
        purpose=purpose,
        digest=digest(raw),
        email=user.email,
        expires_at=timezone.now() + timedelta(minutes=settings.TOKEN_MINUTES),
    )
    url = f"{settings.SITE_URL}/accounts/token/{raw}/"
    Delivery.objects.create(
        recipient=user.email,
        subject="資訊管家：" + ("驗證 Email" if purpose == "verify" else "重設密碼"),
        body="請於30分鐘內開啟連結：" + url,
        next_attempt_at=timezone.now(),
    )
    return raw


@transaction.atomic
def consume_token(raw, password=None):
    # Lock the user before token, matching issue_token/reset lock order.
    found = ActionToken.objects.filter(digest=digest(raw)).first()
    if not found:
        raise ValidationError("連結無效或已過期")
    user = User.objects.select_for_update().get(pk=found.user_id)
    token = ActionToken.objects.select_for_update().get(pk=found.pk)
    if (
        token.used_at
        or token.expires_at <= timezone.now()
        or not user.is_active
        or user.deleted_at
        or (user.company_id and not user.company.is_active)
        or token.email != user.email
    ):
        raise ValidationError("連結無效或已過期")
    if token.purpose == "reset":
        if not user.email_verified_at:
            raise ValidationError("信箱尚未驗證")
        validate_password(password, user)
        user.set_password(password)
        user.must_change_password = False
        user.temporary_expires_at = None
    else:
        user.email_verified_at = timezone.now()
    user.save()
    token.used_at = timezone.now()
    token.save(update_fields=["used_at"])
    log(user, "account." + token.purpose, user.pk)
    return token.purpose

import hashlib
from datetime import timedelta
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from apps.accounts.models import User, LoginAttempt, ActionToken
from apps.accounts.forms import LoginForm, PasswordForm, ProfileForm
from apps.accounts.services import EMAIL_RECOVERY_DISABLED
from apps.audit.services import log
from .helpers import valid, user_data
from apps.notifications.configuration import public_settings


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def session(request):
    return Response(
        {"user": user_data(request.user), "csrf_token": get_token(request._request), "platform": public_settings()}
    )


@csrf_protect
@api_view(["POST"])
@permission_classes([AllowAny])
def sign_in(request):
    data = valid(LoginForm(request.data))
    username = data["username"].lower()
    now = timezone.now()
    key = hashlib.sha256(
        (username + "|" + request.META.get("REMOTE_ADDR", "")).encode()
    ).hexdigest()
    with transaction.atomic():
        attempt, _ = LoginAttempt.objects.get_or_create(
            key=key, defaults={"window_start": now}
        )
        attempt = LoginAttempt.objects.select_for_update().get(pk=attempt.pk)
        if attempt.window_start < now - timedelta(minutes=15):
            attempt.failures = 0
            attempt.window_start = now
        user = (
            None
            if attempt.failures >= 5
            else authenticate(
                request._request, username=username, password=data["password"]
            )
        )
        attempt.failures = 0 if user else attempt.failures + 1
        attempt.save()
    if not user:
        log(None, "account.login", result="failed", request=request)
        raise ValidationError(
            {"message": "帳號或密碼不正確、帳號不可用，或嘗試過於頻繁。"}
        )
    login(request._request, user)
    log(user, "account.login", request=request)
    return Response(
        {"user": user_data(user), "csrf_token": get_token(request._request)}
    )


@api_view(["POST"])
def sign_out(request):
    log(request.user, "account.logout", request=request)
    logout(request._request)
    return Response({"message": "已登出"})


@api_view(["POST"])
def password(request):
    data = valid(PasswordForm(request.user, request.data))
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=request.user.pk)
        if user.password != request.user.password:
            raise ValidationError({"message": "密碼已變更，請重新登入"})
        user.set_password(data["new_password1"])
        user.must_change_password = False
        user.temporary_expires_at = None
        user.save()
        ActionToken.objects.filter(user=user, used_at__isnull=True).update(
            used_at=timezone.now()
        )
        log(user, "account.password_changed", user.pk)
        update_session_auth_hash(request._request, user)
    return Response(
        {
            "user": user_data(user),
            "message": "密碼已更新",
            "csrf_token": get_token(request._request),
        }
    )


@csrf_protect
@api_view(["POST"])
@permission_classes([AllowAny])
def forgot(request):
    return Response({"message": EMAIL_RECOVERY_DISABLED})


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def token(request, raw):
    return Response({"message": EMAIL_RECOVERY_DISABLED}, status=410)


@api_view(["POST"])
def verify(request):
    return Response({"message": EMAIL_RECOVERY_DISABLED}, status=410)


@api_view(["GET", "POST"])
def profile(request):
    if request.method == "GET":
        return Response({"user": user_data(request.user)})
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=request.user.pk)
        form = ProfileForm(request.data, instance=user)
        data = valid(form)
        changed = form.changed_data
        if "email" in changed:
            user.email_verified_at = None
            ActionToken.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        if changed:
            for field in ProfileForm.Meta.fields:
                setattr(user, field, data[field])
            user.save(update_fields=changed + (["email_verified_at"] if "email" in changed else []))
            log(user, "account.profile_updated", user.pk, company=user.company, details={"fields": changed}, request=request)
    return Response({"user": user_data(user), "message": "個人資料已更新"})

import hashlib
from datetime import timedelta
from django import forms
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from .models import User, LoginAttempt, ActionToken
from .forms import LoginForm, PasswordForm, UserForm
from .services import temporary_password, issue_token, consume_token, digest
from common.permissions import require
from apps.audit.services import log


class ForgotForm(forms.Form):
    username = forms.CharField(label="登入帳號", max_length=150)


def login_view(request):
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"].lower()
        ip = request.META.get("REMOTE_ADDR", "")
        key = hashlib.sha256((username + "|" + ip).encode()).hexdigest()
        now = timezone.now()
        with transaction.atomic():
            attempt, _ = LoginAttempt.objects.get_or_create(
                key=key, defaults={"window_start": now}
            )
            attempt = LoginAttempt.objects.select_for_update().get(pk=attempt.pk)
            if attempt.window_start < now - timedelta(minutes=15):
                attempt.failures = 0
                attempt.window_start = now
            blocked = attempt.failures >= 5
            user = (
                None
                if blocked
                else authenticate(
                    request, username=username, password=form.cleaned_data["password"]
                )
            )
            if user:
                attempt.failures = 0
            else:
                attempt.failures += 1
            attempt.save()
        if user:
            login(request, user)
            log(user, "account.login", request=request)
            return redirect("password" if user.must_change_password else "dashboard")
        log(None, "account.login", result="failed", request=request)
        form.add_error(
            None, "帳號或密碼不正確、帳號不可用，或嘗試過於頻繁。請稍後重試。"
        )
    return render(
        request, "accounts/login.html", {"form": form, "title": "登入資訊管家"}
    )


@login_required
@require_POST
def logout_view(request):
    log(request.user, "account.logout", request=request)
    logout(request)
    return redirect("login")


@login_required
def password_view(request):
    form = PasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            if user.password != request.user.password:
                form.add_error(None, "帳號密碼已變動，請重新登入")
            else:
                user.set_password(form.cleaned_data["new_password1"])
                user.must_change_password = False
                user.temporary_expires_at = None
                user.save()
                ActionToken.objects.filter(user=user, used_at__isnull=True).update(
                    used_at=timezone.now()
                )
                log(user, "account.password_changed", user.pk)
                update_session_auth_hash(request, user)
                messages.success(request, "密碼已更新")
                return redirect("dashboard")
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "title": "設定個人密碼",
            "subtitle": "請先設定自己的密碼；完成前不能使用其他功能。"
            if request.user.must_change_password
            else "",
        },
    )


def forgot(request):
    form = ForgotForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = User.objects.filter(
            username=form.cleaned_data["username"].lower(),
            is_active=True,
            deleted_at__isnull=True,
        ).first()
        if (
            user
            and user.email
            and user.email_verified_at
            and (not user.company_id or user.company.is_active)
        ):
            issue_token(user, "reset")
        messages.success(
            request,
            "若帳號已設定可用且已驗證的 Email，系統將寄送重設通知。無 Email 或無法收信請聯絡資訊公司管理者。",
        )
        return redirect("forgot")
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "title": "忘記密碼",
            "subtitle": "無 Email 的使用者請聯絡資訊公司管理者重設臨時密碼。",
        },
    )


def token_view(request, raw):
    token = (
        ActionToken.objects.select_related("user").filter(digest=digest(raw)).first()
    )
    valid = token and not token.used_at and token.expires_at > timezone.now()
    form = (
        SetPasswordForm(token.user, request.POST or None)
        if valid and token.purpose == "reset"
        else None
    )
    if not valid:
        return render(
            request, "message.html", {"title": "連結無效或已過期"}, status=400
        )
    if request.method == "POST" and (form is None or form.is_valid()):
        try:
            purpose = consume_token(
                raw, form.cleaned_data["new_password1"] if form else None
            )
        except ValidationError as e:
            return render(
                request, "message.html", {"title": "連結無效或已過期"}, status=400
            )
        messages.success(
            request, "Email 已驗證" if purpose == "verify" else "密碼已重設，請重新登入"
        )
        return redirect("login")
    response = render(
        request,
        "generic_form.html",
        {"form": form, "title": "設定新密碼" if form else "確認驗證 Email"},
    )
    response["Referrer-Policy"] = "no-referrer"
    response["Cache-Control"] = "no-store"
    return response


@login_required
@require_POST
def verify_email(request):
    if request.user.email and not request.user.email_verified_at:
        issue_token(request.user, "verify")
        messages.success(request, "驗證信已排入寄送")
    return redirect("dashboard")


def managed_users(actor):
    q = User.objects.filter(deleted_at__isnull=True).select_related("company")
    if actor.role == User.Role.IT_ADMIN:
        return q
    return q.filter(company=actor.company, role=User.Role.REPORTER)


@login_required
def users(request):
    require(request.user, "it_admin", "company_admin")
    return render(
        request,
        "accounts/users.html",
        {"rows": managed_users(request.user).order_by("username"), "title": "帳號管理"},
    )


@login_required
def user_edit(request, pk=None):
    require(request.user, "it_admin", "company_admin")
    if pk is None:
        require(request.user, "it_admin")
    obj = get_object_or_404(managed_users(request.user), pk=pk) if pk else User()
    form = UserForm(request.POST or None, instance=obj, actor=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            list(
                User.objects.select_for_update().filter(role="it_admin").order_by("pk")
            )
            existing = (
                User.objects.select_for_update().get(pk=obj.pk) if obj.pk else None
            )
            email_before = existing.email if existing else ""
            if (
                existing
                and existing.role == "it_admin"
                and form.cleaned_data.get("role") != "it_admin"
                and existing.is_active
                and User.objects.filter(
                    role="it_admin", is_active=True, deleted_at__isnull=True
                ).count()
                <= 1
            ):
                form.add_error(None, "必須保留至少一位可用資訊公司管理者")
                return render(
                    request, "generic_form.html", {"form": form, "title": "修改帳號"}
                )
            user = form.save(commit=False)
            if email_before != user.email:
                user.email_verified_at = None
            user.save()
            log(
                request.user,
                "account.updated" if pk else "account.created",
                user.pk,
                company=user.company,
            )
            if not pk:
                raw = temporary_password(request.user, user)
                response = render(
                    request,
                    "accounts/temporary.html",
                    {"account": user, "temporary": raw},
                )
                response["Cache-Control"] = "no-store"
                return response
        messages.success(request, "資料已儲存")
        return redirect("users")
    return render(
        request,
        "generic_form.html",
        {"form": form, "title": "修改帳號" if pk else "新增帳號"},
    )


@login_required
@require_POST
def user_action(request, pk, action):
    require(request.user, "it_admin")
    with transaction.atomic():
        # Serialize administrator lifecycle changes, preserving the last active admin.
        list(User.objects.select_for_update().filter(role="it_admin").order_by("pk"))
        user = get_object_or_404(
            User.objects.select_for_update().filter(deleted_at__isnull=True), pk=pk
        )
        if action == "temporary":
            if not user.is_active:
                messages.error(request, "請先啟用帳號")
                return redirect("users")
            raw = temporary_password(request.user, user)
            response = render(
                request, "accounts/temporary.html", {"account": user, "temporary": raw}
            )
            response["Cache-Control"] = "no-store"
            return response
        if action not in ["enable", "disable", "delete"]:
            return render(request, "message.html", {"title": "無效操作"}, status=400)
        if (
            action in ["disable", "delete"]
            and user.role == "it_admin"
            and user.is_active
            and User.objects.filter(
                role="it_admin", is_active=True, deleted_at__isnull=True
            ).count()
            <= 1
        ):
            messages.error(request, "必須保留至少一位可用資訊公司管理者")
            return redirect("users")
        if (
            action in ["disable", "delete"]
            and user.assigned_tickets.exclude(
                status__in=["closed", "cancelled"]
            ).exists()
        ):
            messages.error(request, "此帳號仍有未結案件，請先改派")
            return redirect("users")
        user.is_active = action == "enable"
        if action == "delete":
            user.deleted_at = timezone.now()
        if action in ["disable", "delete"]:
            # Change password hash so re-enabling cannot resurrect an old session.
            user.set_unusable_password()
            user.must_change_password = True
        user.save()
        log(request.user, "account." + action, user.pk, company=user.company)
    messages.success(request, "帳號狀態已更新；重新啟用後請重設臨時密碼")
    return redirect("users")

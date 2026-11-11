import re
from django import forms
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import ValidationError
from .models import User
from apps.companies.models import Company


class LoginForm(forms.Form):
    username = forms.CharField(label="登入帳號", max_length=150)
    password = forms.CharField(label="密碼", widget=forms.PasswordInput)


class PasswordForm(SetPasswordForm):
    old_password = forms.CharField(label="目前密碼", widget=forms.PasswordInput)

    def clean_old_password(self):
        p = self.cleaned_data["old_password"]
        if not self.user.check_password(p):
            raise ValidationError("目前密碼不正確")
        return p

    def clean_new_password1(self):
        p = self.cleaned_data["new_password1"]
        if self.user.check_password(p):
            raise ValidationError("新密碼不得與目前密碼相同")
        return p


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "username",
            "display_name",
            "role",
            "company",
            "staff_id",
            "department",
            "office",
            "phone",
            "mobile",
            "email",
        ]
        labels = {
            "username": "登入帳號",
            "email": "Email（選填）",
            "company": "所屬公司",
        }

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.fields["company"].queryset = Company.objects.filter(is_active=True)
        self.fields["display_name"].required = True
        if self.instance.pk:
            self.fields["username"].disabled = True
        if actor.role == User.Role.COMPANY_ADMIN:
            for k in ["username", "role", "company"]:
                self.fields.pop(k)

    def clean_username(self):
        name = self.cleaned_data["username"].lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,149}", name):
            raise ValidationError("帳號需3至150字元，只能使用英數、小數點、底線與減號")
        return name

    def clean(self):
        d = super().clean()
        if self.actor.role == User.Role.COMPANY_ADMIN:
            return d
        role = d.get("role")
        company = d.get("company")
        if role in ["reporter", "company_admin"] and not company:
            self.add_error("company", "公司角色必須選擇公司")
        if role == "it_admin" and company:
            self.add_error("company", "贊耀公司角色不能指定客戶公司")
        if self.instance.pk and company != self.instance.company:
            # Role/company transitions require a separate migration workflow.
            self.add_error(None, "既有帳號不支援變更公司，請另建帳號以保留歷史權限")
        return d


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["display_name", "phone", "mobile", "email"]
        labels = {"display_name": "顯示姓名", "phone": "電話／分機", "mobile": "手機", "email": "Email（選填）"}

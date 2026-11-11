from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class User(AbstractUser):
    class Role(models.TextChoices):
        REPORTER = "reporter", "公司報修者"
        COMPANY_ADMIN = "company_admin", "公司管理者"
        IT_ADMIN = "it_admin", "贊耀公司人員"

    role = models.CharField(
        "角色", max_length=20, choices=Role.choices, default=Role.REPORTER
    )
    company = models.ForeignKey(
        "companies.Company", null=True, blank=True, on_delete=models.PROTECT
    )
    display_name = models.CharField("姓名", max_length=100)
    staff_id = models.CharField("工號", max_length=50, blank=True)
    department = models.CharField("部門", max_length=100, blank=True)
    office = models.CharField("辦公室", max_length=100, blank=True)
    phone = models.CharField("電話／分機", max_length=50, blank=True)
    mobile = models.CharField("手機", max_length=50, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    must_change_password = models.BooleanField(default=True)
    temporary_expires_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(role__in=["reporter", "company_admin"], company__isnull=False)
                    | Q(role="it_admin", company__isnull=True)
                ),
                name="user_role_company_consistent",
            )
        ]

    def __str__(self):
        return self.display_name or self.username


class ActionToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    purpose = models.CharField(max_length=20)
    digest = models.CharField(max_length=64, unique=True)
    email = models.EmailField(blank=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class LoginAttempt(models.Model):
    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField()

from django.db import models


class AuditLog(models.Model):
    actor = models.ForeignKey("accounts.User", null=True, on_delete=models.PROTECT)
    role = models.CharField(max_length=20, blank=True)
    company = models.ForeignKey(
        "companies.Company", null=True, on_delete=models.PROTECT
    )
    action = models.CharField(max_length=50, db_index=True)
    target = models.CharField(max_length=150, blank=True)
    details = models.JSONField(default=dict)
    result = models.CharField(max_length=20, default="success")
    ip = models.GenericIPAddressField(null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

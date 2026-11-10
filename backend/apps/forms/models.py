from django.db import models


class FormVersion(models.Model):
    company = models.ForeignKey(
        "companies.Company", on_delete=models.PROTECT, related_name="form_versions"
    )
    number = models.PositiveIntegerField()
    fields = models.JSONField(default=list)
    published_at = models.DateTimeField(null=True, blank=True)
    accepts_until = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "number"], name="unique_form_company_version"
            )
        ]

    def __str__(self):
        return f"{self.company} V{self.number}"

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).first()
            if (
                old
                and old.published_at
                and (
                    old.fields != self.fields
                    or old.company_id != self.company_id
                    or old.number != self.number
                    or old.published_at != self.published_at
                )
            ):
                from django.core.exceptions import ValidationError

                raise ValidationError("已發布表單不可改寫，請建立新版")
        return super().save(*args, **kwargs)

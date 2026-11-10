from django.db import models


class Company(models.Model):
    name = models.CharField("公司名稱", max_length=100)
    code = models.SlugField("公司代碼", max_length=20, unique=True)
    contact = models.CharField("聯絡資訊", max_length=200, blank=True)
    is_active = models.BooleanField("啟用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Location(models.Model):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="locations"
    )
    name = models.CharField("辦公室／據點", max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"], name="unique_company_location"
            )
        ]

    def __str__(self):
        return self.name


class Recipient(models.Model):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="recipients"
    )
    email = models.EmailField()
    events = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)

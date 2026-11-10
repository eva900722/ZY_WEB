from django.db import models


class Attachment(models.Model):
    ticket = models.ForeignKey(
        "tickets.Ticket", on_delete=models.PROTECT, related_name="attachments"
    )
    entry = models.ForeignKey(
        "tickets.Entry",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    key = models.CharField(max_length=100, unique=True)
    content_type = models.CharField(max_length=50)
    size = models.PositiveIntegerField()
    internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

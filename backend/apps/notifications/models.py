from django.db import models


class Notification(models.Model):
    user = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="notifications"
    )
    ticket = models.ForeignKey(
        "tickets.Ticket", null=True, blank=True, on_delete=models.PROTECT
    )
    message = models.CharField(max_length=300)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Delivery(models.Model):
    is_test = models.BooleanField(default=False)
    recipient = models.EmailField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    status = models.CharField(max_length=20, default="pending")
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SystemSettings(models.Model):
    # Single row shared by the website and notification worker.
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    platform_name = models.CharField(max_length=60, default="贊耀服務平台")
    company_name = models.CharField(max_length=100, default="贊耀電腦")
    contact_phone = models.CharField(max_length=50, blank=True)
    contact_email = models.EmailField(blank=True)
    smtp_override = models.BooleanField(default=False)
    smtp_host = models.CharField(max_length=253, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_security = models.CharField(max_length=10, default="starttls")
    smtp_auth = models.BooleanField(default=True)
    smtp_username = models.CharField(max_length=254, blank=True)
    smtp_password_encrypted = models.TextField(blank=True)
    sender_email = models.EmailField(blank=True)
    sender_name = models.CharField(max_length=100, blank=True)
    revision = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="single_system_settings")]

from email.utils import formataddr, parseaddr

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import get_connection

from .models import SystemSettings

BASIC_FIELDS = ("platform_name", "company_name", "contact_phone", "contact_email")
MAIL_FIELDS = (
    "smtp_host",
    "smtp_port",
    "smtp_security",
    "smtp_auth",
    "smtp_username",
    "sender_email",
    "sender_name",
)


def cipher():
    try:
        return Fernet(settings.SETTINGS_ENCRYPTION_KEY.encode("ascii"))
    except (ValueError, UnicodeError):
        raise ValidationError(
            "主機尚未設定有效的 SETTINGS_ENCRYPTION_KEY，請聯絡部署人員。"
        ) from None


def encrypt_password(value):
    return cipher().encrypt(value.encode()).decode("ascii")


def decrypt_password(value):
    if not value:
        return ""
    try:
        return cipher().decrypt(value.encode("ascii")).decode()
    except (InvalidToken, UnicodeError):
        raise ValidationError(
            "SMTP 密碼無法解密，請確認加密金鑰或重新設定密碼。"
        ) from None


def public_settings():
    obj = SystemSettings.objects.filter(pk=1).first() or SystemSettings()
    return {field: getattr(obj, field) for field in BASIC_FIELDS}


def mail_values(obj):
    if obj.smtp_override:
        return {field: getattr(obj, field) for field in MAIL_FIELDS}
    name, address = parseaddr(settings.DEFAULT_FROM_EMAIL)
    return {
        "smtp_host": settings.EMAIL_HOST,
        "smtp_port": settings.EMAIL_PORT,
        "smtp_security": "ssl"
        if settings.EMAIL_USE_SSL
        else "starttls"
        if settings.EMAIL_USE_TLS
        else "none",
        "smtp_auth": bool(settings.EMAIL_HOST_USER),
        "smtp_username": settings.EMAIL_HOST_USER,
        "sender_email": address,
        "sender_name": name,
    }


def settings_data(obj):
    return (
        {field: getattr(obj, field) for field in BASIC_FIELDS}
        | mail_values(obj)
        | {
            "revision": obj.revision,
            "smtp_override": obj.smtp_override,
            "password_set": bool(obj.smtp_password_encrypted)
            if obj.smtp_override
            else bool(settings.EMAIL_HOST_PASSWORD),
        }
    )


def mail_connection():
    obj = SystemSettings.objects.filter(pk=1).first()
    if not obj or not obj.smtp_override:
        return get_connection(), None
    password = decrypt_password(obj.smtp_password_encrypted) if obj.smtp_auth else ""
    connection = get_connection(
        "django.core.mail.backends.smtp.EmailBackend",
        host=obj.smtp_host,
        port=obj.smtp_port,
        username=obj.smtp_username if obj.smtp_auth else "",
        password=password,
        use_tls=obj.smtp_security == "starttls",
        use_ssl=obj.smtp_security == "ssl",
        timeout=settings.EMAIL_TIMEOUT,
    )
    return connection, formataddr((obj.sender_name, obj.sender_email))

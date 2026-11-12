import os
from pathlib import Path
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BASE_DIR.parent
load_dotenv(PROJECT_DIR / ".env")


def flag(k, d="0"):
    return os.getenv(k, d) == "1"


DEBUG = flag("ZY_DEBUG", "1")
SECRET_KEY = os.environ["SECRET_KEY"]
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000").rstrip("/")
INSTALLED_APPS = [
    "rest_framework",
    "apps.api",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
] + [
    f"apps.{n}.apps.Config"
    for n in [
        "accounts",
        "companies",
        "forms",
        "tickets",
        "attachments",
        "notifications",
        "reports",
        "audit",
    ]
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "common.middleware.AccountGateMiddleware",
    "common.response.PrivateResponseMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "common.context.navigation",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DATABASE", "zy_web"),
        "USER": os.getenv("MYSQL_USER", "zy_web"),
        "PASSWORD": os.getenv("MYSQL_PASSWORD", ""),
        "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "PORT": os.getenv("MYSQL_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            "isolation_level": "read committed",
        },
        "TEST": {
            "NAME": os.getenv("MYSQL_TEST_DATABASE", "test_zy_web"),
            "CHARSET": "utf8mb4",
        },
    }
}
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["common.auth.AccountBackend"]
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "zh-hant"
TIME_ZONE = "Asia/Taipei"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = PROJECT_DIR / "staticfiles"
PRIVATE_MEDIA_ROOT = PROJECT_DIR / "private_media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 28800
SESSION_COOKIE_SECURE = flag("SESSION_COOKIE_SECURE")
CSRF_COOKIE_SECURE = flag("CSRF_COOKIE_SECURE")
SECURE_SSL_REDIRECT = flag("SECURE_SSL_REDIRECT")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = flag("EMAIL_USE_TLS", "1")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "service@example.invalid")
EMAIL_TIMEOUT = 15
DATA_UPLOAD_MAX_MEMORY_SIZE = 55 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
TEMP_PASSWORD_HOURS = 24
TOKEN_MINUTES = 30
if not DEBUG and (
    not SESSION_COOKIE_SECURE or not CSRF_COOKIE_SECURE or not SECURE_SSL_REDIRECT
):
    raise ImproperlyConfigured("正式環境必須啟用 HTTPS 與安全 Cookie")

# Only trust this header behind the isolated trusted reverse proxy.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if not DEBUG else None

if DATABASES["default"]["TEST"]["NAME"] == DATABASES["default"][
    "NAME"
] or not DATABASES["default"]["TEST"]["NAME"].startswith("test_"):
    raise ImproperlyConfigured("測試資料庫必須使用獨立 test_ 名稱，不能指向業務資料庫")

# Vue API uses same-origin Django sessions. No credentials are stored in browser localStorage.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.api.authentication.StrictSessionAuthentication"
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "apps.api.helpers.exception_handler",
}
CSRF_FAILURE_VIEW = "apps.api.helpers.csrf_failure"

# Separate from the database backup and Django signing key.
SETTINGS_ENCRYPTION_KEY = os.getenv("SETTINGS_ENCRYPTION_KEY", "")
EMAIL_USE_SSL = flag("EMAIL_USE_SSL")

from django.urls import path, include, re_path
from apps.api import shell
from apps.tickets import views as t
from apps.companies import views as c
from apps.forms import views as f
from apps.attachments import views as a
from apps.notifications import views as n
from apps.audit import views as audit
from apps.reports import views as r

urlpatterns = [
    path("api/", include("apps.api.urls")),
    path("", shell.index, name="vue_home"),
    path("index.html", shell.index),
    re_path(r"^(?P<path>assets/.*)$", shell.asset),
    re_path(
        r"^(?P<path>(?:sw\.js|workbox-[^/]+\.js|manifest\.webmanifest|pwa-192\.png|pwa-512\.png|favicon\.svg|offline\.html))$",
        shell.asset,
    ),
    re_path(
        r"^(?:login|forgot|password|tickets|companies|users|versions|notifications|audit|settings)(?:/.*)?$",
        shell.index,
    ),
    re_path(r"^accounts/(?:login|password|forgot|token/[^/]+)/$", shell.index),
    path("legacy/", t.dashboard, name="dashboard"),
    path("accounts/", include("apps.accounts.urls")),
    path("tickets/new/", t.new, name="ticket_new"),
    path("tickets/<int:pk>/", t.detail, name="ticket_detail"),
    path("forms/status/<int:company_id>/", t.form_status, name="form_status"),
    path("companies/", c.companies, name="companies"),
    path("companies/new/", c.edit, name="company_new"),
    path("companies/<int:pk>/", c.edit, name="company_edit"),
    path("forms/", f.versions, name="versions"),
    path("forms/<int:pk>/edit/", f.versions, name="form_edit"),
    path("forms/<int:pk>/publish/", f.publish_view, name="form_publish"),
    path("attachments/<int:pk>/", a.download, name="attachment"),
    path("notifications/", n.inbox, name="inbox"),
    path("notifications/<int:pk>/read/", n.mark_read, name="notification_read"),
    path("audit/", audit.query, name="audit"),
    path("reports/<str:kind>/", r.export, name="export"),
    path("reports/<str:kind>/<int:pk>/", r.export, name="ticket_export"),
]

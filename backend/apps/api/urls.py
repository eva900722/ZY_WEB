from django.urls import path
from . import auth, tickets, management as m

urlpatterns = [
    path("auth/session/", auth.session),
    path("auth/login/", auth.sign_in),
    path("auth/logout/", auth.sign_out),
    path("auth/password/", auth.password),
    path("auth/forgot/", auth.forgot),
    path("auth/verify/", auth.verify),
    path("auth/token/<str:raw>/", auth.token),
    path("tickets/", tickets.collection),
    path("tickets/meta/", tickets.metadata),
    path("tickets/<int:pk>/", tickets.detail),
    path("companies/", m.companies),
    path("companies/<int:pk>/", m.companies),
    path("users/", m.users),
    path("users/<int:pk>/", m.users),
    path("users/<int:pk>/action/", m.user_action),
    path("versions/", m.versions),
    path("versions/<int:pk>/", m.versions),
    path("notifications/", m.notifications),
    path("notifications/<int:pk>/read/", m.notifications),
    path("audit/", m.audit),
]

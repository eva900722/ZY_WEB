from django.urls import path
from . import views as v

urlpatterns = [
    path("login/", v.login_view, name="login"),
    path("logout/", v.logout_view, name="logout"),
    path("password/", v.password_view, name="password"),
    path("forgot/", v.forgot, name="forgot"),
    path("token/<str:raw>/", v.token_view, name="token"),
    path("verify/", v.verify_email, name="verify_email"),
    path("users/", v.users, name="users"),
    path("users/new/", v.user_edit, name="user_new"),
    path("users/<int:pk>/", v.user_edit, name="user_edit"),
    path("users/<int:pk>/<str:action>/", v.user_action, name="user_action"),
]

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.http import JsonResponse
from common.auth import AccountBackend


class AccountGateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if not AccountBackend().user_can_authenticate(request.user):
                logout(request)
                return (
                    JsonResponse(
                        {"message": "登入已失效", "code": "unauthenticated"}, status=401
                    )
                    if request.path.startswith("/api/")
                    else redirect("login")
                )
            allowed = [
                "/accounts/password/",
                "/accounts/logout/",
                "/api/auth/session/",
                "/api/auth/password/",
                "/api/auth/logout/",
            ]
            if (
                request.user.must_change_password
                and request.path not in allowed
                and not request.path.startswith(("/static/", "/assets/", "/workbox-"))
                and request.path
                not in [
                    "/index.html",
                    "/sw.js",
                    "/manifest.webmanifest",
                    "/pwa-192.png",
                    "/pwa-512.png",
                    "/favicon.svg",
                    "/offline.html",
                ]
            ):
                return (
                    JsonResponse(
                        {
                            "message": "請先更換臨時密碼",
                            "code": "password_change_required",
                        },
                        status=403,
                    )
                    if request.path.startswith("/api/")
                    else redirect("password")
                )
        return self.get_response(request)

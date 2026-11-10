class PrivateResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated or request.path.startswith(
            ("/accounts/", "/api/")
        ):
            response["Cache-Control"] = "private, no-store"
            response["Referrer-Policy"] = "same-origin"
        if response.status_code in [403, 404] and request.user.is_authenticated:
            from apps.audit.services import log

            log(
                request.user,
                "access.denied",
                __import__("re").sub(
                    r"(/(?:accounts|api/auth)/token/)[^/]+",
                    r"\1[redacted]",
                    request.path,
                ),
                result="denied",
                request=request,
            )
        if "/token/" in request.path:
            response["Referrer-Policy"] = "no-referrer"
        return response

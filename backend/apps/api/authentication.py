from rest_framework.authentication import SessionAuthentication


class StrictSessionAuthentication(SessionAuthentication):
    """Enforce CSRF on unsafe requests even before an anonymous login."""

    def authenticate(self, request):
        if request.method not in ("GET", "HEAD", "OPTIONS", "TRACE"):
            self.enforce_csrf(request)
        return super().authenticate(request)

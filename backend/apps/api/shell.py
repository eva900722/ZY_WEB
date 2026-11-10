from django.conf import settings
from django.http import HttpResponse, Http404, FileResponse
from django.views.decorators.http import require_safe


@require_safe
def index(request):
    p = settings.PROJECT_DIR / "frontend/dist/index.html"
    if not p.is_file():
        return HttpResponse(
            "Vue前端尚未建置，請執行前端build。",
            status=503,
            content_type="text/plain; charset=utf-8",
        )
    response = HttpResponse(p.read_text(encoding="utf-8"))
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "same-origin"
    return response


@require_safe
def asset(request, path):
    # Development-only serving; production Nginx serves only the public build directory.
    if not settings.DEBUG:
        raise Http404
    root = (settings.PROJECT_DIR / "frontend/dist").resolve()
    p = (root / path).resolve()
    if not p.is_relative_to(root) or not p.is_file():
        raise Http404
    import mimetypes

    response = FileResponse(
        p.open("rb"),
        content_type=mimetypes.guess_type(str(p))[0] or "application/octet-stream",
    )
    response["Cache-Control"] = (
        "no-cache"
        if path in ["sw.js", "manifest.webmanifest"]
        else "public, max-age=3600"
    )
    if path == "sw.js":
        response["Service-Worker-Allowed"] = "/"
    return response

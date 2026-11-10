from pathlib import Path
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from common.permissions import tickets_for, internal_allowed
from apps.audit.services import log
from .models import Attachment


@login_required
def download(request, pk):
    q = Attachment.objects.filter(ticket__in=tickets_for(request.user))
    if not internal_allowed(request.user):
        q = q.filter(internal=False)
    a = get_object_or_404(q, pk=pk)
    path = Path(settings.PRIVATE_MEDIA_ROOT) / a.key
    if not path.is_file():
        raise Http404
    log(
        request.user,
        "attachment.download",
        a.pk,
        company=a.ticket.company,
        request=request,
    )
    response = FileResponse(
        path.open("rb"),
        as_attachment=True,
        filename=a.name,
        content_type=a.content_type,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response

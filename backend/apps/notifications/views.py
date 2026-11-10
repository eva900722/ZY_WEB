from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Notification
from django.db.models import Q
from common.permissions import tickets_for


@login_required
def inbox(request):
    from django.core.paginator import Paginator

    return render(
        request,
        "notifications/list.html",
        {
            "rows": Paginator(
                request.user.notifications.filter(
                    Q(ticket__isnull=True) | Q(ticket__in=tickets_for(request.user))
                )
                .select_related("ticket")
                .order_by("-pk"),
                30,
            ).get_page(request.GET.get("page")),
            "title": "站內通知",
        },
    )


@login_required
@require_POST
def mark_read(request, pk):
    n = get_object_or_404(Notification, user=request.user, pk=pk)
    n.read_at = timezone.now()
    n.save(update_fields=["read_at"])
    return redirect("inbox")

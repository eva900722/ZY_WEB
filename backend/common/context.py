def navigation(request):
    user = request.user
    if not user.is_authenticated or user.must_change_password:
        return {"unread_count": 0}
    from django.db.models import Q
    from common.permissions import tickets_for

    return {
        "unread_count": user.notifications.filter(
            Q(ticket__isnull=True) | Q(ticket__in=tickets_for(user)),
            read_at__isnull=True,
        ).count()
    }

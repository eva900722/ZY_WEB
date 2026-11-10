from .models import AuditLog


def log(
    actor, action, target="", company=None, details=None, result="success", request=None
):
    return AuditLog.objects.create(
        actor=actor if actor and actor.is_authenticated else None,
        role=getattr(actor, "role", ""),
        company=company,
        action=action,
        target=str(target),
        details=details or {},
        result=result,
        ip=request.META.get("REMOTE_ADDR") if request else None,
    )

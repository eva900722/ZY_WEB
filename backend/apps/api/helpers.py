from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import JsonResponse
from django.views.csrf import csrf_failure as django_csrf_failure
from rest_framework.views import exception_handler as default_handler
from rest_framework.exceptions import ValidationError, NotAuthenticated
from rest_framework.response import Response
from django.core.paginator import Paginator


def valid(form):
    if not form.is_valid():
        raise ValidationError(
            {
                "message": "請檢查填寫內容",
                "fields": {
                    k: [str(e) for e in errors] for k, errors in form.errors.items()
                },
            }
        )
    return form.cleaned_data


def exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        data = {"message": "；".join(exc.messages)}
        if hasattr(exc, "message_dict"):
            data["fields"] = exc.message_dict
        return Response(data, status=400)
    response = default_handler(exc, context)
    if response is not None:
        if isinstance(exc, NotAuthenticated):
            response.status_code = 401
        if isinstance(response.data, dict):
            if "message" not in response.data:
                response.data["message"] = str(
                    response.data.get("detail", "操作失敗，請檢查資料")
                )
        else:
            response.data = {"message": "操作失敗", "fields": response.data}
    return response


def csrf_failure(request, reason=""):
    if request.path.startswith("/api/"):
        return JsonResponse(
            {"message": "安全憑證已失效，請重新整理後重試", "code": "csrf_failed"},
            status=403,
        )
    return django_csrf_failure(request, reason)


def page(qs, request, serialize, size=20):
    result = Paginator(qs, size).get_page(request.query_params.get("page", 1))
    return {
        "items": [serialize(x) for x in result],
        "total": result.paginator.count,
        "pages": result.paginator.num_pages,
        "page": result.number,
    }


def user_data(user):
    if not user or not user.is_authenticated:
        return None
    return {
        k: getattr(user, k)
        for k in [
            "id",
            "username",
            "display_name",
            "role",
            "company_id",
            "staff_id",
            "department",
            "office",
            "phone",
            "mobile",
            "email",
            "is_active",
            "must_change_password",
        ]
    } | {
        "company_name": str(user.company) if user.company_id else "贊耀公司",
        "role_label": user.get_role_display(),
        "email_verified": bool(user.email_verified_at),
    }

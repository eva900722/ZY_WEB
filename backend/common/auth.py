from django.contrib.auth.backends import ModelBackend
from django.utils import timezone


class AccountBackend(ModelBackend):
    def user_can_authenticate(self, user):
        return (
            super().user_can_authenticate(user)
            and user.deleted_at is None
            and (not user.company_id or user.company.is_active)
            and (
                not user.must_change_password
                or not user.temporary_expires_at
                or user.temporary_expires_at > timezone.now()
            )
        )

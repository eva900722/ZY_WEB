from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.accounts.models import User
from apps.accounts.services import temporary_password


class Command(BaseCommand):
    help = "建立第一位贊耀公司人員，輸出一次性臨時密碼。只允許尚無管理者時使用。"

    def add_arguments(self, p):
        p.add_argument("--username", default="zyadmin")

    @transaction.atomic
    def handle(self, *args, **options):
        if User.objects.filter(role="it_admin").exists():
            raise CommandError("已有管理者，請從後台建立其他帳號")
        name = options["username"].lower()
        import re

        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,149}", name):
            raise CommandError("帳號格式不正確")
        user = User.objects.create(
            username=name, display_name="贊耀公司人員", role="it_admin", is_active=True
        )
        raw = temporary_password(user, user)
        self.stdout.write(
            "帳號："
            + user.username
            + "\n臨時密碼（僅此次顯示）："
            + raw
            + "\n請立即登入更換。"
        )

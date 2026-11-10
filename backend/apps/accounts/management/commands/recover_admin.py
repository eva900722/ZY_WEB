from django.core.management.base import BaseCommand, CommandError
from apps.accounts.models import User
from apps.accounts.services import temporary_password


class Command(BaseCommand):
    help = "僅限主機維運人員執行的管理者復原；會撤銷原密碼並輸出新臨時密碼"

    def add_arguments(self, p):
        p.add_argument("--username", required=True)
        p.add_argument("--confirm-recovery", action="store_true")

    def handle(self, *args, **options):
        if not options["confirm_recovery"]:
            raise CommandError("需加 --confirm-recovery 確認復原")
        user = User.objects.filter(
            username=options["username"].lower(),
            role="it_admin",
            is_active=True,
            deleted_at__isnull=True,
        ).first()
        if not user:
            raise CommandError("找不到可用資訊公司管理者")
        raw = temporary_password(user, user)
        self.stdout.write("臨時密碼（僅此次顯示）：" + raw + "\n登入後必須更換。")

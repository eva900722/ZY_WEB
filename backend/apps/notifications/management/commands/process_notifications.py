import time
from django.core.management.base import BaseCommand
from apps.notifications.services import deliver_batch


class Command(BaseCommand):
    help = "處理 Email outbox；--loop 持續處理，預設處理一批後結束"

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")

    def handle(self, *args, **options):
        while True:
            count = deliver_batch()
            self.stdout.write(f"Processed {count} delivery records")
            if not options["loop"]:
                break
            time.sleep(5)

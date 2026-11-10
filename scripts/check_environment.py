import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from django.db import connection

connection.ensure_connection()
with connection.cursor() as c:
    c.execute("SELECT VERSION(), DATABASE(), @@character_set_database")
    version, name, charset = c.fetchone()
    print("Database:", version, name, charset)
    c.execute(
        "SELECT ENGINE, COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() GROUP BY ENGINE"
    )
    print("Table engines:", c.fetchall())
assert connection.vendor == "mysql" and not connection.mysql_is_mariadb, (
    "驗收要求 Oracle MySQL"
)
print("Django:", django.get_version(), "Python:", sys.version.split()[0])

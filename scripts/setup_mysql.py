"""Create a loopback-only isolated MySQL instance. Never touches port 3306."""

import os, secrets, subprocess, time, socket
from pathlib import Path
import MySQLdb

ROOT = Path(__file__).resolve().parent.parent
BIN = Path(os.getenv("MYSQL_BIN", str(ROOT / ".tools/mysql-8.4.13-winx64/bin")))
DATA = ROOT / "mysql_data"
PORT = 3307
if DATA.exists():
    raise SystemExit(
        "Data directory exists; use scripts/start_mysql.ps1. No reinitialization performed."
    )
with socket.socket() as sock:
    if sock.connect_ex(("127.0.0.1", PORT)) == 0:
        raise SystemExit("Port 3307 is occupied; aborting.")
DATA.mkdir()
args = [
    str(BIN / "mysqld.exe"),
    "--no-defaults",
    f"--basedir={BIN.parent}",
    f"--datadir={DATA}",
]
subprocess.run(
    args + ["--initialize-insecure"],
    cwd=DATA,
    check=True,
    creationflags=subprocess.CREATE_NO_WINDOW,
)
proc = subprocess.Popen(
    args
    + [
        f"--port={PORT}",
        "--bind-address=127.0.0.1",
        "--mysqlx=OFF",
        f"--log-error={DATA / 'server.err'}",
    ],
    cwd=DATA,
    creationflags=subprocess.CREATE_NO_WINDOW,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
connection = None
for _ in range(60):
    try:
        connection = MySQLdb.connect(host="127.0.0.1", port=PORT, user="root")
        break
    except MySQLdb.Error:
        time.sleep(0.5)
if connection is None:
    raise SystemExit("MySQL did not start; inspect .mysql-data/server.err")
admin = secrets.token_urlsafe(32)
app = secrets.token_urlsafe(32)
c = connection.cursor()
c.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (admin,))
c.execute("CREATE DATABASE zy_web CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
c.execute("CREATE USER 'zy_web'@'localhost' IDENTIFIED BY %s", (app,))
c.execute("GRANT ALL PRIVILEGES ON zy_web.* TO 'zy_web'@'localhost'")
c.execute("GRANT ALL PRIVILEGES ON test_zy_web.* TO 'zy_web'@'localhost'")
connection.close()
(ROOT / ".mysql-admin.env").write_text(
    "MYSQL_ROOT_PASSWORD=" + admin + "\n", encoding="utf-8"
)
p = ROOT / ".env"
s = p.read_text(encoding="utf-8")
values = {"MYSQL_PORT": "3307", "MYSQL_USER": "zy_web", "MYSQL_PASSWORD": app}
p.write_text(
    "\n".join(
        k + "=" + values.get(k, v) if "=" in line else line
        for line in s.splitlines()
        for k, v in [line.split("=", 1) if "=" in line else ("", "")]
    )
    + "\n",
    encoding="utf-8",
)
(ROOT / ".mysql.pid").write_text(str(proc.pid))
print(
    "Isolated MySQL 8 ready on 127.0.0.1:3307; app credentials saved locally; port 3306 untouched."
)

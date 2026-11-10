$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$binary = Join-Path $root '.tools/mysql-8.4.13-winx64/bin/mysqld.exe'
$data = Join-Path $root 'mysql_data'
if (-not (Test-Path -LiteralPath (Join-Path $data 'auto.cnf'))) { throw '尚未初始化，請先執行 setup_mysql.py' }
if (Test-NetConnection -ComputerName 127.0.0.1 -Port 3307 -InformationLevel Quiet -WarningAction SilentlyContinue) { Write-Output '3307 已有服務，未重複啟動'; exit 0 }
$arguments = @('--no-defaults', ('--basedir="' + (Split-Path (Split-Path $binary -Parent) -Parent) + '"'), ('--datadir="' + $data + '"'), '--port=3307', '--bind-address=127.0.0.1', '--mysqlx=OFF', ('--log-error="' + (Join-Path $data 'server.err') + '"'))
$process = Start-Process -FilePath $binary -ArgumentList $arguments -WorkingDirectory $data -WindowStyle Hidden -PassThru
Set-Content -LiteralPath (Join-Path $root '.mysql.pid') -Value $process.Id
Write-Output '專用 MySQL 啟動中，僅監聽 127.0.0.1:3307'

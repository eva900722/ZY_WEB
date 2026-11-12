# 其他 Windows 啟動步驟

適用於 ZY_WEB 贊耀服務平台，更新日期為 2026-11-12。

以下採用「新電腦、全新空資料庫、先在該電腦本機啟動」方式。範例專案位置為 `C:\ZY_WEB`，命令使用 **CMD（命令提示字元）**。如果你放在其他磁碟或資料夾，請將指令中的路徑換成實際位置。

| 目前情況 | 從哪裡開始 |
| 第一次拿到程式，新電腦尚未安裝 | 依序完成第 1～9 步 |
| 已安裝成功，今天只是要使用 | 直接看第 10 步 |
| 要連同目前的案件、帳號及附件一起搬家 | 先看第 12 步，使用既有資料移轉流程 |

本文件使用專案現有命令。先前討論的 `首次安裝.cmd`、`啟動系統.cmd` 目前尚未建立。

## 1. 在新電腦安裝三項軟體

| 軟體 | 專案使用版本 | 安裝時要確認 |
|---|---|---|
| Python | 3.11，64 位元 | 勾選加入 PATH，包含 Python Launcher |
| Node.js | 24 LTS，64 位元 | 安裝 npm 並加入 PATH |
| MySQL Server | Oracle MySQL 8.4 | 設定 root 管理密碼、記下連接埠、設為 Windows 服務並自動啟動 |

MySQL Workbench 可一併安裝，後續用它建立資料庫。Workbench 是操作工具，還需要 MySQL Server 服務運作。

官方下載與安裝說明如下。

- [Python Windows 下載](https://www.python.org/downloads/windows/)
- [Node.js 下載，選擇 24 LTS](https://nodejs.org/en/download)
- [MySQL 8.4 Windows 安裝說明](https://dev.mysql.com/doc/refman/8.4/en/windows-installation.html)

安裝完成後，重新開一個 CMD，逐行執行。

```cmd
py -3.11 --version
node --version
npm --version
```

預期可看到 Python 3.11、Node v24 及 npm 版本。遇到「不是內部或外部命令」時，先確認安裝完成並重新開啟 CMD。

## 2. 放入專案資料夾

將程式碼放到以下位置，也可從 GitHub 下載 ZIP 後解壓縮並重新命名。

```text
C:\ZY_WEB\
├─ backend\
├─ frontend\
├─ scripts\
├─ docs\
├─ .env.example
└─ README.md
```

確認 `backend\manage.py` 與 `frontend\package-lock.json` 都在。

全新安裝的 Python 環境及前端套件會在這台電腦重新建立。交付程式碼時排除來源電腦的 `.venv`、`frontend/node_modules`、`.env`、`.mysql-admin.env`、`mysql_data`、備份與 PID 檔。需要搬移原有業務附件時，依第 12 步處理。

## 3. 安裝程式需要的 Python 套件

開啟 CMD，逐行執行，每行完成且沒有錯誤後再進行下一行。

```cmd
cd /d C:\ZY_WEB
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

使用完整的 `.venv\Scripts\python.exe` 路徑即可，不必另外啟用虛擬環境。新電腦首次安裝套件需要網路。

## 4. 建立 MySQL 資料庫與應用帳號

先確認 MySQL Windows 服務正在執行。可在 CMD 輸入以下命令開啟服務清單，找到安裝時建立的 MySQL 服務，確認狀態是執行中。

```cmd
services.msc
```

開啟 MySQL Workbench，以安裝 MySQL 時設定的 root 帳號密碼連線。以下以本機 `127.0.0.1`、連接埠 `3306` 為例。

在 Workbench 的 SQL 編輯區執行以下指令，確認版本與連接埠。

```sql
SELECT VERSION(), @@port;
```

接著將下面的 `CHANGE_ME_APP_PASSWORD` 換成自己設定的應用帳號密碼，再於同一個 SQL 編輯區執行。

```sql
CREATE DATABASE zy_web
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

CREATE USER 'zy_web'@'localhost'
IDENTIFIED BY 'CHANGE_ME_APP_PASSWORD';

GRANT ALL PRIVILEGES ON zy_web.*
TO 'zy_web'@'localhost';
```

SQL 指令在 **Workbench** 執行，其他標示 `cmd` 的指令在 **CMD** 執行。記下應用帳號 `zy_web` 的密碼，第 5 步會使用。

若出現同名資料庫或帳號已存在，先確認是否已有資料。一般重新啟動直接使用原資料庫，建立資料庫的步驟只需做一次。

本路線使用 Windows 的 MySQL 服務。`scripts/start_mysql.ps1` 與 `scripts/setup_mysql.py` 是原專案便攜 MySQL 的另一套啟動／初始化流程，適用方式見[完整部署手冊](安裝部署與帳號操作手冊.md)。

## 5. 建立這台電腦的環境設定

回到 CMD。

```cmd
cd /d C:\ZY_WEB
if not exist .env copy .env.example .env
```

接著分別執行以下兩行，產生兩組不同用途的金鑰。每行各輸出一組字串，先保留在畫面上。

```cmd
.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

開啟 `.env`。

```cmd
notepad .env
```

依下表填寫或更新設定。

| 欄位 | 要填的內容 |
|---|---|
| `SECRET_KEY` | 剛才第一行產生的字串 |
| `SETTINGS_ENCRYPTION_KEY` | 剛才第二行產生的字串，用來加密 SMTP 密碼 |
| `MYSQL_HOST` | `127.0.0.1` |
| `MYSQL_PORT` | 安裝時的實際 MySQL 連接埠，本範例為 `3306` |
| `MYSQL_DATABASE` | `zy_web` |
| `MYSQL_USER` | `zy_web` |
| `MYSQL_PASSWORD` | 第 4 步設定的應用帳號密碼 |

本機啟動相關設定如下，請確認 `.env` 內對應欄位的值。

```dotenv
ZY_DEBUG=1
ALLOWED_HOSTS=localhost,127.0.0.1
SITE_URL=http://127.0.0.1:8000
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=zy_web
MYSQL_USER=zy_web
MYSQL_TEST_DATABASE=test_zy_web
SECURE_SSL_REDIRECT=0
SESSION_COOKIE_SECURE=0
CSRF_COOKIE_SECURE=0
```

每個欄位只保留一行，原有 `MYSQL_PORT=3307` 要改為這台電腦的實際值。儲存後關閉記事本。金鑰產生步驟只用於全新安裝，日常啟動沿用原金鑰。

`MYSQL_PASSWORD` 是應用程式連 MySQL 的密碼；網頁登入密碼與 SMTP 寄信密碼會另外設定。

## 6. 建置網頁前端

在專案根目錄的 CMD 執行。

```cmd
powershell -ExecutionPolicy Bypass -File scripts\build_frontend.ps1 -Install
```

這行會呼叫現有 PowerShell 腳本，自動安裝前端套件並建置 Vue／PWA，結果位於 `frontend/dist`。完成後會顯示建置完成訊息。日常啟動沿用建置結果，修改前端程式後再重新建置。

## 7. 建立資料表及第一位管理者

仍在同一個 CMD 執行。

```cmd
.venv\Scripts\python.exe backend\manage.py check
.venv\Scripts\python.exe backend\manage.py migrate --noinput
.venv\Scripts\python.exe backend\manage.py bootstrap_admin --username zyadmin
```

| 命令 | 完成的工作 |
|---|---|
| `check` | 檢查 Django 設定，成功顯示沒有問題 |
| `migrate` | 依 `.env` 連上資料庫，自動建立／更新需要的資料表 |
| `bootstrap_admin` | 建立第一位贊耀公司人員，顯示當次臨時密碼 |

請記下 `zyadmin` 的臨時密碼，24 小時內登入並更換。第一位管理者由這個命令建立，使用者權限依帳號角色決定。資料庫已有贊耀公司人員時，程式會提示已有管理者，後續使用既有帳號登入。

## 8. 開啟網站與寄信服務

第一個 CMD 視窗啟動網站。

```cmd
cd /d C:\ZY_WEB
.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000
```

出現網站啟動訊息後，保持這個視窗開啟。

再開第二個 CMD 視窗，啟動寄信 worker。

```cmd
cd /d C:\ZY_WEB
.venv\Scripts\python.exe backend\manage.py process_notifications --loop
```

第二個視窗也保持開啟。worker 會持續檢查待寄郵件，顯示處理數量為 0 代表當次沒有待寄郵件。

在這台電腦開啟瀏覽器，輸入以下網址。

```text
http://127.0.0.1:8000/
```

本機服務會讀取建置好的 Vue 網頁，使用時維持網站與 worker 這兩個服務即可。

## 9. 第一次登入後做哪些設定

1. 用 `zyadmin` 與第 7 步產生的臨時密碼登入。
2. 依畫面要求設定自己的密碼，至少 10 個字元；兩次輸入一致，且須通過系統密碼檢查。
3. 進入「報修系統入口 → 公司管理」，建立客戶公司。
4. 進入「帳號管理」，建立該公司的公司管理者，將臨時密碼交給本人。
5. 公司管理者登入後，可新增及管理本公司的公司報修者。
6. 贊耀公司人員進入「系統設定 → 寄信設定」，按「套用 HiNet」，填入寄件信箱、SMTP 帳號及有效密碼並儲存。
7. 輸入測試收件信箱，寄送測試信，確認 worker 處理完成並至收件匣檢查。

Email 保持選填。寄件帳號是平台用來發信的帳號，案件通知的收件人依使用者資料與既有通知規則決定。

## 10. 之後每天怎麼啟動

安裝完成後，先確認 MySQL Windows 服務已啟動。若設成自動啟動，開機後可在服務清單確認狀態。

開啟 CMD 視窗 A，執行。

```cmd
cd /d C:\ZY_WEB
.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000
```

開啟 CMD 視窗 B，執行。

```cmd
cd /d C:\ZY_WEB
.venv\Scripts\python.exe backend\manage.py process_notifications --loop
```

再用瀏覽器開啟 `http://127.0.0.1:8000/`，即可使用。一般日常啟動只需要上述步驟，沿用已安裝的套件、既有資料表、金鑰與帳號。

停止時，在兩個 CMD 視窗分別按 `Ctrl＋C`。修改 `.env` 後，網站與 worker 都需要停止再啟動。若服務已經在執行，先使用現有服務，避免重複開啟。

## 11. 常見問題對照

| 畫面或錯誤 | 檢查方式 |
|---|---|
| 找不到 `py`、`node`、`npm` | 檢查安裝與 PATH，完成後重新開啟 CMD |
| 找不到 `backend\manage.py` | 確認先執行 `cd /d C:\ZY_WEB`，且資料夾內有 backend |
| 套件安裝失敗 | 看第一個錯誤，確認網路、Python 3.11／64 位元與套件需求；如提示缺少 Microsoft C++ 執行環境，依提示安裝後重試 |
| MySQL 連線失敗、10061 | 檢查 MySQL 服務、主機與連接埠 |
| MySQL Access denied、1045 | 檢查 `.env` 的應用帳號、密碼及該帳號允許的連線來源 |
| Unknown database、1049 | 檢查是否完成第 4 步，或是否連錯 MySQL 服務 |
| 資料表不存在 | 確認第 7 步的 `migrate --noinput` 成功 |
| Vue 前端尚未建置 | 執行第 6 步，確認 `frontend/dist/index.html` 存在 |
| 8000 已被使用 | 確認是否已開啟網站 CMD 視窗，使用現有服務或先由該視窗 Ctrl＋C 停止 |
| 顯示已有管理者 | 使用既有帳號；忘記密碼依目前帳號復原流程處理 |
| 臨時密碼過期 | 由有權限的管理者重設；僅有第一位管理者且無法登入時，依完整手冊的主機復原程序處理 |
| 測試信一直排隊 | 確認第 8 步的寄信 worker 正在執行 |
| 測試信寄送失敗 | 核對系統設定的 SMTP、密碼、加密方式及測試結果 |
| SMTP 密碼無法解密 | 確認 `SETTINGS_ENCRYPTION_KEY` 與保存密碼時相同，修改金鑰後需重新輸入 SMTP 密碼 |

## 12. 搬移舊資料或正式提供客戶使用

搬移既有資料時，需由原主機匯出 MySQL SQL 備份、備份 `private_media` 附件，並安全保存原 `SETTINGS_ENCRYPTION_KEY`。在新主機還原資料及附件，設定正確的連線與原加密金鑰，執行 `migrate --noinput` 更新結構，再以既有帳號登入。相關步驟見[完整部署與資料移轉手冊](安裝部署與帳號操作手冊.md)。

上述 `runserver 127.0.0.1:8000` 用於新電腦本機驗證，連線範圍是該電腦。正式提供其他公司使用時，需安排 HTTPS、正式應用服務、前端靜態檔服務、程序自動重啟及備份。其他電腦上的 PWA 與直接擷取螢幕也需要符合安全來源條件。Django 官方的正式部署說明見[此處](https://docs.djangoproject.com/en/5.2/howto/deployment/)。

本文件依目前程式、腳本及設定檢查整理；另一台 Windows 的全新安裝、MySQL 安裝與實際寄信，仍須在目標電腦依步驟驗收。

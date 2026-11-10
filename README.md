# ZY_WEB｜資訊管家

Vue 3＋PWA／Django API＋MySQL企業報修網站：四種角色、公司資料隔離、指定工程師處理、版本化報修表單、附件、操作紀錄、Email／站內通知及PDF／Excel匯出。

## 文件

- [專案規格](PROJECT_SPEC.md)
- [目錄整理任務與驗收](TASKS.md)

- [技術架構與檔案用途](docs/技術架構與檔案用途說明.md)
- [安裝部署與帳號操作手冊](docs/安裝部署與帳號操作手冊.md)

## Vue前端建置

首次使用或修改前端後，安裝Node.js 24 LTS並在根目錄執行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_frontend.ps1 -Install
```

本機已提供便攜Node；新主機需自行安裝Node.js。建置結果在frontend/dist，之後使用backend/manage.py啟動同一個8000網站，不需另外維持Vite。

## 現有Windows環境啟動

在ZY_WEB根目錄開啟PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_mysql.ps1
.\.venv\Scripts\python.exe scripts/check_environment.py
.\.venv\Scripts\python.exe backend/manage.py check
.\.venv\Scripts\python.exe backend/manage.py runserver 127.0.0.1:8000
```

另開終端機啟動寄信：

```powershell
.\.venv\Scripts\python.exe backend/manage.py process_notifications --loop
```

瀏覽 http://127.0.0.1:8000/ 。若已有背景程序佔用連接埠，先由維運者確認，不重複啟動。修改.env後重新啟動網站與worker。

## 全新安裝

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Copy-Item .env.example .env
```

依操作手冊設定自己的SECRET_KEY、MySQL與SMTP後：

```powershell
.\.venv\Scripts\python.exe backend/manage.py migrate --noinput
.\.venv\Scripts\python.exe backend/manage.py bootstrap_admin --username zyadmin
```

bootstrap只用於尚無管理者的全新資料庫，會顯示當次臨時密碼，首次登入必須更換。已有資料時不要重新初始化MySQL；不要使用Django createsuperuser替代業務管理者命令。

## 目錄

```text
ZY_WEB/
├─ backend/          Django：apps、common、config、templates、static
│  ├─ deployment/    Docker、Compose、Nginx
│  ├─ manage.py      後端命令入口
│  └─ requirements.txt
├─ docs/             技術、部署及驗收文件
├─ frontend/         Vue／TypeScript／PWA
├─ scripts/          建置、啟動與環境檢查
├─ .env.example
├─ .gitattributes
├─ .gitignore
├─ .dockerignore     根目錄Docker建置必需的排除規則
├─ AGENTS.md
├─ PROJECT_SPEC.md
├─ README.md
└─ TASKS.md
```

本機另保留 `.env`、`.mysql-admin.env`、`.venv/`、`.tools/`、`mysql_data/`、`private_media/` 及 PID 檔；它們是使用中的設定、工具或資料，不屬於可刪除的多餘程式。不要複製到新的空庫部署，也不要直接刪除。使用者原有 `.vscode/` 設定不變。

## 維運注意

- 現有本機資料庫在127.0.0.1:3307，原3306服務另存；新主機依實際設定。
- .env中的Gmail是系統寄件帳號，各使用者資料中的Email才是收件人；無Email不寄信。
- 資料庫、.env、.mysql-admin.env及附件保留，不直接分享；PID檔只屬本機。
- 只新增本次改版必要測試：backend/apps/api/tests.py、backend/apps/api/browser_tests.py及frontend/tests；不恢復無關的舊測試產物。
- 仍保留全部migrations，部署時透過migrate建表。
- runserver只供本機使用；正式Docker／HTTPS部署依手冊，尚須在目標主機驗證。

## 本次改版與PWA

任務／驗收狀態見[Vue與PWA改版任務](docs/Vue_PWA_改版任務.md)。前端使用同源/api/與Session＋CSRF，保留既有權限與業務服務。

PWA可在支援瀏覽器安裝，正式環境需HTTPS；localhost可本機驗證。僅快取公開應用外殼與靜態資源，不快取API、案件、附件、報表或驗證連結；離線不能送單。有新版時提示使用者，尚有未送出表單時不重新載入。

開發Vue可在frontend目錄執行npm run dev（5173代理8000的API），但PWA驗證請使用npm run build後的8000網站。根目錄.env僅供後端；不要將密碼放進任何VITE_變數。

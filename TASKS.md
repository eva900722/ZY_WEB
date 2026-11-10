# 目錄整理任務與驗收

| 任務 | 範圍 | 狀態 |
|---|---|---|
| S01 | 盤點與雜湊、資料庫筆數及附件記錄，搬移後端 | 完成 |
| S02 | 更新設定、啟動腳本、Docker與文件相依路徑 | 完成 |
| S03 | 回歸驗證、資料核對、清理產物與本機重新啟動 | 完成 |

## 最小修改範圍

後端原始碼、manage.py、requirements.txt及deployment集中於backend。frontend、docs、scripts維持同層。新增PROJECT_SPEC.md作規格入口及.gitattributes作文字格式規則，根目錄保留Docker建置所需.dockerignore。

原有134個原始碼／範本／靜態資源／前端檔案均存在，依搬移對照核對SHA-256；僅config/settings.py、apps/api/shell.py、apps/api/browser_tests.py三個Python檔案因檔案位置變動調整路徑。其他業務及前端內容不變。啟動腳本、部署設定、忽略規則與文件同步更新。

## 驗收

- Django check：通過。
- makemigrations --check --dry-run：無模型變更。
- 真實MySQL連線：8.4.13，zy_web，23張InnoDB表。
- API＋Edge瀏覽器：35／35通過，包含權限、報修、附件、派工、PWA與更新流程。
- 前端TypeScript／Vite build：通過；Node PWA政策測試：8／8通過。
- 23張既有資料表筆數與整理前一致；現有1個附件檔案SHA-256一致。
- Compose YAML及context、Dockerfile、env_file路徑核對通過；本機無Docker，未進行容器實際啟動驗證。
- 文件相對連結核對通過；本機網站、Session API、Manifest、Service Worker及前端靜態檔均回應200。
- 網站與寄信worker已使用新backend入口恢復運行；MySQL程序未中斷，未進行真實寄信測試。

首次驗證時前端build與瀏覽器測試並行，dist重建造成一項暫時503。改為build完成後循序重跑，35項全部通過。更新過的PowerShell腳本維持UTF-8 BOM，已實際驗證建置可執行。

## 清理及保留

清除.ruff_cache、後端／腳本__pycache__、.tools下舊Vue截圖與測試日誌、已解壓的Node壓縮檔及本次暫存比對檔。Python執行後可能再次建立__pycache__，這是正常的可重建快取。

保留必要測試、全部migrations、frontend/dist、node_modules、.venv、.tools的MySQL／Node執行檔；它們仍供本機運行或驗收使用。保留.env、.mysql-admin.env、mysql_data、private_media及使用者.vscode設定。不刪除或搬動使用中的MySQL資料，不重設帳號。

## 啟動

在ZY_WEB根目錄執行（目前背景網站已啟動，請勿重複佔用8000埠）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_dev.ps1
```

寄信程序另開終端機（目前背景worker已啟動，請勿重複啟動）：

```powershell
.\.venv\Scripts\python.exe backend/manage.py process_notifications --loop
```

完整步驟見[部署手冊](docs/安裝部署與帳號操作手冊.md)。

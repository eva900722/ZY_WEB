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


## 工程師待派案件與自行領單（2026-11-11）

| 任務 | 工作 | 狀態 |
|---|---|---|
| C01 | 共用可見範圍納入全部公司待派案件，未領單不得處理 | 完成 |
| C02 | 原子領單、Vue領單按鈕、新報修通知啟用中的工程師 | 完成 |
| C03 | API／MySQL競爭／瀏覽器回歸及建置驗收 | 完成 |

維持四種角色；管理者指派／改派與帳號建立流程不變。無模型或migration變更，不需公司別授權。可見範圍亦套用原有附件、匯出與通知權限，待派案件被其他人接手後原查看者失權。舊案件可立即依新規則查看，不重發歷史通知。


本次驗收：Django check通過、makemigrations --check --dry-run無變更；TypeScript／Vite／PWA build通過。隔離MySQL測試庫test_zy_web執行41項測試（30 API、2真實資料庫競爭、9 Edge瀏覽器），全部通過。涵蓋未領單不可處理、只能領給自己、不可改派、無Email／停用帳號、新公司自動適用、領單後其他工程師失權、管理者改派及PWA原流程。未建立正式測試案件，未實際寄送測試Email。網站已用新版本重新啟動，首頁與匿名Session API正常；MySQL與worker未重啟。

重跑本次回歸（先完成前端建置）：

```powershell
.\.venv\Scripts\python.exe backend/manage.py test apps.api.tests apps.api.test_claim_concurrency apps.api.browser_tests --noinput --keepdb
```


## PDF／Excel橫向表格（2026-11-11）

- E01：僅調整backend/apps/reports/views.py的匯出呈現與檔名；權限、篩選、1000件上限及資料庫模型不變。完成。
- E02：新增backend/apps/reports/tests.py，覆蓋每案一列、UI標題、重複處理紀錄合併、動態欄位對齊、公式字串防護、民國台灣時間檔名、PDF橫向與長文字續頁、私有內容與跨公司限制、空結果。5／5通過；Django check通過。
- E03：以假資料產生PDF並檢視首頁與末頁PNG，中文與表格正常，無重疊或裁切；只存忽略的.tools/report-qa。文件更新並重新啟動本機網站。完成。

重跑：`.\.venv\Scripts\python.exe backend/manage.py test apps.reports.tests --noinput --keepdb`。PDF影像驗證測試另需PyMuPDF（本機已安裝），不屬正式執行依賴。未匯出正式客戶資料或寄送郵件。


## 每家公司每日案件流水號（2026-11-11）

| 任務 | 工作 | 狀態 |
|---|---|---|
| N01 | 新增DailyTicketCounter與0002遷移，保留舊單號 | 完成 |
| N02 | 在既有建立案件交易中鎖定取號，不按案件筆數計算 | 完成 |
| N03 | 每日／公司隔離、取消與移除不回收、1000以上、代碼變更、舊單及並行測試 | 完成 |
| N04 | 套用本機遷移、核對既有資料、重啟與更新文件 | 完成 |

業務修改限backend/apps/tickets/models.py與services.py，另新增遷移與本次單號測試。既有瀏覽器測試檔名預期同步先前已上線的民國時間格式；未改前端、權限、派工、報表或刪除流程。


驗收：52／52測試通過（6單號測試、30 API、2領單競爭、9 Edge瀏覽器、5報表），包含四執行緒首次取號與既有計數器取號。Django check、遷移一致性檢查通過。本機zy_web已套用tickets.0002_daily_ticket_counter，資料表由23增為24；遷移前後逐筆pk＋單號雜湊一致，未建立正式測試案件或寄送測試信。新計數表初始為空，新案件當日首次送出才建立計數器。網站已重新啟動，首頁200；MySQL程序與worker未重啟。

重跑：`.\.venv\Scripts\python.exe backend/manage.py test apps.tickets.tests apps.api.tests apps.api.test_claim_concurrency apps.api.browser_tests apps.reports.tests --noinput --keepdb`。


## 贊耀公司人員統一角色（2026-11-11）

| 任務 | 工作 | 狀態 |
|---|---|---|
| U01 | 移除工程師獨立角色，沿用it_admin顯示為贊耀公司人員，資料遷移保留帳號與關聯 | 完成 |
| U02 | 接手直接處理中、已有人負責才可交接、全員查看及協助 | 完成 |
| U03 | 管理／權限／遷移／競爭／瀏覽器驗證，前端建置 | 完成：54項通過，收尾3項精準驗證通過 |
| U04 | 本機遷移、資料核對、重新啟動及操作文件更新 | 完成 |

業務資料欄位engineer與內部it_admin代碼保留，減少無關欄位及路由搬移。未改每日單號、附件儲存、密碼流程或公司端權限；報表與UI負責人標題同步。舊工程師權限測試改為統一角色權限預期，新增資料遷移保留與帳號角色選項驗證。


本次驗收：54／54完整回歸通過（31 API、2接手競爭、6每日單號、5報表、1角色資料遷移、9 Edge瀏覽器）；文字收尾後另3項角色管理／接手／交接精準驗證通過。TypeScript／Vite／PWA build、Django check、遷移一致性檢查通過。本機已套用accounts.0002與tickets.0003；逐筆比對帳號資料，僅舊engineer角色變更為it_admin，密碼、啟用／刪除、案件內容／負責人及每日計數器保持不變。網站與匿名Session API正常；未建立正式測試案件或寄送測試信，MySQL及worker程序未重啟。

重跑：`.\.venv\Scripts\python.exe backend/manage.py test apps.api.tests apps.api.test_claim_concurrency apps.tickets.tests apps.reports.tests apps.accounts.test_role_migration apps.api.browser_tests --noinput --keepdb`。


## 通知中心全部已讀（2026-11-11）

- B01：新增POST /api/notifications/read-all/，沿用原通知查詢的登入者與案件可見性限制，一次更新全部分頁內未讀通知；保留既有已讀時間，重複操作不重寫。完成。
- B02：通知中心新增全部標為已讀按鈕，無未讀或操作中停用。單筆／全部已讀後觸發通知更新事件，立即刷新鈴鐺及側邊未讀數；操作紀錄頁不顯示此按鈕。完成。
- B03：35／35測試通過（34 API回歸＋1 Edge通知流程），驗證跨頁、他人與無權案件通知不受影響、所有角色、登入／CSRF、GET不可變更、既有已讀時間不變、重複操作、新通知未讀及重新載入後狀態。TypeScript／Vite建置、Django check通過。本機網站已重啟且首頁200。完成。

修改限API通知處理及路由、ActivityView.vue與App.vue通知更新事件、相應測試及說明。無模型／遷移變更，未標記正式通知、寄送測試信或重啟資料庫與worker。

重跑：`.\.venv\Scripts\python.exe backend/manage.py test apps.api.tests apps.api.browser_tests.VueBrowserAcceptance.test_mark_all_notifications_updates_list_and_bell --noinput --keepdb`。


## 頭貼個人設定（2026-11-11）

- P01：新增本人資料API與ProfileForm白名單（姓名、電話／分機、手機、Email），驗證與稽核。完成。
- P02：新增ProfileView，頭貼／姓名連入、移除側邊改密碼入口，沿用既有密碼與驗證信API。完成。
- P03：51／51 API＋Edge回歸通過；版面收尾後另2項個人設定與強制改密碼瀏覽器測試通過。完成。
- P04：桌面／390px手機截圖檢視正常且無橫向溢出，TypeScript／Vite建置、Django check、遷移一致性檢查通過；網站已重啟，個人設定外殼200。完成。

驗證涵蓋三種角色、不可變更他人／公司／角色／工號等保護欄位、Email變更／清除後重驗、撤銷舊連結、未驗證不可忘記密碼、無變更不寫稽核、真實變更留欄位名稱、既有案件快照不變、修改密碼後維持登入並可用新密碼重新登入，以及臨時密碼無法直接進入個人設定。診斷截圖為忽略的.tools/vue-qa/profile-desktop.png與profile-mobile.png，僅用假資料。

未改模型、資料庫結構、帳號建立、公司隔離或其他案件流程；未建立正式測試資料、修改正式使用者或寄送真實測試信，MySQL與worker未重啟。

重跑：`.\.venv\Scripts\python.exe backend/manage.py test apps.api.tests apps.api.browser_tests --noinput --keepdb`。


## 取消Email驗證與自助密碼復原（2026-11-11）

- R01：停用API、舊頁面與issue_token／consume_token服務，舊連結亦不得驗證或重設；忘記密碼只顯示聯絡贊耀公司人員。完成。
- R02：移除首頁及個人設定Email驗證提示與按鈕，保留選填Email與格式驗證、直接寄送維修通知。完成。
- R03：54／54 API與Edge瀏覽器測試通過（41 API＋13瀏覽器），前端型別／Vite建置與Django check、遷移一致性檢查通過。驗證舊連結410、服務拒絕、復原不寄信、未驗證信箱照常寄維修通知、臨時密碼24小時到期、重設後原密碼及登入失效、不可沿用臨時密碼、前後端強制改密碼與既有個人設定流程。完成。
- R04：規範更新，網站已重啟，忘記密碼頁200、舊token API 410；MySQL與worker未重啟。完成。

無模型或migration變更，既有email_verified_at與ActionToken僅保留歷史相容；不修改維修通知、資料隔離、派工／接手、報表或recover_admin。正式資料庫查詢確認待寄的舊驗證／重設Email為0，未更動正式使用者、通知或Delivery，也未寄送真實測試信。

重跑：`.\.venv\Scripts\python.exe backend/manage.py test apps.api.tests apps.api.browser_tests --noinput --keepdb`。


## Email僅接手與完成（2026-11-11）

- M01：event新增預設關閉的send_email參數；接手處理與完成操作才開啟，站內通知繼續建立。完成。
- M02：新增4項通知規則測試，既有個人Email測試改用真實接手事件；47／47測試通過（4通知、41 API、2接手競爭）。完成。
- M03：Django check及無模型變更檢查通過，規範更新並重新啟動網站，首頁200。完成。

業務程式只改apps/notifications/services.py的排信條件與apps/tickets/services.py的兩個呼叫點。測試涵蓋接手／完成寄信、跨事件不寄、恢復處理不寄、站內通知仍建立、未驗證信箱可寄、無Email、停用額外收件人、地址去重與重複接手不排信。未改前端、SMTP或worker、其他權限與案件邏輯；無資料庫遷移，未建立正式測試案件或寄出測試信，既有郵件紀錄不變。

重跑：`.\.venv\Scripts\python.exe backend/manage.py test apps.notifications.tests apps.api.tests apps.api.test_claim_concurrency --noinput --keepdb`。


## 贊耀服務平台品牌與收合模組導覽（2026-11-11）

- G01：新增frontend/src/navigation.ts模組設定，報修系統入口內依原角色呈現子功能；App.vue加入可收合按鈕、aria-expanded／aria-controls、選取標示與模組麵包屑。完成。
- G02：更新前端平台／登入／安裝／離線頁及Manifest品牌，個人設定、安裝及登出維持共用入口。完成。
- G03：14／14 Edge瀏覽器測試通過（既有流程＋新收合／角色／鍵盤／手機／品牌檢查）、8／8 Node PWA政策測試通過；TypeScript／Vite build與Django check通過。完成。
- G04：檢視展開、收合、手機截圖，沒有遮擋或橫向溢出；目前8000網站首頁與Manifest皆已提供新名稱。文件已更新。完成。

功能修改限前端導覽與品牌呈現；後端僅更新相關瀏覽器測試，未改任何業務程式、資料表、權限服務、Email或報表。必要相容修正是將登入頁測試名稱改為新品牌；新測試通知選單採href定位，避免未讀數混入可存取名稱。診斷圖片僅存忽略的.tools/vue-qa/module-desktop.png、module-collapsed.png與module-mobile.png，皆為假資料。

重跑：先執行scripts/build_frontend.ps1，再執行`.\.venv\Scripts\python.exe backend/manage.py test apps.api.browser_tests --noinput --keepdb`；frontend目錄執行npm test。一般重新整理或接受PWA新版即可；本次不需重啟MySQL或worker。


## 科技藍及導覽層級配色（2026-11-11）

- H01：只調整app.css品牌、按鈕、焦點、側邊樣式，以及App.vue第一層固定底色；index.html／vite.config.ts同步PWA外觀色。完成。
- H02：3／3精準Edge測試通過，驗證第一／二層實際CSS色值、滑入、鍵盤焦點與收合後固定底色、主要按鈕、PWA主題色、角色選單、桌面手機登入與無橫向溢出；TypeScript／Vite建置通過。完成。
- H03：已檢視.tools/vue-qa/theme-desktop.png與theme-mobile.png，層級清楚、未遮擋；目前本機Manifest已提供新主題色。完成。

功能程式、後端權限、API、資料庫、狀態成功／警告／錯誤語意不變，未改SMTP或worker。測試初次定位問題已改為實際鍵盤Tab觸發focus-visible，並以原有管理者公司選單完成報修頁按鈕驗證；未為配合測試而修改報修功能。

重跑：先執行scripts/build_frontend.ps1，再執行`.\.venv\Scripts\python.exe backend/manage.py test apps.api.browser_tests.VueBrowserAcceptance.test_technology_theme_layers_focus_and_mobile apps.api.browser_tests.VueBrowserAcceptance.test_repair_module_collapses_permissions_mobile_and_brand apps.api.browser_tests.VueBrowserAcceptance.test_login_desktop_mobile_and_dashboard --noinput --keepdb`。


## 案件清單四欄與動態單號連結（2026-11-11）

- L01：僅DashboardView.vue將桌面清單改為問題單號、報修公司、狀態、更新時間；手機卡片維持同四欄，取消整卡連結及獨立箭頭。完成。
- L02：新增限本頁使用的單號樣式，hover 1.05倍／180ms／底線／手形，列滑入淡藍；transform避免推擠，鍵盤焦點與prefers-reduced-motion處理。完成。
- L03：16／16 Edge測試通過，包含四欄順序、詳情連結、實際transform、列高不變、減少動畫、鍵盤Enter、手機點擊範圍及無橫向溢出，並回歸原接手／交接、個人設定、通知及PWA流程。TypeScript／Vite建置通過，桌面／手機截圖檢查正常。完成。

後端只有相關瀏覽器測試更新（案件連結改用單號定位、離線斷言改檢查單號）；業務API、權限、資料庫、篩選與匯出未修改。診斷圖片為忽略的.tools/vue-qa/case-list-hover.png、case-list-mobile.png，僅假資料。未修改或寄送正式資料，無需重啟MySQL、網站或worker。

重跑：先執行scripts/build_frontend.ps1，再執行`.\.venv\Scripts\python.exe backend/manage.py test apps.api.browser_tests --noinput --keepdb`。


## 清單欄距、字體與詳情返回入口（2026-11-11）

- J01：DashboardView.vue使用colgroup固定單號欄範圍及狀態／時間欄寬，表頭近黑14px粗體、內容14px，手機同步；保留原連結動畫及四欄順序。完成。
- J02：TicketDetailView.vue將原返回文字改成返回案件總覽的淡藍底邊框連結，14px粗體、至少44px高度、hover加深；原路由及功能不變。完成。
- J03：3／3精準Edge測試通過（可讀性／欄距／返回、原四欄動畫與減少動畫、接手交接）；TypeScript／Vite build通過，桌面截圖已檢視，手機返回可用且無溢出。完成。

功能來源只修改上述兩個Vue頁面及限定範圍的scoped樣式，後端只有相關測試新增；未修改API、權限、資料庫、報表或其他程式邏輯。假資料截圖存忽略的.tools/vue-qa/case-list-readable.png及return-case-button.png。無需重啟服務，重新整理或接受PWA新版即可。

重跑：先執行scripts/build_frontend.ps1，再執行`.\.venv\Scripts\python.exe backend/manage.py test apps.api.browser_tests.VueBrowserAcceptance.test_case_list_readability_and_prominent_return_link apps.api.browser_tests.VueBrowserAcceptance.test_four_column_case_list_number_link_hover_and_mobile apps.api.browser_tests.VueBrowserAcceptance.test_staff_takeover_handover_and_assistance --noinput --keepdb`。


## 四欄平均與返回去底色（2026-11-11）

- K01：僅DashboardView.vue將col寬統一25%；TicketDetailView.vue返回連結改透明、無邊框，保留14px粗體、44px觸控高度與文字hover提示。完成。
- K02：2／2精準Edge測試通過，量測四欄等寬、一般／滑入透明背景與無邊框、返回操作、手機無溢出；原單號動畫與減少動畫測試通過。TypeScript／Vite建置通過，更新後桌面截圖已檢視。完成。

僅兩個頁面的限定樣式及相應測試預期變更，未改後端業務、資料庫、API或其他功能。重新整理或接受PWA新版即可，無需重啟服務。


## 關閉前端操作紀錄查詢（2026-11-12）

- A01：移除操作紀錄導覽項目及 Vue 路由，舊 /audit/、帶查詢參數及子路徑由既有未知路由規則導回案件總覽。完成。
- A02：TypeScript／Vite／PWA 建置與 Django check 通過；2／2 精準瀏覽器測試通過，確認選單移除、舊網址導向、不請求 audit API、後端仍產生操作紀錄，以及通知中心全部已讀正常。完成。

僅調整前端導覽、路由與相應測試，後端操作紀錄寫入、資料表及既有受權限控管的 API 保留。重新整理或接受 PWA 新版後生效。


## 新增報修返回入口一致化（2026-11-12）

- 將 TicketCreateView.vue 返回入口移至標題上方，改為「返回案件總覽」，沿用案件詳情頁的透明背景、藍色文字、箭頭、14px粗體與滑入底線樣式。完成。
- TypeScript／Vite／PWA 建置及 Django check 通過；2／2 精準瀏覽器測試通過，包含桌面／手機位置與樣式、返回導覽、報修送出與附件下載、原詳情返回功能。完成。


## 系統設定與 HiNet SMTP（2026-11-12）

- S01：沿用 notifications 模組新增 SystemSettings 單筆設定及 Delivery.is_test，產生並套用 0002 遷移。本機獨立 Fernet 金鑰已寫入忽略的 .env，密碼加密存庫且 API 不回傳密文／明文。完成。
- S02：新增贊耀公司人員專用設定 API，保留 Session／CSRF／臨時密碼閘門；設定版本衝突回應 409，變更以欄位名稱寫入操作紀錄。完成。
- S03：側欄新增獨立系統設定入口，提供基本資料、SMTP、HiNet 快速套用、密碼更換與測試信狀態；基本資料套用網站品牌及聯絡方式。完成。
- S04：寄信 worker 每次寄送讀取資料庫設定，尚未啟用 UI 設定時沿用 .env。測試信共用原 outbox／重試流程，原維修通知寄送事件維持。完成。
- S05：49／49 後端 API 測試、4／4 瀏覽器測試、8／8 PWA 政策測試通過；TypeScript／Vite／PWA 建置、Django check、遷移一致性及新增檔案 Ruff 檢查通過。已以隔離本機 SMTP 驗證實際郵件傳輸，手機截圖檢查完成。完成。

本機網站已自動重載新程式，寄信 worker 已啟動。HiNet 真實帳密驗證及外部收件結果尚待使用者在 UI 填入目前有效的寄信密碼後執行測試；未使用聊天中的密碼設定寄信。PWA 安裝名稱及歷史報表／信件維持原定義。


## 系統設定收進報修入口（2026-11-12）

- 僅調整 navigation.ts 與 App.vue 的導覽配置，系統設定移為報修系統入口的子項，依既有規則收合、標示選取及顯示麵包屑。完成。
- 前端建置、Django check 與 2／2 相關瀏覽器測試通過，包含設定子項收合、當前選取、麵包屑、設定操作及原角色選單／手機行為。完成。


## 案件狀態與角色呈現整併（2026-11-12）

- ST01：移除目前案件的 unassigned／closed，新增 tickets/0004 遷移分別轉 assigned／completed，增加 revision，保留案件其他欄位與 StatusHistory，並寫入遷移摘要。新案件預設 assigned、負責人空白，接手操作與行鎖保留。完成。
- ST02：新增共用 statuses.py，統一角色狀態名稱、統計、篩選及可用轉換；同步 API、舊版入口與 PDF／Excel。移除確認結案操作，已完成視為終止狀態納入帳號停用檢查。完成。
- ST03：贊耀人員卡片／篩選為處理中、待客戶回覆、已完成、已取消；客戶端為處理中、已完成、已取消，桌面三欄均分；客戶端將 assigned／processing／waiting 合併呈現處理中。完成。
- ST04：63／63 相關後端測試及 19／19 完整瀏覽器測試通過，涵蓋角色隔離、統計篩選、詳情、實際 PDF／Excel、接手併發、通知時機與舊資料遷移；TypeScript／Vite／PWA 建置、Django check 及遷移一致性檢查通過，已檢視兩角色桌面截圖。完成。

現有業務資料庫的 1 筆 closed 已轉 completed，案件其他欄位與全部狀態歷史雜湊比對一致，已無 unassigned／closed 的目前案件。歷史紀錄仍保留當時狀態。重新整理或接受 PWA 新版後可看到新卡片及選項。


## 公司管理者管理本公司報修者（2026-11-12）

- CA01：開放公司管理者新增本公司報修者，UserForm 固定公司與 reporter 角色，保留帳號格式／唯一限制及既有帳號唯讀。API 與原頁面同時調整，交易鎖定後重新確認可管理目標。完成。
- CA02：公司管理者可重設本公司報修者臨時密碼、啟停與邏輯刪除，沿用密碼雜湊、24 小時期限、舊登入撤銷、首次強制改密碼及操作紀錄。公司管理者、贊耀帳號及其他公司帳號由原權限阻擋。完成。
- CA03：UsersView 開放公司管理者新增及操作選單，顯示固定公司／角色；同步忘記密碼說明與操作手冊。完成。
- CA04：41／41 既有 API 測試及 6／6 新增公司帳號測試通過，涵蓋公司／角色竄改、重複帳號、跨公司與管理者限制、重設／啟停／刪除、舊入口及案件快照保留。3／3 相關瀏覽器測試通過，包含公司管理者建帳與生命週期、員工首次改密碼及忘記密碼說明。前端建置、Django check、遷移一致性與新增測試 Ruff 檢查通過。完成。

本次不需資料庫結構遷移；實際使用者帳號未被測試修改，假資料均使用獨立測試資料庫。重新整理或接受 PWA 新版即可使用。


## 螢幕擷取與跨螢幕截圖貼上（2026-11-12）

- SC01：新增 ScreenCapture.vue，使用瀏覽器授權擷取單一螢幕／視窗，靜態預覽可框選、重設完整畫面、確認加入 PNG 或取消；正常、取消、離頁與延遲授權皆停止串流並釋放預覽。完成。
- SC02：AttachmentPicker 加入擷取入口及 Windows Win＋Shift＋S／Ctrl＋V 跨螢幕操作提示，沿用原附件格式、五個／10MB 限制。新增報修在附件更新時標記未儲存狀態。完成。
- SC03：7／7 相關瀏覽器測試通過（五項新增、兩項既有上傳／表單換版），涵蓋四種裝置縮放、框選後改變視窗、裁切像素及實際送單下載、取消／不支援／延遲授權清理、附件上限與離頁保護。3840×1080 圖片貼上後上傳下載位元組一致。完成。
- SC04：TypeScript／Vite／PWA 建置及 Django check、差異格式檢查通過，已檢視模擬擷取的裁切預覽截圖。完成。

自動擷取驗證使用 Canvas 模擬 MediaStream。實體螢幕來源選擇、Windows 跨螢幕框選及混合 DPI 尚待現機確認，未宣稱已完成硬體驗收。本次無後端業務與資料庫結構變更，重新整理或接受 PWA 更新後生效。

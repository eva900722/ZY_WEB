"""Browser acceptance limited to the Vue/PWA migration; all data goes to test_zy_web."""

import io, os, tempfile
from pathlib import Path
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.utils import timezone
from django.db import connections
from playwright.sync_api import sync_playwright, expect
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.accounts.services import temporary_password
from apps.companies.models import Company
from apps.forms.models import FormVersion
from apps.forms.services import publish
from apps.tickets.services import create_ticket

PASSWORD = "Vue-Browser-Test!359218"
ROOT = Path(__file__).resolve().parents[3]
SHOTS = ROOT / ".tools/vue-qa"


@override_settings(
    DEBUG=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
class VueBrowserAcceptance(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        SHOTS.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.media_override = override_settings(PRIVATE_MEDIA_ROOT=self.media.name)
        self.media_override.enable()
        self.company = Company.objects.create(name="揚發企業", code="vueyf")

        def u(name, role, company=None):
            return User.objects.create_user(
                username=name,
                display_name={
                    "reporter": "王小明",
                    "manager": "林經理",
                    "admin": "資訊管理者",
                    "engineer": "陳工程師",
                }[name],
                password=PASSWORD,
                role=role,
                company=company,
                must_change_password=False,
            )

        self.admin = u("admin", "it_admin")
        self.reporter = u("reporter", "reporter", self.company)
        self.manager = u("manager", "company_admin", self.company)
        self.engineer = u("engineer", "it_admin")
        self.version = FormVersion.objects.create(
            company=self.company,
            number=1,
            fields=[],
            published_at=timezone.now(),
            created_by=self.admin,
        )
        self.ticket = create_ticket(
            self.reporter,
            self.company,
            self.reporter,
            self.version,
            {
                "title": "辦公室印表機無法列印",
                "description": "今天早上開始無法列印，重新啟動後仍發生相同問題。",
            },
            {},
        )
        self.play = sync_playwright().start()
        self.browser = self.play.chromium.launch(
            executable_path=os.getenv(
                "E2E_BROWSER",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            ),
            headless=True,
        )
        self.context = self.browser.new_context(
            viewport={"width": 1440, "height": 1000}
        )
        self.page = self.context.new_page()
        self.page.set_default_timeout(12000)
        self.page.set_default_navigation_timeout(15000)
        self.errors = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.on(
            "console",
            lambda msg: (
                print("BROWSER_" + msg.type + ": " + msg.text, flush=True)
                if msg.type in ["error", "warning"]
                else None
            ),
        )

    def tearDown(self):
        self.context.close()
        self.browser.close()
        self.play.stop()
        self.media_override.disable()
        self.media.cleanup()
        self.assertEqual(self.errors, [])

    def db(self, fn):
        def run():
            try:
                return fn()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(run).result()

    def login(self, name="reporter", password=PASSWORD):
        self.page.goto(self.live_server_url + "/accounts/login/")
        self.page.locator("[name=username]").fill(name)
        self.page.locator("[name=password]").fill(password)
        self.page.get_by_role("button", name="登入", exact=True).click()
        self.page.wait_for_url(lambda url: "/accounts/login" not in str(url))

    def test_login_desktop_mobile_and_dashboard(self):
        self.page.goto(self.live_server_url + "/accounts/login/")
        expect(self.page.get_by_role("heading", name="登入贊耀服務平台")).to_be_visible()
        self.page.screenshot(
            path=str(SHOTS / "login-desktop.png"), full_page=True, animations="disabled"
        )
        card = self.page.locator(".auth-card").bounding_box()
        self.assertLessEqual(card["width"], 440)
        self.login("admin")
        expect(self.page.get_by_role("heading", name="案件總覽")).to_be_visible()
        self.page.screenshot(
            path=str(SHOTS / "dashboard-desktop.png"),
            full_page=True,
            animations="disabled",
        )
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.screenshot(
            path=str(SHOTS / "dashboard-mobile.png"),
            full_page=True,
            animations="disabled",
        )
        self.assertLessEqual(
            self.page.evaluate("document.documentElement.scrollWidth"), 392
        )
        self.page.get_by_role("button", name="開啟選單").click()
        expect(self.page.locator(".sidebar.open")).to_be_visible()
        self.page.get_by_role("button", name="登出系統", exact=True).click()
        expect(self.page.get_by_role("heading", name="登入贊耀服務平台")).to_be_visible()
        self.page.screenshot(
            path=str(SHOTS / "login-mobile.png"), full_page=True, animations="disabled"
        )

    def test_reporter_create_attachment_and_download(self):
        self.login()
        self.page.goto(self.live_server_url + "/tickets/new/")
        back = self.page.get_by_role("link", name="返回案件總覽", exact=True)
        for width, height in ((1440, 900), (390, 844)):
            self.page.set_viewport_size({"width": width, "height": height})
            expect(back).to_have_attribute("href", "/")
            expect(back).to_have_css("background-color", "rgba(0, 0, 0, 0)")
            expect(back).to_have_css("border-top-style", "none")
            expect(back).to_have_css("font-size", "14px")
            expect(back).to_have_css("font-weight", "650")
            title = self.page.get_by_role("heading", name="新增報修", exact=True)
            self.assertLessEqual(back.bounding_box()["y"] + back.bounding_box()["height"], title.bounding_box()["y"])
            self.assertGreaterEqual(back.bounding_box()["height"], 44)
            self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
        self.page.set_viewport_size({"width": 1440, "height": 900})
        back.hover()
        expect(back).to_have_css("text-decoration-line", "underline")
        self.page.screenshot(path=str(SHOTS / "create-return-link.png"), full_page=True, animations="disabled")
        back.click()
        expect(self.page.get_by_role("heading", name="案件總覽", exact=True)).to_be_visible()
        self.page.goto(self.live_server_url + "/tickets/new/")
        self.page.get_by_label("問題摘要 *").fill("Vue實際送出案件")
        self.page.get_by_label("問題描述 *").fill("驗證新介面報修與圖片附件。")
        from PIL import Image

        data = io.BytesIO()
        Image.new("RGB", (180, 100), "#176953").save(data, format="PNG")
        self.page.locator("input[type=file]").set_input_files(
            {"name": "screen.png", "mimeType": "image/png", "buffer": data.getvalue()}
        )
        self.page.get_by_role("button", name="送出報修", exact=True).click()
        expect(
            self.page.get_by_role("heading", name="Vue實際送出案件", exact=True)
        ).to_be_visible()
        expect(self.page.get_by_role("link", name="screen.png")).to_be_visible()
        with self.page.expect_download() as download:
            self.page.get_by_role("link", name="Excel", exact=True).click()
        self.assertRegex(download.value.suggested_filename, r"^\d{7}_\d{4}\.xlsx$")
        self.page.screenshot(
            path=str(SHOTS / "ticket-detail.png"), full_page=True, animations="disabled"
        )

    def test_staff_takeover_handover_and_assistance(self):
        self.login("admin")
        self.page.goto(self.live_server_url + f"/tickets/{self.ticket.pk}/")
        expect(self.page.get_by_role("button", name="確認交接", exact=True)).to_have_count(0)
        self.page.get_by_role("button", name="接手處理", exact=True).click()
        expect(self.page.locator(".heading-actions .status")).to_have_text("處理中")
        self.page.locator("[name=engineer]").select_option(str(self.engineer.pk))
        self.page.locator("[name=assignment_reason]").fill("請同事接續追蹤")
        self.page.get_by_role("button", name="確認交接", exact=True).click()
        self.page.get_by_role("button", name="登出系統", exact=True).click()
        self.login("engineer")
        self.page.get_by_role("link", name=self.ticket.number, exact=True).first.click()
        self.page.locator("[name=status]").select_option("waiting")
        self.page.locator("[name=reason]").fill("已聯絡客戶")
        self.page.get_by_role("button", name="更新狀態", exact=True).click()
        expect(self.page.locator(".heading-actions .status")).to_have_text("待客戶回覆")

    def test_temporary_password_must_change(self):
        raw = self.db(lambda: temporary_password(self.admin, self.reporter))
        self.login(password=raw)
        expect(self.page.get_by_role("heading", name="設定個人密碼")).to_be_visible()
        self.page.locator("[name=password]").fill(raw)
        self.page.locator("[name=new_password1]").fill("Changed-Vue-Browser!9876")
        self.page.locator("[name=new_password2]").fill("Changed-Vue-Browser!9876")
        self.page.get_by_role("button", name="設定密碼並繼續").click()
        expect(self.page.get_by_role("heading", name="案件總覽")).to_be_visible()

    def test_form_version_switch_preserves_text_and_files(self):
        self.login()
        self.page.goto(self.live_server_url + "/tickets/new/")
        self.page.get_by_label("問題摘要 *").fill("表單版本切換")
        self.page.get_by_label("問題描述 *").fill("這份內容必須保留")
        v = self.db(
            lambda: FormVersion.objects.create(
                company=self.company,
                number=2,
                fields=[
                    {
                        "key": "device",
                        "label": "設備類型",
                        "type": "text",
                        "required": True,
                    }
                ],
                created_by=self.admin,
            )
        )
        self.db(lambda: publish(self.admin, v, True))
        self.page.get_by_role("button", name="送出報修", exact=True).click()
        expect(
            self.page.get_by_role("button", name="保留內容並切換新版")
        ).to_be_visible()
        self.page.get_by_role("button", name="保留內容並切換新版").click()
        expect(self.page.get_by_label("問題描述 *")).to_have_value("這份內容必須保留")
        self.page.locator("[name=field_device]").fill("印表機")
        self.page.get_by_role("button", name="送出報修", exact=True).click()
        expect(
            self.page.get_by_role("heading", name="表單版本切換", exact=True)
        ).to_be_visible()

    def test_admin_forms_and_role_menus(self):
        self.login("admin")
        self.page.goto(self.live_server_url + "/companies/")
        self.page.get_by_role("button", name="新增公司", exact=True).click()
        self.page.locator("[name=name]").fill("Vue新公司")
        self.page.locator("[name=code]").fill("vue-new")
        self.page.get_by_role("button", name="儲存公司", exact=True).click()
        expect(
            self.page.get_by_role("heading", name="Vue新公司", exact=True)
        ).to_be_visible()
        self.page.goto(self.live_server_url + "/users/")
        self.page.get_by_role("button", name="新增帳號", exact=True).click()
        self.page.locator("[name=username]").fill("vue-newuser")
        self.page.locator("[name=display_name]").fill("測試新人")
        self.page.locator("[name=company]").select_option(str(self.company.pk))
        self.page.get_by_role("button", name="儲存帳號", exact=True).click()
        expect(self.page.get_by_role("heading", name="帳號已準備完成")).to_be_visible()
        self.page.get_by_role("button", name="已記錄，完成").click()
        self.page.goto(self.live_server_url + "/versions/")
        self.page.get_by_role("button", name="建立草稿", exact=True).click()
        self.page.get_by_label("所屬公司 *").select_option(str(self.company.pk))
        self.page.get_by_role("button", name="新增欄位", exact=True).click()
        self.page.get_by_label("欄位名稱 *").fill("設備分類")
        self.page.get_by_role("button", name="儲存草稿", exact=True).click()
        self.page.screenshot(
            path=str(SHOTS / "form-designer.png"), full_page=True, animations="disabled"
        )
        expect(self.page.locator('#module-repairs a[href="/audit/"]')).to_have_count(0)
        audit_requests = []
        self.page.on("request", lambda request: audit_requests.append(request.url)
                     if "/api/audit/" in request.url else None)
        for path in ("/audit/", "/audit/?actor=admin", "/audit/old/"):
            self.page.goto(self.live_server_url + path)
            expect(self.page.get_by_role("heading", name="案件總覽", exact=True)).to_be_visible()
            self.assertEqual(urlsplit(self.page.url).path, "/")
            expect(self.page.get_by_role("heading", name="操作紀錄", exact=True)).to_have_count(0)
        self.assertEqual(audit_requests, [])
        self.assertTrue(self.db(lambda: AuditLog.objects.filter(actor_id=self.admin.pk).exists()))
        self.page.goto(self.live_server_url + "/notifications/")
        expect(self.page.get_by_role("heading", name="通知中心", exact=True)).to_be_visible()
        self.page.get_by_role("button", name="登出系統", exact=True).click()
        self.login("manager")
        self.assertEqual(
            self.page.get_by_role("link", name="公司管理", exact=True).count(), 0
        )
        self.page.goto(self.live_server_url + "/users/")
        expect(self.page.get_by_role("button", name="新增帳號", exact=True)).to_be_visible()

    def test_pwa_manifest_cache_and_offline(self):
        self.login()
        expect(self.page.get_by_role("heading", name="案件總覽")).to_be_visible()
        manifest = self.page.request.get(
            self.live_server_url + "/manifest.webmanifest"
        ).json()
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(
            {i["sizes"] for i in manifest["icons"]}, {"192x192", "512x512"}
        )
        self.page.wait_for_function(
            "async()=>Boolean((await navigator.serviceWorker.getRegistration())?.active)",
            timeout=15000,
        )
        self.page.reload()
        self.page.wait_for_function("navigator.serviceWorker.controller !== null")
        self.page.request.get(self.live_server_url + "/api/tickets/")
        urls = self.page.evaluate(
            "async()=>{const keys=await caches.keys();const out=[];for(const key of keys){const c=await caches.open(key);for(const r of await c.keys())out.push(r.url)}return out}"
        )
        self.assertTrue(urls)
        self.assertFalse(
            any(
                "/api/" in u
                or "/attachments/" in u
                or "/reports/" in u
                or "/accounts/token/" in u
                for u in urls
            )
        )
        self.context.set_offline(True)
        self.page.reload()
        expect(
            self.page.get_by_text(
                "目前離線，案件查詢與送出需連上網路；未送出的內容仍留在目前畫面。",
                exact=True,
            )
        ).to_be_visible()
        self.assertEqual(
            self.page.get_by_text(self.ticket.number, exact=True).count(), 0
        )
        self.context.set_offline(False)
        self.page.goto(self.live_server_url + "/")
        expect(self.page.get_by_role("heading", name="案件總覽")).to_be_visible()

    def test_pwa_update_prompt_keeps_dirty_form(self):
        self.login()
        expect(self.page.get_by_role("heading", name="案件總覽")).to_be_visible()
        self.page.wait_for_function(
            "async()=>Boolean((await navigator.serviceWorker.getRegistration())?.active)",
            timeout=15000,
        )
        self.page.reload()
        self.page.wait_for_function("navigator.serviceWorker.controller !== null")
        self.page.goto(self.live_server_url + "/tickets/new/")
        self.page.get_by_label("問題摘要 *").fill("更新時不能遺失內容")
        self.page.clock.install()
        self.page.clock.fast_forward(61000)
        sw = ROOT / "frontend/dist/sw.js"
        original = sw.read_text(encoding="utf-8")
        try:
            sw.write_text(
                original + "\n// isolated QA update probe\n", encoding="utf-8"
            )
            self.page.evaluate(
                "async()=>{const registration=await navigator.serviceWorker.getRegistration();await registration.update()}"
            )
            expect(
                self.page.get_by_role("button", name="立即更新", exact=True)
            ).to_be_visible(timeout=15000)
            self.page.get_by_role("button", name="立即更新", exact=True).click()
            expect(self.page.get_by_label("問題摘要 *")).to_have_value(
                "更新時不能遺失內容"
            )
            expect(
                self.page.get_by_text(
                    "請先送出或處理尚未完成的表單，再更新應用程式", exact=True
                )
            ).to_be_visible()
        finally:
            sw.write_text(original, encoding="utf-8")

    def test_staff_self_takeover(self):
        self.login("engineer")
        self.page.get_by_role("link", name=self.ticket.number, exact=True).first.click()
        self.page.get_by_role("button", name="接手處理", exact=True).click()
        expect(self.page.locator(".heading-actions .status")).to_have_text("處理中")
        expect(self.page.get_by_role("button", name="接手處理", exact=True)).to_have_count(0)
        expect(self.page.get_by_role("button", name="送出補充", exact=True)).to_be_visible()
        self.page.locator("[name=status]").select_option("completed")
        self.page.locator("[name=reason]").fill("接手後完成維修")
        self.page.get_by_role("button", name="更新狀態", exact=True).click()
        expect(self.page.locator(".heading-actions .status")).to_have_text("已完成")

    def test_mark_all_notifications_updates_list_and_bell(self):
        from apps.notifications.models import Notification
        self.db(lambda: Notification.objects.bulk_create([
            Notification(user=self.reporter, ticket=self.ticket, message=f"全部已讀測試{i}") for i in range(30)
        ]))
        self.login()
        self.page.goto(self.live_server_url + "/notifications/")
        button = self.page.get_by_role("button", name="全部標為已讀", exact=True)
        expect(button).to_be_enabled()
        expect(self.page.locator(".notification-button i")).to_have_count(1)
        button.click()
        expect(button).to_be_disabled()
        expect(self.page.locator(".notification-item.unread")).to_have_count(0)
        expect(self.page.locator(".notification-button i")).to_have_count(0)
        self.assertFalse(self.db(lambda: self.reporter.notifications.filter(read_at__isnull=True).exists()))
        self.assertTrue(self.db(lambda: self.admin.notifications.filter(read_at__isnull=True).exists()))
        self.page.reload()
        expect(button).to_be_disabled()

    def test_avatar_profile_contact_email_and_password(self):
        self.login()
        expect(self.page.locator(".sidebar-bottom").get_by_text("修改密碼", exact=True)).to_have_count(0)
        self.page.get_by_role("link", name="個人設定", exact=True).click()
        expect(self.page.get_by_role("heading", name="個人設定", exact=True)).to_be_visible()
        self.page.set_viewport_size({"width": 1440, "height": 1000})
        self.page.screenshot(path=str(SHOTS / "profile-desktop.png"), full_page=True, animations="disabled")
        self.page.set_viewport_size({"width": 390, "height": 844})
        expect(self.page.get_by_role("link", name="個人設定", exact=True)).to_be_visible()
        self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
        self.page.screenshot(path=str(SHOTS / "profile-mobile.png"), full_page=True, animations="disabled")
        self.page.set_viewport_size({"width": 1440, "height": 1000})
        self.page.locator("[name=display_name]").fill("新姓名")
        self.page.locator("[name=phone]").fill("02-1234#8")
        self.page.locator("[name=email]").fill("profile@example.invalid")
        self.page.get_by_role("button", name="儲存個人資料", exact=True).click()
        expect(self.page.locator(".user-info strong")).to_have_text("新姓名")
        expect(self.page.get_by_role("button", name="寄送驗證信", exact=True)).to_have_count(0)
        expect(self.page.get_by_text("Email選填，儲存後直接依此信箱寄送維修通知，不需驗證。忘記密碼請聯絡贊耀公司人員。", exact=True)).to_be_visible()
        self.page.locator("[name=old_password]").fill(PASSWORD)
        self.page.locator("[name=new_password1]").fill("New-Profile-Test!92638")
        self.page.locator("[name=new_password2]").fill("New-Profile-Test!92638")
        self.page.get_by_role("button", name="更新密碼", exact=True).click()
        expect(self.page.locator("[name=old_password]")).to_have_value("")
        self.page.reload()
        expect(self.page.get_by_role("heading", name="個人設定", exact=True)).to_be_visible()
        self.page.get_by_role("button", name="登出系統", exact=True).click()
        self.login(password="New-Profile-Test!92638")
        expect(self.page.get_by_role("heading", name="案件總覽", exact=True)).to_be_visible()

    def test_temporary_password_blocks_profile_direct_navigation(self):
        raw = self.db(lambda: temporary_password(self.admin, self.reporter))
        self.login(password=raw)
        self.page.goto(self.live_server_url + "/settings/profile/")
        expect(self.page.get_by_role("heading", name="設定個人密碼", exact=True)).to_be_visible()

    def test_forgot_password_is_contact_instructions_and_old_link_disabled(self):
        self.page.goto(self.live_server_url + "/accounts/login/")
        self.page.get_by_role("link", name="忘記密碼？", exact=True).click()
        expect(self.page.get_by_role("heading", name="忘記密碼", exact=True)).to_be_visible()
        expect(self.page.get_by_text("報修者請聯絡本公司管理者或贊耀公司人員重設臨時密碼；公司管理者請聯絡贊耀公司人員。使用臨時密碼登入後，必須先設定自己的密碼才能繼續使用。", exact=True)).to_be_visible()
        expect(self.page.locator("form")).to_have_count(0)
        self.page.goto(self.live_server_url + "/accounts/token/old-link/")
        expect(self.page.get_by_role("heading", name="連結已停用", exact=True)).to_be_visible()
        expect(self.page.locator("form")).to_have_count(0)

    def test_repair_module_collapses_permissions_mobile_and_brand(self):
        self.login("admin")
        toggle = self.page.get_by_role("button", name="報修系統入口", exact=True)
        nav = self.page.get_by_role("navigation", name="報修系統入口", exact=True)
        expect(toggle).to_have_attribute("aria-expanded", "true")
        expect(nav.get_by_role("link", name="公司管理", exact=True)).to_be_visible()
        self.assertEqual(self.page.title(), "贊耀服務平台｜企業報修服務")
        manifest = self.page.request.get(self.live_server_url + "/manifest.webmanifest").json()
        self.assertEqual(manifest["name"], "贊耀服務平台")
        toggle.click()
        expect(toggle).to_have_attribute("aria-expanded", "false")
        expect(self.page.locator("#module-repairs")).not_to_be_visible()
        expect(self.page.get_by_role("button", name="登出系統", exact=True)).to_be_visible()
        self.page.screenshot(path=str(SHOTS / "module-collapsed.png"), full_page=True, animations="disabled")
        toggle.focus()
        self.page.keyboard.press("Enter")
        expect(toggle).to_have_attribute("aria-expanded", "true")
        nav.locator('a[href="/notifications/"]').click()
        expect(self.page.locator(".breadcrumb")).to_contain_text("報修系統入口")
        expect(self.page.locator(".breadcrumb strong")).to_have_text("通知中心")
        self.page.screenshot(path=str(SHOTS / "module-desktop.png"), full_page=True, animations="disabled")
        self.page.get_by_role("button", name="登出系統", exact=True).click()
        self.login("reporter")
        self.assertEqual(self.page.locator("#module-repairs a").count(), 3)
        expect(self.page.locator("#module-repairs").get_by_role("link", name="公司管理", exact=True)).to_have_count(0)
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.get_by_role("button", name="開啟選單", exact=True).click()
        toggle.click()
        expect(toggle).to_have_attribute("aria-expanded", "false")
        toggle.click()
        self.page.screenshot(path=str(SHOTS / "module-mobile.png"), full_page=True, animations="disabled")
        self.page.locator("#module-repairs").get_by_role("link", name="新增報修", exact=True).click()
        expect(self.page.locator(".sidebar")).not_to_have_class("sidebar open")
        expect(self.page.get_by_role("heading", name="新增報修", exact=True)).to_be_visible()
        self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))

    def test_technology_theme_layers_focus_and_mobile(self):
        self.login("admin")
        toggle = self.page.get_by_role("button", name="報修系統入口", exact=True)
        selected = self.page.locator('#module-repairs a[aria-current="page"]')
        expect(toggle).to_have_css("background-color", "rgb(30, 58, 95)")
        expect(toggle).to_have_css("color", "rgb(248, 250, 252)")
        expect(self.page.locator(".sidebar")).to_have_css("background-color", "rgb(15, 23, 42)")
        expect(selected).to_have_css("background-color", "rgb(207, 250, 254)")
        expect(selected).to_have_css("color", "rgb(22, 78, 99)")
        normal = self.page.locator('#module-repairs a[href="/tickets/new/"]')
        normal.hover()
        expect(normal).to_have_css("background-color", "rgb(30, 41, 59)")
        toggle.focus()
        self.page.keyboard.press("Tab")
        self.page.keyboard.press("Shift+Tab")
        expect(toggle).to_have_css("outline-color", "rgb(34, 211, 238)")
        self.page.mouse.move(1300, 800)
        self.page.keyboard.press("Enter")
        expect(toggle).to_have_attribute("aria-expanded", "false")
        expect(toggle).to_have_css("background-color", "rgb(30, 58, 95)")
        self.page.keyboard.press("Enter")
        expect(toggle).to_have_attribute("aria-expanded", "true")
        self.page.screenshot(path=str(SHOTS / "theme-desktop.png"), full_page=True, animations="disabled")
        self.page.locator('#module-repairs a[href="/tickets/new/"]').click()
        self.page.locator(".panel.compact select").select_option(str(self.company.pk))
        self.page.mouse.move(0, 0)
        expect(self.page.get_by_role("button", name="送出報修", exact=True)).to_have_css("background-color", "rgb(37, 99, 235)")
        manifest = self.page.request.get(self.live_server_url + "/manifest.webmanifest").json()
        self.assertEqual(manifest["theme_color"], "#0f172a")
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.get_by_role("button", name="開啟選單", exact=True).click()
        expect(toggle).to_be_visible()
        expect(toggle).to_have_css("background-color", "rgb(30, 58, 95)")
        self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
        self.page.screenshot(path=str(SHOTS / "theme-mobile.png"), full_page=True, animations="disabled")

    def test_four_column_case_list_number_link_hover_and_mobile(self):
        self.login()
        table = self.page.locator(".case-table")
        expect(table.locator("thead th")).to_have_text(["問題單號", "報修公司", "狀態", "更新時間"])
        expect(table.locator("tbody tr").first.locator("td")).to_have_count(4)
        expect(table).not_to_contain_text(self.ticket.title)
        link = table.get_by_role("link", name=self.ticket.number, exact=True)
        expect(link).to_have_attribute("href", f"/tickets/{self.ticket.pk}/")
        before = table.locator("tbody tr").first.bounding_box()["height"]
        link.hover()
        expect(link).to_have_css("transform", "matrix(1.05, 0, 0, 1.05, 0, 0)")
        expect(link).to_have_css("cursor", "pointer")
        expect(link).to_have_css("text-decoration-line", "underline")
        self.assertAlmostEqual(table.locator("tbody tr").first.bounding_box()["height"], before, places=1)
        self.page.screenshot(path=str(SHOTS / "case-list-hover.png"), full_page=True)
        self.page.emulate_media(reduced_motion="reduce")
        expect(link).to_have_css("transform", "none")
        expect(link).to_have_css("transition-duration", "0s")
        self.page.emulate_media(reduced_motion="no-preference")
        link.focus()
        self.page.keyboard.press("Enter")
        expect(self.page.get_by_role("heading", name=self.ticket.title, exact=True)).to_be_visible()
        self.page.goto(self.live_server_url + "/")
        self.page.set_viewport_size({"width": 390, "height": 844})
        fields = self.page.locator(".mobile-ticket .case-mobile-fields").first
        expect(fields.locator("dt")).to_have_text(["問題單號", "報修公司", "狀態", "更新時間"])
        expect(fields).not_to_contain_text(self.ticket.title)
        fields.get_by_text(self.company.name, exact=True).click()
        self.assertEqual(self.page.url, self.live_server_url + "/")
        self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
        self.page.screenshot(path=str(SHOTS / "case-list-mobile.png"), full_page=True, animations="disabled")
        fields.get_by_role("link", name=self.ticket.number, exact=True).click()
        expect(self.page.get_by_role("heading", name=self.ticket.title, exact=True)).to_be_visible()

    def test_case_list_readability_and_prominent_return_link(self):
        self.login()
        table = self.page.locator(".case-table")
        heading = table.locator("th").first
        expect(heading).to_have_css("color", "rgb(17, 24, 39)")
        expect(heading).to_have_css("font-size", "14px")
        expect(heading).to_have_css("font-weight", "700")
        link = table.get_by_role("link", name=self.ticket.number, exact=True)
        expect(link).to_have_css("font-size", "14px")
        expect(table.locator("td").nth(1)).to_have_css("font-size", "14px")
        widths = [table.locator("td").nth(i).bounding_box()["width"] for i in range(4)]
        for width in widths:
            self.assertAlmostEqual(width, widths[0], delta=1)
        self.page.screenshot(path=str(SHOTS / "case-list-readable.png"), full_page=True, animations="disabled")
        link.click()
        back = self.page.get_by_role("link", name="返回案件總覽", exact=True)
        expect(back).to_have_attribute("href", "/")
        expect(back).to_have_css("background-color", "rgba(0, 0, 0, 0)")
        expect(back).to_have_css("border-top-style", "none")
        expect(back).to_have_css("font-size", "14px")
        self.assertGreaterEqual(back.bounding_box()["height"], 44)
        back.hover()
        expect(back).to_have_css("background-color", "rgba(0, 0, 0, 0)")
        expect(back).to_have_css("text-decoration-line", "underline")
        self.page.mouse.move(1300, 800)
        self.page.screenshot(path=str(SHOTS / "return-case-button.png"), full_page=True, animations="disabled")
        back.click()
        expect(self.page.get_by_role("heading", name="案件總覽", exact=True)).to_be_visible()
        self.page.set_viewport_size({"width": 390, "height": 844})
        fields = self.page.locator(".case-mobile-fields").first
        expect(fields.locator("dt").first).to_have_css("font-size", "14px")
        fields.get_by_role("link", name=self.ticket.number, exact=True).click()
        expect(back).to_be_visible()
        self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
        back.click()
        expect(self.page.get_by_role("heading", name="案件總覽", exact=True)).to_be_visible()


    def test_system_settings_permissions_hinet_and_masked_password(self):
        from cryptography.fernet import Fernet
        from apps.notifications.models import SystemSettings, Delivery
        with override_settings(SETTINGS_ENCRYPTION_KEY=Fernet.generate_key().decode(), EMAIL_HOST_PASSWORD="", EMAIL_HOST_USER="", DEFAULT_FROM_EMAIL="test@example.com"):
            self.login("admin")
            nav = self.page.get_by_role("navigation", name="報修系統入口", exact=True)
            settings_link = nav.get_by_role("link", name="系統設定", exact=True)
            expect(settings_link).to_be_visible()
            toggle = self.page.get_by_role("button", name="報修系統入口", exact=True)
            toggle.click()
            expect(settings_link).not_to_be_visible()
            toggle.click()
            settings_link.click()
            expect(settings_link).to_have_attribute("aria-current", "page")
            expect(self.page.locator(".breadcrumb")).to_contain_text("報修系統入口")
            expect(self.page.locator(".breadcrumb strong")).to_have_text("系統設定")
            self.page.get_by_label("平台名稱", exact=True).fill("驗收服務平台")
            self.page.get_by_role("button", name="儲存基本資料", exact=True).click()
            expect(self.page.locator(".brand")).to_contain_text("驗收服務平台")
            self.page.get_by_role("button", name="套用 HiNet", exact=True).click()
            expect(self.page.get_by_label("SMTP 主機", exact=True)).to_have_value("msr.hinet.net")
            expect(self.page.get_by_label("連接埠", exact=True)).to_have_value("587")
            expect(self.page.get_by_label("加密方式", exact=True)).to_have_value("starttls")
            self.page.get_by_label("寄件信箱", exact=True).fill("smtp@example.com")
            self.page.get_by_label("SMTP 帳號", exact=True).fill("smtp@example.com")
            self.page.get_by_label("新的 SMTP 密碼", exact=True).fill("Browser-test-only-secret!")
            self.page.get_by_role("button", name="儲存寄信設定", exact=True).click()
            expect(self.page.get_by_role("button", name="更換密碼", exact=True)).to_be_visible()
            expect(self.page.locator('input[type="password"]')).to_have_count(0)
            self.page.reload()
            expect(self.page.get_by_role("button", name="更換密碼", exact=True)).to_be_visible()
            self.page.get_by_label("測試收件信箱", exact=True).fill("test@example.com")
            self.page.get_by_role("button", name="寄送測試信", exact=True).click()
            expect(self.page.get_by_text("排隊或重試中", exact=False)).to_be_visible()
            self.assertTrue(self.db(lambda: Delivery.objects.filter(is_test=True, recipient="test@example.com").exists()))
            self.page.set_viewport_size({"width": 390, "height": 844})
            self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
            self.page.screenshot(path=str(SHOTS / "system-settings-mobile.png"), full_page=True, animations="disabled")
            self.page.set_viewport_size({"width": 1440, "height": 900})
            self.page.get_by_role("button", name="登出系統", exact=True).click()
            self.login("reporter")
            expect(self.page.get_by_role("link", name="系統設定", exact=True)).to_have_count(0)
            self.page.goto(self.live_server_url + "/settings/system/")
            expect(self.page.get_by_role("heading", name="案件總覽", exact=True)).to_be_visible()
            self.assertEqual(self.db(lambda: SystemSettings.objects.get().platform_name), "驗收服務平台")


    def test_status_cards_choices_and_customer_waiting_presentation(self):
        from apps.tickets.models import Ticket
        def prepare():
            for status in ("processing", "waiting", "completed", "cancelled"):
                Ticket.objects.create(number="BROWSER-" + status, company=self.company,
                    reporter=self.reporter, created_by=self.reporter, form_version=self.version,
                    title="status case", description="fixture", status=status, engineer=self.admin)
        self.db(prepare)
        self.login("admin")
        expect(self.page.locator(".stat-card > div > span")).to_have_text(["處理中", "待客戶回覆", "已完成", "已取消"])
        expect(self.page.locator('select[aria-label="案件狀態"] option')).to_have_text(["全部狀態", "處理中", "待客戶回覆", "已完成", "已取消"])
        expect(self.page.locator(".stat-card strong")).to_have_text(["2", "1", "1", "1"])
        self.page.screenshot(path=str(SHOTS / "staff-status-cards.png"), full_page=True, animations="disabled")
        self.page.get_by_role("button", name="登出系統", exact=True).click()
        for username in ("reporter", "manager"):
            self.login(username)
            expect(self.page.locator(".stat-card > div > span")).to_have_text(["處理中", "已完成", "已取消"])
            expect(self.page.locator(".stat-card strong")).to_have_text(["3", "1", "1"])
            expect(self.page.locator('select[aria-label="案件狀態"] option')).to_have_text(["全部狀態", "處理中", "已完成", "已取消"])
            widths = self.page.locator(".stat-card").evaluate_all("cards => cards.map(card => card.getBoundingClientRect().width)")
            self.assertAlmostEqual(widths[0], widths[1], delta=1)
            self.assertAlmostEqual(widths[0], widths[2], delta=1)
            self.page.get_by_label("案件狀態", exact=True).select_option("processing")
            self.page.get_by_role("button", name="查詢", exact=True).click()
            expect(self.page.locator(".case-table tbody tr")).to_have_count(3)
            expect(self.page.locator(".case-table .status")).to_have_text(["處理中"] * 3)
            self.page.get_by_role("link", name="BROWSER-waiting", exact=True).click()
            expect(self.page.locator(".heading-actions .status")).to_have_text("處理中")
            self.page.get_by_role("link", name="返回案件總覽", exact=True).click()
            self.page.screenshot(path=str(SHOTS / "customer-status-cards.png"), full_page=True, animations="disabled")
            self.page.set_viewport_size({"width": 390, "height": 844})
            expect(self.page.locator(".stat-card")).to_have_count(3)
            self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
            self.page.set_viewport_size({"width": 1440, "height": 900})
            self.page.get_by_role("button", name="登出系統", exact=True).click()


    def test_company_manager_account_lifecycle_and_employee_first_login(self):
        self.login("manager")
        self.page.goto(self.live_server_url + "/users/")
        self.page.get_by_role("button", name="新增帳號", exact=True).click()
        expect(self.page.locator('select[name="role"]')).to_have_count(0)
        expect(self.page.locator('select[name="company"]')).to_have_count(0)
        self.page.locator('[name="username"]').fill("manager.worker")
        self.page.locator('[name="display_name"]').fill("公司員工")
        self.page.get_by_role("button", name="儲存帳號", exact=True).click()
        expect(self.page.get_by_role("heading", name="帳號已準備完成", exact=True)).to_be_visible()
        raw = self.page.locator(".credential.secret").inner_text()
        self.page.get_by_role("button", name="已記錄，完成", exact=True).click()
        row = self.page.locator("tbody tr").filter(has_text="manager.worker")
        expect(row).to_contain_text("公司報修者")
        self.page.get_by_role("button", name="登出系統", exact=True).click()
        self.login("manager.worker", raw)
        expect(self.page.get_by_role("heading", name="設定個人密碼", exact=True)).to_be_visible()
        self.page.locator('[name="password"]').fill(raw)
        self.page.locator('[name="new_password1"]').fill(PASSWORD)
        self.page.locator('[name="new_password2"]').fill(PASSWORD)
        self.page.get_by_role("button", name="設定密碼並繼續", exact=True).click()
        expect(self.page.get_by_role("heading", name="案件總覽", exact=True)).to_be_visible()
        self.page.get_by_role("button", name="登出系統", exact=True).click()
        self.login("manager")
        self.page.goto(self.live_server_url + "/users/")
        row.get_by_role("button", name="修改資料", exact=True).click()
        expect(self.page.locator('[name="username"]')).to_be_disabled()
        self.page.get_by_role("button", name="關閉", exact=True).click()
        self.page.on("dialog", lambda dialog: dialog.accept())
        for label in ("重設臨時密碼", "停用帳號", "啟用帳號", "刪除帳號"):
            if not row.get_by_role("button", name=label, exact=True).is_visible():
                row.locator("summary").click()
            row.get_by_role("button", name=label, exact=True).click()
            if label == "重設臨時密碼":
                expect(self.page.get_by_role("heading", name="帳號已準備完成", exact=True)).to_be_visible()
                self.page.get_by_role("button", name="已記錄，完成", exact=True).click()
            elif label == "停用帳號":
                expect(row.locator(".status")).to_have_text("停用")
            elif label == "啟用帳號":
                expect(row.locator(".status")).to_have_text("啟用")
            else:
                expect(row).to_have_count(0)

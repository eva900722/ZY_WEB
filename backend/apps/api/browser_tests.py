"""Browser acceptance limited to the Vue/PWA migration; all data goes to test_zy_web."""

import io, os, tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.utils import timezone
from django.db import connections
from playwright.sync_api import sync_playwright, expect
from apps.accounts.models import User
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
        self.engineer = u("engineer", "engineer")
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
        expect(self.page.get_by_role("heading", name="登入資訊管家")).to_be_visible()
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
        expect(self.page.get_by_role("heading", name="登入資訊管家")).to_be_visible()
        self.page.screenshot(
            path=str(SHOTS / "login-mobile.png"), full_page=True, animations="disabled"
        )

    def test_reporter_create_attachment_and_download(self):
        self.login()
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
        self.assertEqual(download.value.suggested_filename, "maintenance.xlsx")
        self.page.screenshot(
            path=str(SHOTS / "ticket-detail.png"), full_page=True, animations="disabled"
        )

    def test_assign_and_engineer_status(self):
        self.login("admin")
        self.page.goto(self.live_server_url + f"/tickets/{self.ticket.pk}/")
        self.page.locator("[name=engineer]").select_option(str(self.engineer.pk))
        self.page.locator("[name=assignment_reason]").fill("安排遠端檢查")
        self.page.get_by_role("button", name="確認指派", exact=True).click()
        self.page.get_by_role("button", name="登出系統", exact=True).click()
        self.login("engineer")
        self.page.get_by_role("link", name=self.ticket.title, exact=True).first.click()
        self.page.locator("[name=status]").select_option("processing")
        self.page.locator("[name=reason]").fill("已開始排查列印服務")
        self.page.get_by_role("button", name="更新狀態", exact=True).click()
        expect(self.page.locator(".heading-actions .status")).to_have_text("處理中")

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
        self.page.goto(self.live_server_url + "/audit/")
        expect(self.page.get_by_role("heading", name="操作紀錄")).to_be_visible()
        self.page.get_by_role("button", name="登出系統", exact=True).click()
        self.login("manager")
        self.assertEqual(
            self.page.get_by_role("link", name="公司管理", exact=True).count(), 0
        )
        self.page.goto(self.live_server_url + "/users/")
        self.assertEqual(
            self.page.get_by_role("button", name="新增帳號", exact=True).count(), 0
        )

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
            self.page.get_by_text(self.ticket.title, exact=True).count(), 0
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

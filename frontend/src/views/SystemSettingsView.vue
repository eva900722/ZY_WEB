<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount } from "vue";
import { api, post, errorText, dateText } from "../api";
import { useAuth } from "../stores/auth";
import { useUi } from "../stores/ui";
import PageHeading from "../components/PageHeading.vue";
import FieldErrors from "../components/FieldErrors.vue";
const auth = useAuth(),
  ui = useUi();
const data = reactive({
  platform_name: "",
  company_name: "",
  contact_phone: "",
  contact_email: "",
  smtp_host: "",
  smtp_port: 587,
  smtp_security: "starttls",
  smtp_auth: true,
  smtp_username: "",
  sender_email: "",
  sender_name: "",
  password_set: false,
  smtp_override: false,
  revision: 0,
});
const password = ref(""),
  changingPassword = ref(false),
  recipient = ref(""),
  error = ref(""),
  busy = ref(false),
  loading = ref(true),
  testResult = ref<any>(null),
  testBusy = ref(false),
  basicDirty = ref(false),
  mailDirty = ref(false);
let timer: ReturnType<typeof setInterval> | undefined;
function dirty(section: string) {
  if (section === "basic") basicDirty.value = true;
  else mailDirty.value = true;
  ui.dirty = true;
}
async function load() {
  try {
    Object.assign(data, await api("system-settings/"));
  } catch (e) {
    error.value = errorText(e);
  } finally {
    loading.value = false;
  }
}
function hinet() {
  Object.assign(data, {
    smtp_host: "msr.hinet.net",
    smtp_port: 587,
    smtp_security: "starttls",
    smtp_auth: true,
  });
  dirty("mail");
}
async function save(section: string) {
  busy.value = true;
  error.value = "";
  try {
    const fields =
      section === "basic"
        ? ["platform_name", "company_name", "contact_phone", "contact_email"]
        : [
            "smtp_host",
            "smtp_port",
            "smtp_security",
            "smtp_auth",
            "smtp_username",
            "sender_email",
            "sender_name",
          ];
    const payload: Record<string, any> = { section, revision: data.revision };
    for (const key of fields) payload[key] = data[key as keyof typeof data];
    if (section === "mail") payload.smtp_password = password.value;
    const result = await post("system-settings/", payload);
    for (const key of fields) (data as any)[key] = result[key];
    data.revision = result.revision;
    if (section === "basic") {
      basicDirty.value = false;
      await auth.load();
    } else {
      mailDirty.value = false;
      password.value = "";
      changingPassword.value = false;
      data.password_set = result.password_set;
      data.smtp_override = result.smtp_override;
    }
    ui.dirty = basicDirty.value || mailDirty.value;
    ui.notify(
      section === "basic"
        ? "平台基本資料已儲存"
        : "SMTP 設定已儲存，後續寄信將使用新設定",
    );
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
async function poll() {
  if (!testResult.value || testResult.value.status !== "pending") return;
  try {
    testResult.value = await api(
      "system-settings/test-mail/" + testResult.value.id + "/",
    );
    if (testResult.value.status !== "pending") clearInterval(timer);
  } catch (e) {
    error.value = errorText(e);
    clearInterval(timer);
  }
}
async function sendTest() {
  testBusy.value = true;
  error.value = "";
  try {
    clearInterval(timer);
    testResult.value = await post("system-settings/test-mail/", {
      recipient: recipient.value,
    });
    timer = setInterval(poll, 3000);
  } catch (e) {
    error.value = errorText(e);
  } finally {
    testBusy.value = false;
  }
}
onMounted(load);
onBeforeUnmount(() => {
  clearInterval(timer);
  password.value = "";
});
</script>
<template>
  <PageHeading title="系統設定" subtitle="設定平台基本資料與寄信服務。" />
  <FieldErrors :message="error" />
  <div v-if="loading" class="loading-state">載入設定中…</div>
  <div v-else class="settings-sections">
    <form class="panel" @submit.prevent="save('basic')" @input="dirty('basic')">
      <h2>平台基本資料</h2>
      <div class="form-grid">
        <label
          >平台名稱<input v-model="data.platform_name" maxlength="60" required
        /></label>
        <label
          >公司名稱<input v-model="data.company_name" maxlength="100" required
        /></label>
        <label
          >聯絡電話<input v-model="data.contact_phone" maxlength="50"
        /></label>
        <label
          >客服 Email<input
            v-model="data.contact_email"
            type="email"
            maxlength="254"
        /></label>
      </div>
      <button class="btn primary" :disabled="busy">儲存基本資料</button>
    </form>
    <form
      class="panel"
      @submit.prevent="save('mail')"
      @input="dirty('mail')"
      @change="dirty('mail')"
    >
      <div class="row between wrap">
        <h2>寄信設定</h2>
        <button class="btn secondary" type="button" @click="hinet">
          套用 HiNet
        </button>
      </div>
      <p class="muted">
        {{
          data.smtp_override
            ? "目前使用此頁儲存的 SMTP 設定。"
            : "目前沿用部署環境設定，儲存後改用此頁設定。"
        }}
      </p>
      <div class="form-grid">
        <label
          >SMTP 主機<input
            v-model="data.smtp_host"
            maxlength="253"
            required
            placeholder="msr.hinet.net"
        /></label>
        <label
          >連接埠<input
            v-model.number="data.smtp_port"
            type="number"
            min="1"
            max="65535"
            required
        /></label>
        <label
          >加密方式<select v-model="data.smtp_security" aria-label="加密方式">
            <option value="starttls">STARTTLS</option>
            <option value="ssl">SSL/TLS</option>
            <option value="none">無加密</option>
          </select></label
        >
        <label
          >寄件者名稱<input v-model="data.sender_name" maxlength="100"
        /></label>
        <label
          >寄件信箱<input
            v-model="data.sender_email"
            type="email"
            maxlength="254"
            required
        /></label>
      </div>
      <label class="checkbox-label"
        ><input v-model="data.smtp_auth" type="checkbox" />SMTP
        需要帳號密碼驗證</label
      >
      <template v-if="data.smtp_auth">
        <label
          >SMTP 帳號<input
            v-model="data.smtp_username"
            maxlength="254"
            autocomplete="off"
            required
        /></label>
        <div class="row wrap password-status">
          <span
            >SMTP 密碼 · {{ data.password_set ? "已設定" : "尚未設定" }}</span
          >
          <button
            v-if="data.password_set && !changingPassword"
            type="button"
            class="btn secondary small"
            @click="changingPassword = true"
          >
            更換密碼
          </button>
        </div>
        <label v-if="!data.password_set || changingPassword"
          >新的 SMTP 密碼<input
            v-model="password"
            type="password"
            maxlength="1024"
            autocomplete="new-password"
            :required="!data.password_set"
            placeholder="留空保留既有密碼"
        /></label>
      </template>
      <p v-if="data.smtp_security === 'none'" class="text-error">
        此連線不會加密，請確認郵件伺服器的要求。
      </p>
      <button class="btn primary" :disabled="busy">儲存寄信設定</button>
    </form>
    <form class="panel" @submit.prevent="sendTest">
      <h2>測試寄信</h2>
      <p class="muted">
        先儲存寄信設定。測試信由寄信 worker 處理，請保持 worker 執行。
      </p>
      <label
        >測試收件信箱<input
          v-model="recipient"
          type="email"
          maxlength="254"
          required
      /></label>
      <button
        class="btn secondary"
        :disabled="
          busy ||
          testBusy ||
          mailDirty ||
          !data.smtp_override ||
          testResult?.status === 'pending'
        "
      >
        寄送測試信
      </button>
      <div v-if="testResult" class="test-result" role="status">
        <p v-if="testResult.status === 'sent'">
          SMTP 已接受寄送 ·
          {{ dateText(testResult.sent_at) }}，請至收件信箱確認。
        </p>
        <p v-else-if="testResult.status === 'failed'">
          寄送失敗，請確認寄信設定後重試。
        </p>
        <p v-else>
          排隊或重試中，已嘗試
          {{ testResult.attempts || 0 }} 次。若持續未處理，請確認 worker
          已啟動。
        </p>
        <p v-if="testResult.last_error" class="text-error">
          錯誤類型 · {{ testResult.last_error }}
        </p>
        <button
          v-if="testResult.status === 'pending'"
          class="btn ghost small"
          type="button"
          @click="poll"
        >
          更新狀態
        </button>
      </div>
    </form>
  </div>
</template>
<style scoped>
.settings-sections {
  display: grid;
  gap: 24px;
  max-width: 1000px;
}
.settings-sections > .panel {
  padding: 24px;
  margin-bottom: 0;
}
.panel > .row,
.panel > p,
.panel > .btn {
  margin-left: 0;
  margin-right: 0;
}
.panel > .row,
.panel > p {
  margin-top: 0;
}
.panel > .btn {
  margin-bottom: 0;
}
h2 {
  margin-bottom: 16px;
  font-size: 18px;
}
.row h2 {
  margin-bottom: 0;
}
.panel > .btn {
  margin-top: 16px;
}
.password-status {
  margin: 16px 0;
}
.test-result {
  margin-top: 18px;
  overflow-wrap: anywhere;
}
@media (max-width: 600px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>

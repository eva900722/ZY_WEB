<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, reactive } from "vue";
import { useRouter, RouterLink } from "vue-router";
import { ArrowLeft, Send, Info, RefreshCw } from "@lucide/vue";
import { api, post, errorText } from "../api";
import { useAuth } from "../stores/auth";
import { useUi } from "../stores/ui";
import PageHeading from "../components/PageHeading.vue";
import FieldErrors from "../components/FieldErrors.vue";
import AttachmentPicker from "../components/AttachmentPicker.vue";
type Field = {
  key: string;
  label: string;
  type: string;
  required?: boolean;
  options?: string[];
};
const auth = useAuth(),
  ui = useUi(),
  router = useRouter(),
  meta = ref<any>({ companies: [], reporters: [], version: null }),
  company = ref(""),
  schema = ref<any>(null),
  newSchema = ref<any>(null),
  oldAccepted = ref(true),
  values = reactive<Record<string, string>>({}),
  unmapped = ref<string[][]>([]),
  files = ref<File[]>([]),
  picker = ref<any>(null),
  error = ref(""),
  busy = ref(false),
  loading = ref(true);
const form = reactive({
  title: "",
  description: "",
  office: auth.user?.office || "",
  anydesk: "",
  reporter: "",
});
let timer: ReturnType<typeof setInterval>;
async function load() {
  loading.value = true;
  error.value = "";
  try {
    const d = await api(
      "tickets/meta/" + (company.value ? "?company=" + company.value : ""),
    );
    meta.value = d;
    if (d.company) company.value = String(d.company);
    schema.value = d.version;
    newSchema.value = null;
    oldAccepted.value = true;
    form.reporter = d.reporters.some((u: any) => u.id === auth.user?.id)
      ? String(auth.user?.id)
      : "";
  } catch (e) {
    error.value = errorText(e);
  } finally {
    loading.value = false;
  }
}
async function changeCompany() {
  if (ui.dirty && !confirm("切換公司將清除目前報修內容，確定繼續？")) {
    company.value = String(meta.value.company || "");
    return;
  }
  ui.dirty = false;
  form.title = "";
  form.description = "";
  form.reporter = "";
  files.value = [];
  unmapped.value = [];
  for (const k of Object.keys(values)) delete values[k];
  await load();
}
async function checkVersion() {
  if (!company.value || !schema.value || !navigator.onLine) return;
  try {
    const d = await api(
      "tickets/meta/?company=" + company.value + "&version=" + schema.value.id,
    );
    if (d.version?.id !== schema.value.id) {
      newSchema.value = d.version;
      oldAccepted.value = d.accepted !== false;
    }
  } catch {
    /* Final submit always checks the active policy. */
  }
}
function switchVersion() {
  if (!newSchema.value) return;
  for (const old of schema.value.fields as Field[]) {
    const next = newSchema.value.fields.find((f: Field) => f.key === old.key);
    const value = values[old.key];
    if (
      value &&
      (!next ||
        next.type !== old.type ||
        (next.type === "select" && !next.options.includes(value)))
    ) {
      unmapped.value.push([old.label, value]);
      delete values[old.key];
    }
  }
  schema.value = newSchema.value;
  newSchema.value = null;
  oldAccepted.value = true;
  ui.dirty = true;
  ui.notify("已切換新版，請確認新增或變更的欄位；原附件保留。");
}
async function submit() {
  busy.value = true;
  error.value = "";
  try {
    const body = new FormData();
    for (const [key, value] of Object.entries(form)) body.append(key, value);
    body.append("company", company.value);
    body.append("form_version", String(schema.value.id));
    body.append("unmapped", JSON.stringify(unmapped.value));
    for (const field of schema.value.fields as Field[])
      body.append("field_" + field.key, values[field.key] || "");
    files.value.forEach((f) => body.append("attachments", f));
    const d = await post("tickets/", body);
    ui.dirty = false;
    ui.notify("報修已建立，將安排處理。");
    await router.push("/tickets/" + d.id + "/");
  } catch (e: any) {
    error.value = errorText(e);
    if (e.status === 409) await checkVersion();
  } finally {
    busy.value = false;
  }
}
function visible() {
  if (!document.hidden) checkVersion();
}
onMounted(async () => {
  await load();
  timer = setInterval(checkVersion, 20000);
  document.addEventListener("visibilitychange", visible);
});
onBeforeUnmount(() => {
  clearInterval(timer);
  document.removeEventListener("visibilitychange", visible);
});
</script>
<template>
  <PageHeading title="新增報修" subtitle="描述遇到的問題，讓我們更快協助您。"
    ><RouterLink to="/" class="btn ghost"
      ><ArrowLeft :size="16" />返回案件</RouterLink
    ></PageHeading
  ><FieldErrors :message="error" />
  <div v-if="loading" class="loading-state">載入報修表單…</div>
  <template v-else
    ><section v-if="auth.isAdmin" class="panel compact">
      <label
        >報修公司<select v-model="company" @change="changeCompany">
          <option value="">請選擇公司</option>
          <option v-for="c in meta.companies" :value="String(c.id)">
            {{ c.name }}
          </option>
        </select></label
      >
    </section>
    <form
      v-if="schema"
      @submit.prevent="submit"
      @input="ui.dirty = true"
      @change="ui.dirty = true"
      @paste="picker?.paste($event)"
      class="ticket-create-grid"
    >
      <section class="panel">
        <div class="panel-heading">
          <div>
            <h2>問題資訊</h2>
            <p class="muted">帶有 * 的欄位為必填</p>
          </div>
          <span class="version-chip">表單 V{{ schema.number }}</span>
        </div>
        <div v-if="newSchema" class="alert warning version-alert">
          <Info :size="19" />
          <div>
            <strong>報修表單已有新版</strong>
            <p>
              {{
                oldAccepted
                  ? "目前版本仍可送出，也可保留內容切換新版。"
                  : "此版本已停止接受，請切換新版並補填。"
              }}
            </p>
            <button
              type="button"
              class="btn secondary small"
              @click="switchVersion"
            >
              <RefreshCw :size="14" />保留內容並切換新版
            </button>
          </div>
        </div>
        <div class="form-section">
          <label
            >問題摘要 *<input
              v-model="form.title"
              name="title"
              maxlength="200"
              placeholder="例如：辦公室印表機無法列印"
              required /></label
          ><label
            >問題描述 *<textarea
              v-model="form.description"
              name="description"
              rows="6"
              maxlength="20000"
              placeholder="請說明發生時間、操作步驟與錯誤訊息…"
              required
            ></textarea>
          </label>
          <div class="form-grid">
            <label
              >辦公室／位置<input
                v-model="form.office"
                list="office-options"
                maxlength="100"
                placeholder="設備所在位置" /><datalist id="office-options">
                <option
                  v-for="location in meta.locations"
                  :value="location"
                /></datalist></label
            ><label
              >AnyDesk ID<input
                v-model="form.anydesk"
                maxlength="50"
                placeholder="需要遠端協助時填寫"
            /></label>
          </div>
          <template v-for="field in schema.fields" :key="field.key"
            ><label
              >{{ field.label }}{{ field.required ? " *" : ""
              }}<select
                v-if="field.type === 'select'"
                v-model="values[field.key]"
                :name="'field_' + field.key"
                :required="field.required"
              >
                <option value="">請選擇</option>
                <option v-for="option in field.options" :value="option">
                  {{ option }}
                </option></select
              ><textarea
                v-else-if="field.type === 'textarea'"
                v-model="values[field.key]"
                :name="'field_' + field.key"
                :required="field.required"
                rows="3"
                maxlength="10000"
              ></textarea
              ><input
                v-else
                v-model="values[field.key]"
                :name="'field_' + field.key"
                :type="
                  field.type === 'number'
                    ? 'number'
                    : field.type === 'date'
                      ? 'date'
                      : 'text'
                "
                :step="field.type === 'number' ? 'any' : undefined"
                :required="field.required"
                maxlength="500" /></label
          ></template>
          <div v-if="unmapped.length" class="alert warning">
            <strong>舊版保留內容</strong>
            <p v-for="item in unmapped">{{ item[0] }}：{{ item[1] }}</p>
            <small>會隨案件保存，請確認是否需要補充說明。</small>
          </div>
        </div>
        <div class="form-section border-top">
          <h3>圖片與附件</h3>
          <p class="muted">錯誤畫面或照片，有助於工程師判斷問題。</p>
          <AttachmentPicker ref="picker" v-model="files" />
        </div>
        <div class="panel-footer">
          <span class="muted">送出後可在案件頁補充說明</span
          ><button class="btn primary" :disabled="busy || !oldAccepted">
            <Send :size="16" />{{ busy ? "正在送出…" : "送出報修" }}
          </button>
        </div>
      </section>
      <aside class="ticket-context">
        <section class="panel">
          <h3>報修人資訊</h3>
          <label
            >報修人 *<select
              v-model="form.reporter"
              name="reporter"
              :disabled="auth.user?.role === 'reporter'"
              required
            >
              <option value="">請選擇報修人</option>
              <option v-for="u in meta.reporters" :value="String(u.id)">
                {{ u.name }}
              </option>
            </select></label
          >
          <p class="muted">基本聯絡資料會依帳號帶入，並保存送出當時的紀錄。</p>
        </section>
        <section class="help-panel">
          <Info :size="19" />
          <h3>提供完整資訊，更快處理</h3>
          <p>
            請避免在問題描述或截圖中包含密碼。若尚未設定Email，可登入網站查看維修進度。
          </p>
        </section>
      </aside>
    </form>
    <section v-else-if="company" class="panel empty-state">
      <h3>公司尚未發布報修表單</h3>
      <p>請聯絡資訊公司管理者。</p>
    </section></template
  >
</template>

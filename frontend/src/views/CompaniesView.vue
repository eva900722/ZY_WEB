<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { Plus, Building2, ArrowUpRight, X, Users } from "@lucide/vue";
import { api, post, errorText } from "../api";
import { useUi } from "../stores/ui";
import PageHeading from "../components/PageHeading.vue";
import FieldErrors from "../components/FieldErrors.vue";
const ui = useUi(),
  rows = ref<any[]>([]),
  error = ref(""),
  modal = ref(false),
  editing = ref<number | null>(null),
  busy = ref(false);
const form = reactive({
  name: "",
  code: "",
  contact: "",
  is_active: true,
  locations: "",
  emails: "",
});
async function load() {
  try {
    rows.value = (await api("companies/")).items;
  } catch (e) {
    error.value = errorText(e);
  }
}
function edit(c?: any) {
  editing.value = c?.id || null;
  Object.assign(form, {
    name: c?.name || "",
    code: c?.code || "",
    contact: c?.contact || "",
    is_active: c?.is_active ?? true,
    locations: c?.locations || "",
    emails: c?.emails || "",
  });
  error.value = "";
  modal.value = true;
}
function close() {
  if (ui.dirty && !confirm("尚未儲存，確定關閉？")) return;
  ui.dirty = false;
  modal.value = false;
  error.value = "";
}
async function save() {
  busy.value = true;
  try {
    await post("companies/" + (editing.value ? editing.value + "/" : ""), form);
    ui.dirty = false;
    modal.value = false;
    ui.notify("公司資料已儲存");
    await load();
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <PageHeading title="公司管理" subtitle="維護客戶公司、服務據點與通知設定。"
    ><button class="btn primary" @click="edit()">
      <Plus :size="17" />新增公司
    </button></PageHeading
  ><FieldErrors v-if="!modal" :message="error" />
  <div class="company-grid">
    <article v-for="c in rows" :key="c.id" class="panel company-card">
      <div class="row between">
        <div class="company-icon"><Building2 :size="23" /></div>
        <span
          class="status"
          :class="c.is_active ? 'status-completed' : 'status-cancelled'"
          ><span></span>{{ c.is_active ? "服務中" : "已停用" }}</span
        >
      </div>
      <h2>{{ c.name }}</h2>
      <p class="muted">公司代碼 · {{ c.code }}</p>
      <p>{{ c.contact || "尚未填寫聯絡資訊" }}</p>
      <div class="company-card-footer">
        <span
          >{{ c.locations ? c.locations.split("\n").length : 0 }} 個據點</span
        ><button class="btn ghost small" @click="edit(c)">
          管理公司<ArrowUpRight :size="15" />
        </button>
      </div>
    </article>
    <div v-if="!rows.length" class="panel empty-state">
      <Building2 :size="32" />
      <h3>先建立第一家公司</h3>
      <p>新增公司後，就能建立管理者與報修者帳號。</p>
    </div>
  </div>
  <div v-if="modal" class="modal-backdrop" @click.self="close">
    <section class="dialog wide">
      <div class="dialog-heading">
        <h2>{{ editing ? "修改公司" : "新增公司" }}</h2>
        <button class="icon-button" aria-label="關閉" @click="close">
          <X :size="20" />
        </button>
      </div>
      <FieldErrors :message="error" />
      <form
        @submit.prevent="save"
        @input="ui.dirty = true"
        @change="ui.dirty = true"
      >
        <div class="form-grid">
          <label
            >公司名稱 *<input
              v-model="form.name"
              name="name"
              required
              maxlength="100" /></label
          ><label
            >公司代碼 *<input
              v-model="form.code"
              name="code"
              required
              maxlength="20"
              placeholder="例如 yf"
          /></label>
        </div>
        <label>聯絡資訊<input v-model="form.contact" maxlength="200" /></label>
        <div class="form-grid">
          <label
            >辦公室／據點<textarea
              v-model="form.locations"
              rows="4"
              placeholder="每行一筆，新增據點不會刪除歷史位置"
            ></textarea></label
          ><label
            >額外通知收件人<textarea
              v-model="form.emails"
              rows="4"
              placeholder="選填，每行一個Email"
            ></textarea>
          </label>
        </div>
        <label class="checkbox-label"
          ><input
            v-model="form.is_active"
            type="checkbox"
          />啟用公司（停用後該公司帳號不能登入）</label
        >
        <div class="dialog-footer">
          <button type="button" class="btn ghost" @click="close">取消</button
          ><button class="btn primary" :disabled="busy">儲存公司</button>
        </div>
      </form>
    </section>
  </div>
</template>

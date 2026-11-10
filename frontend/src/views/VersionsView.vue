<script setup lang="ts">
import { ref, onMounted } from "vue";
import {
  Plus,
  Copy,
  FilePenLine,
  X,
  ArrowUp,
  ArrowDown,
  Trash2,
  Layers,
  Send,
} from "@lucide/vue";
import { api, post, errorText, dateText } from "../api";
import { useUi } from "../stores/ui";
import PageHeading from "../components/PageHeading.vue";
import FieldErrors from "../components/FieldErrors.vue";
const ui = useUi(),
  data = ref<any>({ items: [], companies: [] }),
  error = ref(""),
  modal = ref(false),
  editing = ref<number | null>(null),
  company = ref(""),
  fields = ref<any[]>([]),
  policy = ref("grace"),
  busy = ref(false);
async function load() {
  try {
    data.value = await api("versions/");
  } catch (e) {
    error.value = errorText(e);
  }
}
function edit(v?: any, copy = false) {
  editing.value = v && !copy ? v.id : null;
  company.value = v ? String(v.company) : "";
  fields.value = v ? JSON.parse(JSON.stringify(v.fields)) : [];
  modal.value = true;
  error.value = "";
}
function add() {
  if (fields.value.length >= 40) {
    ui.notify("最多40個欄位", "error");
    return;
  }
  fields.value.push({
    key: "field_" + Date.now(),
    label: "",
    type: "text",
    required: false,
    options: [],
  });
  ui.dirty = true;
}
function move(i: number, delta: number) {
  const next = i + delta;
  if (next < 0 || next >= fields.value.length) return;
  [fields.value[i], fields.value[next]] = [fields.value[next], fields.value[i]];
  ui.dirty = true;
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
    await post("versions/" + (editing.value ? editing.value + "/" : ""), {
      company: company.value,
      fields: fields.value,
    });
    ui.dirty = false;
    modal.value = false;
    ui.notify("草稿已儲存，發布後使用者才會看到。");
    await load();
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
async function publish(v: any) {
  if (
    !confirm(
      policy.value === "immediate"
        ? "發布後立即停止接受所有舊版，確定繼續？"
        : "發布新版，舊版再接受24小時，確定繼續？",
    )
  )
    return;
  try {
    await post("versions/" + v.id + "/", {
      action: "publish",
      company: v.company,
      policy: policy.value,
    });
    ui.notify("表單已發布");
    await load();
  } catch (e) {
    error.value = errorText(e);
  }
}
onMounted(load);
</script>
<template>
  <PageHeading title="報修表單" subtitle="先儲存草稿，確認欄位後再發布新版。"
    ><button class="btn primary" @click="edit()">
      <Plus :size="17" />建立草稿
    </button></PageHeading
  ><FieldErrors v-if="!modal" :message="error" />
  <section class="panel compact">
    <div class="row wrap between">
      <p class="muted">固定報修資訊保留，以下管理各公司的額外欄位。</p>
      <label class="inline-label"
        >發布政策<select v-model="policy">
          <option value="grace">舊版再接受24小時</option>
          <option value="immediate">立即停止接受所有舊版</option>
        </select></label
      >
    </div>
  </section>
  <div class="version-list">
    <article v-for="v in data.items" :key="v.id" class="panel version-card">
      <div class="row between">
        <div class="row">
          <span class="version-icon"><Layers :size="21" /></span>
          <div>
            <h2>{{ v.company_name }}</h2>
            <small
              >版本 V{{ v.number }} ·
              {{
                v.published_at
                  ? "發布於 " + dateText(v.published_at)
                  : "尚未發布"
              }}</small
            >
          </div>
        </div>
        <span
          class="status"
          :class="v.published_at ? 'status-completed' : 'status-unassigned'"
          ><span></span>{{ v.published_at ? "已發布" : "草稿" }}</span
        >
      </div>
      <div class="field-tags">
        <span v-for="f in v.fields"
          >{{ f.label }}{{ f.required ? " *" : "" }}</span
        ><span v-if="!v.fields.length" class="muted">使用基本報修欄位</span>
      </div>
      <div class="row wrap between">
        <small class="muted">{{
          v.accepts_until
            ? "舊版接受至 " + dateText(v.accepts_until)
            : "發布版本不直接改寫"
        }}</small>
        <div class="row">
          <button
            v-if="!v.published_at"
            class="btn ghost small"
            @click="edit(v)"
          >
            <FilePenLine :size="15" />編輯</button
          ><button class="btn ghost small" @click="edit(v, true)">
            <Copy :size="15" />複製新版</button
          ><button
            v-if="!v.published_at"
            class="btn secondary small"
            @click="publish(v)"
          >
            <Send :size="14" />發布
          </button>
        </div>
      </div>
    </article>
    <section v-if="!data.items.length" class="panel empty-state">
      新增公司後會建立基本表單。
    </section>
  </div>
  <div v-if="modal" class="modal-backdrop" @click.self="close">
    <section class="dialog wide">
      <div class="dialog-heading">
        <div>
          <h2>{{ editing ? "編輯草稿" : "建立新版草稿" }}</h2>
          <p class="muted">同一欄位請沿用代碼，以保留轉版內容。</p>
        </div>
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
        <label
          >所屬公司 *<select v-model="company" required :disabled="!!editing">
            <option value="">請選擇公司</option>
            <option v-for="c in data.companies" :value="String(c.id)">
              {{ c.name }}
            </option>
          </select></label
        >
        <div v-for="(f, i) in fields" :key="i" class="field-editor">
          <div class="row between">
            <strong>欄位 {{ i + 1 }}</strong>
            <div class="row">
              <button
                type="button"
                class="icon-button"
                aria-label="上移欄位"
                @click="move(i, -1)"
              >
                <ArrowUp :size="15" /></button
              ><button
                type="button"
                class="icon-button"
                aria-label="下移欄位"
                @click="move(i, 1)"
              >
                <ArrowDown :size="15" /></button
              ><button
                type="button"
                class="icon-button text-error"
                aria-label="刪除欄位"
                @click="
                  fields.splice(i, 1);
                  ui.dirty = true;
                "
              >
                <Trash2 :size="15" />
              </button>
            </div>
          </div>
          <div class="form-grid">
            <label
              >欄位名稱 *<input
                v-model="f.label"
                required
                maxlength="100" /></label
            ><label
              >欄位代碼 *<input
                v-model="f.key"
                required
                pattern="[a-z][a-z0-9_]{0,39}"
                title="小寫英文字母開頭，搭配數字或底線"
                maxlength="40" /></label
            ><label
              >輸入方式<select v-model="f.type">
                <option value="text">單行文字</option>
                <option value="textarea">多行文字</option>
                <option value="number">數字</option>
                <option value="date">日期</option>
                <option value="select">下拉選單</option>
              </select></label
            ><label class="checkbox-label"
              ><input v-model="f.required" type="checkbox" />必填欄位</label
            >
          </div>
          <label v-if="f.type === 'select'"
            >選項（每行一筆）<textarea
              :value="f.options?.join('\n')"
              @input="
                f.options = ($event.target as HTMLTextAreaElement).value
                  .split('\n')
                  .map((x) => x.trim())
                  .filter(Boolean)
              "
              rows="3"
              required
            ></textarea>
          </label>
        </div>
        <button type="button" class="btn ghost" @click="add">
          <Plus :size="16" />新增欄位
        </button>
        <div class="dialog-footer">
          <button type="button" class="btn ghost" @click="close">取消</button
          ><button class="btn primary" :disabled="busy">儲存草稿</button>
        </div>
      </form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { useRoute, RouterLink } from "vue-router";
import {
  ArrowLeft,
  Download,
  Paperclip,
  Send,
  UserRound,
  Clock3,
  LockKeyhole,
  ChevronDown,
} from "@lucide/vue";
import { api, post, errorText, dateText } from "../api";
import { useAuth } from "../stores/auth";
import { useUi } from "../stores/ui";
import PageHeading from "../components/PageHeading.vue";
import StatusBadge from "../components/StatusBadge.vue";
import FieldErrors from "../components/FieldErrors.vue";
import AttachmentPicker from "../components/AttachmentPicker.vue";
const route = useRoute(),
  auth = useAuth(),
  ui = useUi(),
  ticket = ref<any>(null),
  error = ref(""),
  loading = ref(true),
  busy = ref(false),
  body = ref(""),
  internal = ref(false),
  files = ref<File[]>([]),
  picker = ref<any>(null),
  engineer = ref(""),
  assignmentReason = ref(""),
  status = ref(""),
  reason = ref(""),
  tab = ref("all");
async function load() {
  loading.value = true;
  try {
    ticket.value = await api("tickets/" + route.params.id + "/");
    engineer.value = "";
    status.value = ticket.value.transitions[0]?.value || "";
  } catch (e) {
    error.value = errorText(e);
    ticket.value = null;
  } finally {
    loading.value = false;
  }
}
async function action(kind: string) {
  error.value = "";
  busy.value = true;
  try {
    let data: any = { action: kind, revision: ticket.value.revision };
    if (kind === "entry") {
      const form = new FormData();
      form.append("action", kind);
      form.append("revision", String(ticket.value.revision));
      form.append("body", body.value);
      form.append("internal", internal.value ? "on" : "");
      files.value.forEach((f) => form.append("attachments", f));
      data = form;
    } else if (kind === "assign")
      Object.assign(data, {
        engineer: engineer.value,
        reason: assignmentReason.value,
      });
    else if (kind === "status")
      Object.assign(data, { status: status.value, reason: reason.value });
    ticket.value = await post("tickets/" + route.params.id + "/", data);
    if (kind === "entry") {
      body.value = "";
      files.value = [];
      internal.value = false;
      ui.dirty = false;
    }
    if (kind === "status") reason.value = "";
    if (kind === "assign") assignmentReason.value = "";
    status.value = ticket.value.transitions[0]?.value || "";
    ui.notify("案件已更新");
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
function refresh() {
  if (
    ui.dirty &&
    !confirm("重新載入會保留補充文字，但需重新確認最新案件版本，是否繼續？")
  )
    return;
  load();
}
watch(
  [body, files, reason, assignmentReason],
  () => {
    ui.dirty =
      !!body.value ||
      !!files.value.length ||
      !!reason.value ||
      !!assignmentReason.value;
  },
  { deep: true },
);
onMounted(load);
watch(() => route.params.id, load);
</script>
<template>
  <div class="back-link">
    <RouterLink to="/" class="return-cases"
      ><ArrowLeft :size="16" />返回案件總覽</RouterLink
    >
  </div>
  <FieldErrors :message="error" />
  <div v-if="loading" class="loading-state">載入案件中…</div>
  <template v-else-if="ticket"
    ><PageHeading :title="ticket.title" :subtitle="ticket.number"
      ><StatusBadge :status="ticket.status" :label="ticket.status_label" /><a
        class="btn ghost small"
        :href="'/reports/pdf/' + ticket.id + '/'"
        ><Download :size="15" />PDF</a
      ><a class="btn ghost small" :href="'/reports/xlsx/' + ticket.id + '/'"
        ><Download :size="15" />Excel</a
      ></PageHeading
    >
    <div class="detail-grid">
      <section>
        <section class="panel">
          <div class="panel-heading">
            <h2>報修資訊</h2>
            <span class="version-chip">表單 V{{ ticket.form_version }}</span>
          </div>
          <div class="form-section">
            <p class="preserve description">{{ ticket.description }}</p>
            <dl class="details-list">
              <template
                v-for="[label, value] in [
                  ['公司', ticket.company_name],
                  ['報修人', ticket.snapshot.display_name],
                  ['辦公室', ticket.snapshot.office],
                  ['電話／分機', ticket.snapshot.phone],
                  ['手機', ticket.snapshot.mobile],
                  ['Email', ticket.snapshot.email],
                  ['AnyDesk ID', ticket.anydesk],
                ]"
                ><dt>{{ label }}</dt>
                <dd>{{ value || "未填寫" }}</dd></template
              ><template v-for="answer in ticket.answers"
                ><dt>{{ answer.label }}</dt>
                <dd class="preserve">{{ answer.value || "—" }}</dd></template
              >
            </dl>
          </div>
          <div class="form-section border-top">
            <h3>
              附件 <span class="muted">{{ ticket.attachments.length }}</span>
            </h3>
            <div class="file-list">
              <a
                v-for="file in ticket.attachments"
                :key="file.id"
                :href="file.url"
                ><Paperclip :size="17" /><span
                  >{{ file.name
                  }}<small
                    >{{ Math.ceil(file.size / 1024) }} KB
                    <span v-if="file.internal">· 內部</span></small
                  ></span
                ><Download :size="16"
              /></a>
              <p v-if="!ticket.attachments.length" class="muted">
                此案件尚無附件。
              </p>
            </div>
          </div>
        </section>
        <section class="panel">
          <div class="panel-heading">
            <h2>處理歷程</h2>
            <select
              v-if="ticket.can_internal"
              v-model="tab"
              class="compact-select"
              aria-label="歷程篩選"
            >
              <option value="all">全部紀錄</option>
              <option value="public">公開紀錄</option>
              <option value="internal">內部備註</option>
            </select>
          </div>
          <div class="timeline">
            <article class="timeline-item">
              <div class="timeline-dot"></div>
              <div>
                <div class="timeline-meta">
                  <strong>案件已建立</strong
                  ><time>{{ dateText(ticket.created_at) }}</time>
                </div>
                <p>
                  {{ ticket.reporter_name }} 提交報修，等待贊耀公司人員接手。
                </p>
              </div>
            </article>
            <article
              v-for="entry in ticket.entries.filter(
                (e: any) =>
                  tab === 'all' ||
                  (tab === 'internal' ? e.internal : !e.internal),
              )"
              :key="entry.id"
              class="timeline-item"
              :class="{ internal: entry.internal }"
            >
              <div class="timeline-dot"></div>
              <div>
                <div class="timeline-meta">
                  <strong>{{ entry.author }}</strong
                  ><span class="internal-label" v-if="entry.internal"
                    ><LockKeyhole :size="12" />內部備註</span
                  ><time>{{ dateText(entry.created_at) }}</time>
                </div>
                <p class="preserve">{{ entry.body }}</p>
              </div>
            </article>
          </div>
          <form
            v-if="ticket.can_comment"
            class="comment-form border-top"
            @submit.prevent="action('entry')"
            @paste="picker?.paste($event)"
          >
            <label
              >{{ internal ? "新增內部備註" : "補充說明"
              }}<textarea
                v-model="body"
                name="body"
                rows="4"
                required
                maxlength="20000"
                placeholder="補充問題、回覆或處理紀錄…"
                @input="ui.dirty = !!body || !!files.length"
              ></textarea></label
            ><label v-if="ticket.can_internal" class="checkbox-label"
              ><input v-model="internal" type="checkbox" />僅贊耀公司可見</label
            ><AttachmentPicker ref="picker" v-model="files" /><button
              class="btn primary"
              :disabled="busy"
            >
              <Send :size="16" />送出補充
            </button>
          </form>
          <p v-else class="form-section muted">
            {{
              ticket.can_claim
                ? "請先領取案件，再補充處理紀錄。"
                : "案件已取消，需由贊耀公司人員重新開啟後才能補充。"
            }}
          </p>
        </section>
      </section>
      <aside>
        <section class="panel">
          <h3>服務狀態</h3>
          <div class="service-person">
            <div class="avatar"><UserRound :size="19" /></div>
            <div>
              <small>負責人</small><strong>{{ ticket.engineer_name }}</strong>
            </div>
          </div>
          <div class="row muted">
            <Clock3 :size="15" /><span
              >更新於 {{ dateText(ticket.updated_at) }}</span
            >
          </div>
          <button class="btn ghost small full mt" @click="refresh">
            重新載入最新狀態
          </button>
        </section>
        <section v-if="ticket.can_claim" class="panel">
          <h3>接手案件</h3>
          <p class="muted">
            接手後由你負責處理；其他贊耀公司人員仍可查看及協助。
          </p>
          <button
            class="btn primary full"
            :disabled="busy"
            @click="action('claim')"
          >
            接手處理
          </button>
        </section>
        <section
          v-if="
            auth.isAdmin &&
            !ticket.can_claim &&
            ticket.status !== 'cancelled'
          "
          class="panel"
        >
          <h3>變更負責人</h3>
          <form @submit.prevent="action('assign')">
            <label
              >負責人<select v-model="engineer" required name="engineer">
                <option value="">請選擇贊耀公司人員</option>
                <option v-for="u in ticket.engineers" :value="String(u.id)">
                  {{ u.name }}
                </option>
              </select></label
            ><label
              >交接原因<input
                v-model="assignmentReason"
                name="assignment_reason"
                required
                maxlength="500"
                placeholder="說明本次安排" /></label
            ><button class="btn secondary full" :disabled="busy">
              確認交接
            </button>
          </form>
        </section>
        <section v-if="ticket.transitions.length" class="panel">
          <h3>更新案件狀態</h3>
          <form @submit.prevent="action('status')">
            <label
              >新狀態<select v-model="status" name="status" required>
                <option v-for="s in ticket.transitions" :value="s.value">
                  {{ s.label }}
                </option>
              </select></label
            ><label
              >處理說明<textarea
                v-model="reason"
                name="reason"
                rows="3"
                required
                maxlength="10000"
                placeholder="填寫本次處理結果"
              ></textarea></label
            ><button class="btn primary full" :disabled="busy">更新狀態</button>
          </form>
        </section>
      </aside>
    </div></template
  >
</template>

<style scoped>
.back-link .return-cases {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  padding: 10px 0;
  border: 0;
  background: transparent;
  color: #1d4ed8;
  font-size: 14px;
  font-weight: 650;
  transition: color 150ms ease;
}
.back-link .return-cases:hover {
  color: #1e40af;
  text-decoration: underline;
}
@media (prefers-reduced-motion: reduce) {
  .back-link .return-cases {
    transition: none;
  }
}
</style>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { RouterLink } from "vue-router";
import {
  Plus,
  Search,
  Download,
  ArrowUpRight,
  Inbox,
  Clock3,
  MessageSquare,
  CheckCircle2,
  MailCheck,
} from "@lucide/vue";
import { api, post, errorText, dateText } from "../api";
import { useAuth } from "../stores/auth";
import { useUi } from "../stores/ui";
import PageHeading from "../components/PageHeading.vue";
import StatusBadge from "../components/StatusBadge.vue";
import Pagination from "../components/Pagination.vue";
import FieldErrors from "../components/FieldErrors.vue";
const auth = useAuth(),
  ui = useUi(),
  company = ref(""),
  verifying = ref(false),
  data = ref<any>({
    items: [],
    counts: {},
    statuses: [],
    page: 1,
    pages: 1,
    total: 0,
  }),
  busy = ref(true),
  error = ref(""),
  q = ref(""),
  status = ref(""),
  start = ref(""),
  end = ref("");
function query(page = 1) {
  return new URLSearchParams({
    q: q.value,
    company: company.value,
    status: status.value,
    start: start.value,
    end: end.value,
    page: String(page),
  }).toString();
}
async function load(page = 1) {
  busy.value = true;
  error.value = "";
  try {
    data.value = await api("tickets/?" + query(page));
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
async function verify() {
  verifying.value = true;
  try {
    const d = await post("auth/verify/", {});
    ui.notify(d.message);
  } catch (e) {
    error.value = errorText(e);
  } finally {
    verifying.value = false;
  }
}
onMounted(() => load());
</script>
<template>
  <PageHeading
    title="案件總覽"
    :subtitle="
      auth.isAdmin
        ? '集中掌握各公司的服務需求與處理進度。'
        : auth.isEngineer
          ? '優先處理目前指派給您的維修工作。'
          : '追蹤報修進度，讓工作順利進行。'
    "
    ><RouterLink v-if="!auth.isEngineer" to="/tickets/new/" class="btn primary"
      ><Plus :size="17" />新增報修</RouterLink
    ></PageHeading
  ><FieldErrors :message="error" />
  <div
    v-if="auth.user?.email && !auth.user.email_verified"
    class="email-reminder"
  >
    <MailCheck :size="20" />
    <div>
      <strong>驗證信箱，接收服務通知</strong
      ><small>驗證後也能使用忘記密碼功能。</small>
    </div>
    <button class="btn secondary small" :disabled="verifying" @click="verify">
      {{ verifying ? "處理中…" : "寄送驗證信" }}
    </button>
  </div>
  <div class="stat-grid">
    <div class="stat-card">
      <span class="stat-icon amber"><Inbox :size="20" /></span>
      <div>
        <span>待派工</span><strong>{{ data.counts.unassigned || 0 }}</strong>
      </div>
      <small>等待安排人員</small>
    </div>
    <div class="stat-card">
      <span class="stat-icon blue"><Clock3 :size="20" /></span>
      <div>
        <span>處理中</span
        ><strong>{{
          (data.counts.assigned || 0) + (data.counts.processing || 0)
        }}</strong>
      </div>
      <small>待處理與進行中</small>
    </div>
    <div class="stat-card">
      <span class="stat-icon purple"><MessageSquare :size="20" /></span>
      <div>
        <span>待客戶回覆</span><strong>{{ data.counts.waiting || 0 }}</strong>
      </div>
      <small>等待補充資訊</small>
    </div>
    <div class="stat-card">
      <span class="stat-icon green"><CheckCircle2 :size="20" /></span>
      <div>
        <span>已完成</span><strong>{{ data.counts.completed || 0 }}</strong>
      </div>
      <small>處理完成待確認</small>
    </div>
  </div>
  <section class="panel">
    <div class="panel-heading">
      <div>
        <h2>維修案件</h2>
        <p class="muted">依您目前的權限顯示案件</p>
      </div>
      <div class="row">
        <a class="btn ghost small" :href="'/reports/pdf/?' + query()"
          ><Download :size="15" />PDF</a
        ><a class="btn ghost small" :href="'/reports/xlsx/?' + query()"
          ><Download :size="15" />Excel</a
        >
      </div>
    </div>
    <form class="filter-bar" @submit.prevent="load()">
      <div class="search-input">
        <Search :size="17" /><input
          v-model="q"
          placeholder="搜尋單號或問題摘要"
          aria-label="搜尋案件"
        />
      </div>
      <select v-if="auth.isAdmin" v-model="company" aria-label="篩選公司">
        <option value="">全部公司</option>
        <option v-for="c in data.companies" :value="String(c.id)">
          {{ c.name }}
        </option></select
      ><select v-model="status" aria-label="案件狀態">
        <option value="">全部狀態</option>
        <option v-for="s in data.statuses" :value="s.value">
          {{ s.label }}
        </option></select
      ><input v-model="start" type="date" aria-label="開始日期" /><span
        class="date-separator"
        >—</span
      ><input v-model="end" type="date" aria-label="結束日期" /><button
        class="btn secondary"
        :disabled="busy"
      >
        查詢
      </button>
    </form>
    <div v-if="busy" class="loading-state">
      <span class="spinner"></span>載入案件中…
    </div>
    <template v-else
      ><div v-if="!data.items.length" class="empty-state">
        <div><Inbox :size="30" /></div>
        <h3>目前沒有符合條件的案件</h3>
        <p>試著調整篩選，或建立第一張報修單。</p>
      </div>
      <template v-else
        ><div class="desktop-table table-scroll">
          <table>
            <thead>
              <tr>
                <th>單號／問題</th>
                <th>公司／報修人</th>
                <th>狀態</th>
                <th>負責工程師</th>
                <th>更新時間</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in data.items" :key="t.id">
                <td>
                  <RouterLink
                    :to="'/tickets/' + t.id + '/'"
                    class="ticket-title"
                    >{{ t.title }}</RouterLink
                  ><small class="ticket-number">{{ t.number }}</small>
                </td>
                <td>
                  {{ t.company_name }}<small>{{ t.reporter_name }}</small>
                </td>
                <td>
                  <StatusBadge :status="t.status" :label="t.status_label" />
                </td>
                <td>{{ t.engineer_name }}</td>
                <td class="muted nowrap">{{ dateText(t.updated_at) }}</td>
                <td>
                  <RouterLink
                    :to="'/tickets/' + t.id + '/'"
                    class="icon-button"
                    aria-label="查看案件"
                    ><ArrowUpRight :size="17"
                  /></RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="mobile-ticket-list">
          <RouterLink
            v-for="t in data.items"
            :key="t.id"
            :to="'/tickets/' + t.id + '/'"
            class="mobile-ticket"
            ><div class="row between">
              <small>{{ t.company_name }}</small
              ><StatusBadge :status="t.status" :label="t.status_label" />
            </div>
            <h3>{{ t.title }}</h3>
            <p>{{ t.number }}</p>
            <div class="row between">
              <span>{{ t.engineer_name }}</span
              ><small>{{ dateText(t.updated_at) }}</small>
            </div></RouterLink
          >
        </div></template
      ><Pagination
        :page="data.page"
        :pages="data.pages"
        :total="data.total"
        @change="load"
    /></template>
  </section>
  <p class="page-hint">報表依目前篩選條件匯出，最多1,000件。</p>
</template>

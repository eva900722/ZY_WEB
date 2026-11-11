<script setup lang="ts">
import { ref, onMounted } from "vue";
import { RouterLink } from "vue-router";
import {
  Plus,
  Search,
  Download,
  Inbox,
  Clock3,
  MessageSquare,
  CheckCircle2,
} from "@lucide/vue";
import { api, errorText, dateText } from "../api";
import { useAuth } from "../stores/auth";
import PageHeading from "../components/PageHeading.vue";
import StatusBadge from "../components/StatusBadge.vue";
import Pagination from "../components/Pagination.vue";
import FieldErrors from "../components/FieldErrors.vue";
const auth = useAuth(),
  company = ref(""),
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
onMounted(() => load());
</script>
<template>
  <PageHeading
    title="案件總覽"
    :subtitle="
      auth.isAdmin
        ? '查看全部案件、接手處理或協助同事。'
        : '追蹤報修進度，讓工作順利進行。'
    "
    ><RouterLink v-if="!auth.isAdmin" to="/tickets/new/" class="btn primary"
      ><Plus :size="17" />新增報修</RouterLink
    ></PageHeading
  ><FieldErrors :message="error" />
  <div class="stat-grid">
    <div class="stat-card">
      <span class="stat-icon amber"><Inbox :size="20" /></span>
      <div>
        <span>待接手</span><strong>{{ data.counts.unassigned || 0 }}</strong>
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
          <table class="case-table">
            <colgroup>
              <col class="case-number-column" />
              <col />
              <col class="case-status-column" />
              <col class="case-time-column" />
            </colgroup>
            <thead>
              <tr>
                <th>問題單號</th>
                <th>報修公司</th>
                <th>狀態</th>
                <th>更新時間</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in data.items" :key="t.id">
                <td>
                  <RouterLink
                    :to="'/tickets/' + t.id + '/'"
                    class="case-number-link"
                    >{{ t.number }}</RouterLink
                  >
                </td>
                <td>{{ t.company_name }}</td>
                <td>
                  <StatusBadge :status="t.status" :label="t.status_label" />
                </td>
                <td class="muted nowrap">{{ dateText(t.updated_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="mobile-ticket-list">
          <article v-for="t in data.items" :key="t.id" class="mobile-ticket">
            <dl class="case-mobile-fields">
              <dt>問題單號</dt>
              <dd>
                <RouterLink
                  :to="'/tickets/' + t.id + '/'"
                  class="case-number-link"
                  >{{ t.number }}</RouterLink
                >
              </dd>
              <dt>報修公司</dt>
              <dd>{{ t.company_name }}</dd>
              <dt>狀態</dt>
              <dd>
                <StatusBadge :status="t.status" :label="t.status_label" />
              </dd>
              <dt>更新時間</dt>
              <dd class="muted">{{ dateText(t.updated_at) }}</dd>
            </dl>
          </article>
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

<style scoped>
.case-table {
  table-layout: fixed;
  font-size: 14px;
  color: #334155;
}
.case-table col {
  width: 25%;
}
.case-table th {
  color: #111827;
  font-size: 14px;
  font-weight: 700;
}
.case-table td {
  overflow-wrap: anywhere;
}
.case-table td.muted,
.case-mobile-fields dd.muted {
  color: #475569;
}
.case-table :deep(.status),
.case-mobile-fields :deep(.status) {
  font-size: 12px;
}

.case-number-link {
  display: inline-block;
  max-width: calc(100% / 1.05);
  padding: 4px 0;
  color: var(--primary);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.6;
  overflow-wrap: anywhere;
  cursor: pointer;
  transform-origin: left center;
  transition:
    transform 180ms ease,
    color 180ms ease;
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
}
.case-number-link:focus-visible {
  color: #1d4ed8;
  text-decoration: underline;
}
@media (hover: hover) {
  .case-number-link:hover {
    transform: scale(1.05);
    color: #1d4ed8;
    text-decoration: underline;
  }
  .case-table tbody tr:hover {
    background: #eff6ff;
  }
}
.case-mobile-fields {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  align-items: center;
  gap: 10px 12px;
  margin: 0;
  font-size: 14px;
}
.case-mobile-fields dt {
  color: #111827;
  font-weight: 700;
}
.case-mobile-fields dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.case-mobile-fields .case-number-link {
  min-height: 44px;
  align-content: center;
}
@media (prefers-reduced-motion: reduce) {
  .case-number-link {
    transition: none;
  }
  .case-number-link:hover {
    transform: none;
  }
}
</style>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from "vue";
import { useRoute, RouterLink } from "vue-router";
import { Bell, Check, ScrollText, Search, ArrowUpRight } from "@lucide/vue";
import { api, post, errorText, dateText } from "../api";
import PageHeading from "../components/PageHeading.vue";
import FieldErrors from "../components/FieldErrors.vue";
import Pagination from "../components/Pagination.vue";
const route = useRoute(),
  isAudit = computed(() => route.path.startsWith("/audit")),
  data = ref<any>({ items: [], page: 1, pages: 1, total: 0 }),
  error = ref(""),
  busy = ref(false),
  filters = reactive({
    actor: "",
    company: "",
    action: "",
    result: "",
    start: "",
    end: "",
  });
async function load(page = 1) {
  busy.value = true;
  error.value = "";
  try {
    data.value = await api(
      (isAudit.value ? "audit/" : "notifications/") +
        "?" +
        new URLSearchParams({ ...filters, page: String(page) }),
    );
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
async function read(n: any) {
  try {
    await post("notifications/" + n.id + "/read/", {});
    await load(data.value.page);
  } catch (e) {
    error.value = errorText(e);
  }
}
onMounted(() => load());
watch(
  () => route.path,
  () => {
    Object.assign(filters, {
      actor: "",
      company: "",
      action: "",
      result: "",
      start: "",
      end: "",
    });
    load();
  },
);
</script>
<template>
  <PageHeading
    :title="isAudit ? '操作紀錄' : '通知中心'"
    :subtitle="
      isAudit
        ? '追蹤系統重要操作與資料異動。'
        : '查看案件更新與需要您回覆的事項。'
    "
  /><FieldErrors :message="error" />
  <section class="panel">
    <template v-if="isAudit"
      ><form class="filter-bar audit-filters" @submit.prevent="load()">
        <input
          v-model="filters.actor"
          placeholder="操作者帳號"
          aria-label="操作者"
        /><input
          v-model="filters.company"
          placeholder="公司名稱"
          aria-label="公司"
        /><input
          v-model="filters.action"
          placeholder="操作類型"
          aria-label="操作類型"
        /><select v-model="filters.result" aria-label="結果">
          <option value="">全部結果</option>
          <option value="success">成功</option>
          <option value="failed">失敗</option>
          <option value="denied">拒絕</option></select
        ><input
          v-model="filters.start"
          type="date"
          aria-label="開始日期"
        /><input
          v-model="filters.end"
          type="date"
          aria-label="結束日期"
        /><button class="btn secondary">查詢</button>
      </form>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>時間</th>
              <th>操作者</th>
              <th>公司</th>
              <th>操作／對象</th>
              <th>結果</th>
              <th>異動摘要</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in data.items" :key="item.id">
              <td class="nowrap muted">{{ dateText(item.created_at) }}</td>
              <td>
                {{ item.actor }}<small>{{ item.role }}</small>
              </td>
              <td>{{ item.company_name }}</td>
              <td>
                {{ item.action
                }}<small class="break-word">{{ item.target }}</small>
              </td>
              <td>
                <span
                  class="status"
                  :class="
                    item.result === 'success'
                      ? 'status-completed'
                      : 'status-cancelled'
                  "
                  ><span></span
                  >{{
                    item.result === "success"
                      ? "成功"
                      : item.result === "denied"
                        ? "拒絕"
                        : "失敗"
                  }}</span
                >
              </td>
              <td class="audit-details">
                {{
                  Object.keys(item.details).length
                    ? JSON.stringify(item.details)
                    : "—"
                }}
              </td>
            </tr>
          </tbody>
        </table>
      </div></template
    ><template v-else
      ><article
        v-for="item in data.items"
        :key="item.id"
        class="notification-item"
        :class="{ unread: !item.read_at }"
      >
        <div class="notification-symbol"><Bell :size="20" /></div>
        <div class="notification-body">
          <div class="row between">
            <strong>{{ item.message }}</strong
            ><i v-if="!item.read_at" class="unread-dot"></i>
          </div>
          <p class="muted">{{ dateText(item.created_at) }}</p>
          <div class="row wrap">
            <RouterLink
              v-if="item.ticket_id"
              :to="'/tickets/' + item.ticket_id + '/'"
              class="btn ghost small"
              >查看案件<ArrowUpRight :size="14" /></RouterLink
            ><button
              v-if="!item.read_at"
              class="btn ghost small"
              @click="read(item)"
            >
              <Check :size="14" />標記已讀
            </button>
          </div>
        </div>
      </article></template
    >
    <div v-if="busy" class="loading-state">載入中…</div>
    <div v-else-if="!data.items.length" class="empty-state">
      <Bell v-if="!isAudit" :size="30" /><ScrollText v-else :size="30" />
      <h3>{{ isAudit ? "沒有符合條件的操作紀錄" : "目前沒有新通知" }}</h3>
      <p>有新的案件更新時會顯示在這裡。</p>
    </div>
    <Pagination
      :page="data.page"
      :pages="data.pages"
      :total="data.total"
      @change="load"
    />
  </section>
</template>

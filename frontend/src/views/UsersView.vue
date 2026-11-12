<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import {
  Plus,
  Users,
  MoreHorizontal,
  X,
  KeyRound,
  ShieldCheck,
  Search,
} from "@lucide/vue";
import { api, post, errorText } from "../api";
import { useAuth } from "../stores/auth";
import { useUi } from "../stores/ui";
import PageHeading from "../components/PageHeading.vue";
import FieldErrors from "../components/FieldErrors.vue";
import Pagination from "../components/Pagination.vue";
const auth = useAuth(),
  ui = useUi(),
  data = ref<any>({
    items: [],
    companies: [],
    roles: [],
    page: 1,
    pages: 1,
    total: 0,
  }),
  error = ref(""),
  busy = ref(false),
  modal = ref(false),
  editing = ref<number | null>(null),
  temporary = ref(""),
  tempUsername = ref("");
const form = reactive<any>({
  username: "",
  display_name: "",
  role: "reporter",
  company: "",
  staff_id: "",
  department: "",
  office: "",
  phone: "",
  mobile: "",
  email: "",
});
async function load(page = 1) {
  try {
    data.value = await api("users/?page=" + page);
  } catch (e) {
    error.value = errorText(e);
  }
}
function edit(user?: any) {
  editing.value = user?.id || null;
  for (const k of Object.keys(form)) form[k] = user?.[k] || "";
  form.role = user?.role || "reporter";
  form.company = user?.company_id ? String(user.company_id) : "";
  modal.value = true;
  error.value = "";
}
async function save() {
  busy.value = true;
  error.value = "";
  try {
    const body = {
      ...form,
      company: ["reporter", "company_admin"].includes(form.role)
        ? form.company
        : "",
    };
    const d = await post(
      "users/" + (editing.value ? editing.value + "/" : ""),
      body,
    );
    modal.value = false;
    ui.dirty = false;
    if (d.temporary_password) {
      temporary.value = d.temporary_password;
      tempUsername.value = d.user.username;
    } else ui.notify("帳號資料已儲存");
    await load(data.value.page);
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
async function action(user: any, kind: string) {
  const prompt =
    kind === "temporary"
      ? "原密碼與登入狀態將失效，確定重設臨時密碼？"
      : kind === "delete"
        ? "確定刪除此帳號？歷史案件保留。"
        : kind === "disable"
          ? "確定停用此帳號？重新啟用後需再重設密碼。"
          : "確定啟用此帳號？";
  if (!confirm(prompt)) return;
  try {
    const d = await post("users/" + user.id + "/action/", { action: kind });
    if (d.temporary_password) {
      temporary.value = d.temporary_password;
      tempUsername.value = user.username;
    } else ui.notify(d.message);
    await load(data.value.page);
  } catch (e) {
    error.value = errorText(e);
  }
}
function close() {
  if (ui.dirty && !confirm("尚未儲存，確定關閉？")) return;
  modal.value = false;
  ui.dirty = false;
  error.value = "";
}
onMounted(() => load());
</script>
<template>
  <PageHeading
    title="帳號管理"
    :subtitle="
      auth.isAdmin
        ? '管理系統成員、角色與帳號使用狀態。'
        : '管理本公司報修者的帳號、聯絡資料與使用狀態。'
    "
    ><button v-if="auth.isManager" class="btn primary" @click="edit()">
      <Plus :size="17" />新增帳號
    </button></PageHeading
  ><FieldErrors v-if="!modal" :message="error" />
  <section class="panel">
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>帳號／姓名</th>
            <th>公司</th>
            <th>角色</th>
            <th>狀態</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in data.items" :key="u.id">
            <td>
              <div class="person-cell">
                <span class="avatar">{{ u.display_name.slice(0, 1) }}</span>
                <div>
                  <strong>{{ u.display_name }}</strong
                  ><small>{{ u.username }}</small>
                </div>
              </div>
            </td>
            <td>{{ u.company_name }}</td>
            <td>{{ u.role_label }}</td>
            <td>
              <span
                class="status"
                :class="u.is_active ? 'status-completed' : 'status-cancelled'"
                ><span></span>{{ u.is_active ? "啟用" : "停用" }}</span
              ><small v-if="u.must_change_password">待設定密碼</small>
            </td>
            <td>
              <div class="row wrap">
                <button class="btn ghost small" @click="edit(u)">
                  修改資料
                </button>
                <details v-if="auth.isManager" class="action-menu">
                  <summary class="icon-button" aria-label="帳號操作">
                    <MoreHorizontal :size="19" />
                  </summary>
                  <div>
                    <button @click="action(u, 'temporary')">重設臨時密碼</button
                    ><button
                      @click="action(u, u.is_active ? 'disable' : 'enable')"
                    >
                      {{ u.is_active ? "停用帳號" : "啟用帳號" }}</button
                    ><button class="text-error" @click="action(u, 'delete')">
                      刪除帳號
                    </button>
                  </div>
                </details>
              </div>
            </td>
          </tr>
          <tr v-if="!data.items.length">
            <td colspan="5" class="empty-cell">尚無可管理帳號。</td>
          </tr>
        </tbody>
      </table>
    </div>
    <Pagination
      :page="data.page"
      :pages="data.pages"
      :total="data.total"
      @change="load"
    />
  </section>
  <div v-if="modal" class="modal-backdrop" @click.self="close">
    <section class="dialog wide">
      <div class="dialog-heading">
        <div>
          <h2>{{ editing ? "修改帳號資料" : "新增帳號" }}</h2>
          <p class="muted">Email選填，儲存後交付臨時密碼給本人。</p>
        </div>
        <button class="icon-button" aria-label="關閉" @click="close">
          <X :size="20" />
        </button>
      </div>
      <FieldErrors :message="error" />
      <p v-if="!auth.isAdmin" class="muted">所屬公司：{{ auth.user?.company_name }} · 角色：公司報修者</p>
      <form
        @submit.prevent="save"
        @input="ui.dirty = true"
        @change="ui.dirty = true"
      >
        <div class="form-grid">
          <label
            >登入帳號 *<input
              v-model="form.username"
              name="username"
              :disabled="!!editing"
              placeholder="例：yf001"
              required
              minlength="3"
              maxlength="150" /></label
          ><label
            >姓名 *<input
              v-model="form.display_name"
              name="display_name"
              required
              maxlength="100" /></label
          ><label v-if="auth.isAdmin"
            >角色 *<select v-model="form.role" name="role">
              <option v-for="role in data.roles" :value="role.value">
                {{ role.label }}
              </option>
            </select></label
          ><label
            v-if="
              auth.isAdmin && ['reporter', 'company_admin'].includes(form.role)
            "
            >所屬公司 *<select v-model="form.company" name="company" required>
              <option value="">請選擇公司</option>
              <option v-for="c in data.companies" :value="String(c.id)">
                {{ c.name }}
              </option>
            </select></label
          ><label>工號<input v-model="form.staff_id" maxlength="50" /></label
          ><label>部門<input v-model="form.department" maxlength="100" /></label
          ><label>辦公室<input v-model="form.office" maxlength="100" /></label
          ><label>電話／分機<input v-model="form.phone" maxlength="50" /></label
          ><label>手機<input v-model="form.mobile" maxlength="50" /></label
          ><label
            >Email<input
              v-model="form.email"
              type="email"
              placeholder="選填，用於維修進度通知"
          /></label>
        </div>
        <div class="dialog-footer">
          <button type="button" class="btn ghost" @click="close">取消</button
          ><button class="btn primary" :disabled="busy">
            {{ busy ? "儲存中…" : "儲存帳號" }}
          </button>
        </div>
      </form>
    </section>
  </div>
  <div v-if="temporary" class="modal-backdrop">
    <section class="dialog">
      <div class="auth-symbol"><KeyRound :size="24" /></div>
      <h2>帳號已準備完成</h2>
      <p class="muted">請將登入資訊交付本人，密碼僅在本頁顯示。</p>
      <label
        >登入帳號
        <div class="credential">{{ tempUsername }}</div></label
      ><label
        >臨時密碼
        <div class="credential secret">{{ temporary }}</div></label
      >
      <p class="alert warning">
        24小時內有效，首次登入必須更換個人密碼。請勿在公開群組分享。
      </p>
      <button class="btn primary full" @click="temporary = ''">
        已記錄，完成
      </button>
    </section>
  </div>
</template>

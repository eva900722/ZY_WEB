<script setup lang="ts">
import { reactive, ref, onMounted, watch, onBeforeUnmount } from "vue";
import { api, post, errorText } from "../api";
import { useAuth } from "../stores/auth";
import { useUi } from "../stores/ui";
import PageHeading from "../components/PageHeading.vue";
import FieldErrors from "../components/FieldErrors.vue";
const auth = useAuth(),
  ui = useUi();
const info = ref<any>(null),
  busy = ref(false),
  error = ref(""),
  saved = ref("");
const form = reactive({ display_name: "", phone: "", mobile: "", email: "" });
const passwords = reactive({
  old_password: "",
  new_password1: "",
  new_password2: "",
});
function updateUser(user: any) {
  info.value = user;
  auth.user = user;
}
function dirty() {
  ui.dirty =
    !!saved.value &&
    (JSON.stringify(form) !== saved.value ||
      Object.values(passwords).some(Boolean));
}
watch([form, passwords], dirty, { deep: true });
onBeforeUnmount(() => {
  ui.dirty = false;
});
onMounted(async () => {
  try {
    const data = await api("auth/profile/");
    updateUser(data.user);
    for (const key of Object.keys(form) as (keyof typeof form)[])
      form[key] = data.user[key] || "";
    saved.value = JSON.stringify(form);
  } catch (e) {
    error.value = errorText(e);
  }
});
async function save() {
  busy.value = true;
  error.value = "";
  try {
    const data = await post("auth/profile/", form);
    updateUser(data.user);
    for (const key of Object.keys(form) as (keyof typeof form)[])
      form[key] = data.user[key] || "";
    saved.value = JSON.stringify(form);
    dirty();
    ui.notify(data.message);
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
async function changePassword() {
  busy.value = true;
  error.value = "";
  try {
    const data = await post("auth/password/", passwords);
    updateUser(data.user);
    Object.assign(passwords, {
      old_password: "",
      new_password1: "",
      new_password2: "",
    });
    dirty();
    ui.notify(data.message);
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <PageHeading title="個人設定" subtitle="維護自己的聯絡資料、Email及密碼。" />
  <FieldErrors :message="error" />
  <div v-if="info" class="profile-layout">
    <section class="panel">
      <form @submit.prevent="save">
        <div class="form-section">
          <h2>基本資料</h2>
          <dl class="info-grid">
            <dt>登入帳號</dt>
            <dd>{{ info.username }}</dd>
            <dt>所屬公司</dt>
            <dd>{{ info.company_name }}</dd>
            <dt>角色</dt>
            <dd>{{ info.role_label }}</dd>
            <dt>工號</dt>
            <dd>{{ info.staff_id || "未填寫" }}</dd>
            <dt>部門</dt>
            <dd>{{ info.department || "未填寫" }}</dd>
            <dt>辦公室</dt>
            <dd>{{ info.office || "未填寫" }}</dd>
          </dl>
          <p class="muted">
            帳號、公司、角色、工號、部門與辦公室由有權限的管理者維護。
          </p>
          <label
            >顯示姓名<input
              v-model="form.display_name"
              name="display_name"
              required
              maxlength="100"
              autocomplete="name"
          /></label>
          <label
            >電話／分機<input
              v-model="form.phone"
              name="phone"
              maxlength="50"
              autocomplete="tel"
          /></label>
          <label
            >手機<input
              v-model="form.mobile"
              name="mobile"
              maxlength="50"
              autocomplete="tel"
          /></label>
        </div>
        <div class="form-section border-top">
          <h2>Email</h2>
          <label
            >Email（選填）<input
              v-model="form.email"
              name="email"
              type="email"
              maxlength="254"
              autocomplete="email"
          /></label>
          <p class="muted">
            Email選填，儲存後直接依此信箱寄送維修通知，不需驗證。忘記密碼請聯絡贊耀公司人員。
          </p>
          <button class="btn primary" :disabled="busy">儲存個人資料</button>
        </div>
      </form>
    </section>
    <section class="panel form-section">
      <h2>修改密碼</h2>
      <form @submit.prevent="changePassword">
        <label
          >目前密碼<input
            v-model="passwords.old_password"
            name="old_password"
            type="password"
            required
            autocomplete="current-password"
        /></label>
        <label
          >新密碼<input
            v-model="passwords.new_password1"
            name="new_password1"
            type="password"
            required
            minlength="10"
            autocomplete="new-password"
        /></label>
        <label
          >確認新密碼<input
            v-model="passwords.new_password2"
            name="new_password2"
            type="password"
            required
            minlength="10"
            autocomplete="new-password"
        /></label>
        <button class="btn primary" :disabled="busy">更新密碼</button>
      </form>
    </section>
  </div>
  <div v-else class="loading-state">載入中…</div>
</template>

<style scoped>
.profile-layout {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: 22px;
  align-items: start;
}
.profile-layout > .panel > form {
  padding: 0;
}
.profile-layout .info-grid {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px 18px;
  margin: 18px 0;
}
.info-grid dt {
  color: var(--muted);
}
.info-grid dd {
  margin: 0;
  overflow-wrap: anywhere;
}
@media (max-width: 860px) {
  .profile-layout {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
  }
}
</style>

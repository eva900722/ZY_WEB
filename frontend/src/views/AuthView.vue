<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import {
  Eye,
  EyeOff,
  ArrowRight,
  ShieldCheck,
  ArrowLeft,
  LockKeyhole,
  CheckCircle2,
} from "@lucide/vue";
import { useAuth } from "../stores/auth";
import { useUi } from "../stores/ui";
import { post, errorText } from "../api";
import FieldErrors from "../components/FieldErrors.vue";
const route = useRoute(),
  router = useRouter(),
  auth = useAuth(),
  ui = useUi();
const username = ref(""),
  password = ref(""),
  newPassword = ref(""),
  confirmPassword = ref(""),
  show = ref(false),
  busy = ref(false),
  error = ref("");
const mode = computed(() =>
  route.params.raw
    ? "token"
    : route.path.includes("forgot")
      ? "forgot"
      : route.path.includes("password")
        ? "password"
        : "login",
);
const title = computed(() =>
  mode.value === "login"
    ? "登入" + auth.platform.platform_name
    : mode.value === "forgot"
      ? "忘記密碼"
      : mode.value === "password"
        ? "設定個人密碼"
        : "連結已停用",
);
const done = computed(() =>
  ["forgot", "token"].includes(mode.value)
    ? "報修者請聯絡本公司管理者或贊耀公司人員重設臨時密碼；公司管理者請聯絡贊耀公司人員。使用臨時密碼登入後，必須先設定自己的密碼才能繼續使用。"
    : "",
);
watch(
  () => route.fullPath,
  () => {
    error.value = "";
    password.value = "";
    newPassword.value = "";
    confirmPassword.value = "";
  },
);
async function submit() {
  error.value = "";
  busy.value = true;
  try {
    if (mode.value === "login") {
      await auth.login(username.value, password.value);
      password.value = "";
      await router.push(
        auth.user?.must_change_password ? "/accounts/password/" : "/",
      );
    } else if (mode.value === "password") {
      const data = await post("auth/password/", {
        old_password: password.value,
        new_password1: newPassword.value,
        new_password2: confirmPassword.value,
      });
      auth.user = data.user;
      password.value = "";
      newPassword.value = "";
      confirmPassword.value = "";
      ui.notify(data.message);
      await router.push("/");
    }
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="auth-page">
    <div class="auth-top">
      <RouterLink to="/" class="auth-brand"
        ><span class="brand-mark">Z</span
        ><strong>{{ auth.platform.platform_name }}</strong></RouterLink
      ><span>{{ auth.platform.company_name }}｜銷售・維修・資訊服務</span>
    </div>
    <main class="auth-main">
      <section class="auth-card">
        <div class="auth-symbol">
          <LockKeyhole v-if="mode !== 'token'" :size="23" /><ShieldCheck
            v-else
            :size="23"
          />
        </div>
        <h1>{{ title }}</h1>
        <p class="auth-subtitle">
          {{
            mode === "login"
              ? "使用管理者提供的帳號，掌握報修與維修進度。"
              : mode === "forgot"
                ? "不提供Email自助重設，請聯絡贊耀公司人員。"
                : mode === "password"
                  ? "請設定只有您知道的密碼，完成後即可繼續。"
                  : "舊的驗證與密碼重設連結已停止使用。"
          }}
        </p>
        <FieldErrors :message="error" />
        <div v-if="done" class="alert success">
          <CheckCircle2 :size="18" />{{ done }}
        </div>
        <form v-if="!done" @submit.prevent="submit">
          <label v-if="mode === 'login'"
            >登入帳號<input
              v-model="username"
              name="username"
              autocomplete="username"
              placeholder="請輸入帳號"
              required
              autofocus
              maxlength="150" /></label
          ><label v-if="mode === 'login' || mode === 'password'"
            >{{ mode === "password" ? "目前密碼／臨時密碼" : "密碼" }}
            <div class="password-input">
              <input
                v-model="password"
                name="password"
                :type="show ? 'text' : 'password'"
                autocomplete="current-password"
                placeholder="請輸入密碼"
                required
              /><button
                type="button"
                class="icon-button"
                :aria-label="show ? '隱藏密碼' : '顯示密碼'"
                @click="show = !show"
              >
                <EyeOff v-if="show" :size="18" /><Eye v-else :size="18" />
              </button></div></label
          ><template v-if="mode === 'password'"
            ><label
              >新密碼<input
                v-model="newPassword"
                name="new_password1"
                type="password"
                autocomplete="new-password"
                placeholder="至少10個字元"
                minlength="10"
                required /></label
            ><label
              >再次確認密碼<input
                v-model="confirmPassword"
                name="new_password2"
                type="password"
                autocomplete="new-password"
                placeholder="再次輸入新密碼"
                required /></label></template
          ><button class="btn primary full" :disabled="busy">
            <span v-if="busy" class="spinner"></span
            >{{ busy ? "處理中…" : mode === "login" ? "登入" : "設定密碼並繼續"
            }}<ArrowRight v-if="!busy" :size="17" />
          </button>
        </form>
        <div class="auth-links">
          <RouterLink v-if="mode === 'login'" to="/accounts/forgot/"
            >忘記密碼？</RouterLink
          ><RouterLink
            v-else
            :to="
              auth.user && !auth.user.must_change_password
                ? '/'
                : '/accounts/login/'
            "
            ><ArrowLeft :size="15" />{{
              auth.user && !auth.user.must_change_password
                ? "返回工作台"
                : "返回登入"
            }}</RouterLink
          >
        </div>
        <div class="auth-note">
          <ShieldCheck :size="16" /><span>{{
            mode === "login"
              ? "首次登入需更換管理者提供的臨時密碼。"
              : mode === "forgot"
                ? "贊耀公司人員重設的臨時密碼有效24小時。"
                : "不再提供Email驗證或重設連結。"
          }}</span>
        </div>
      </section>
      <p class="auth-footer">ZY-Info · {{ auth.platform.platform_name }}</p>
    </main>
  </div>
</template>

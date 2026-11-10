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
import { api, post, errorText } from "../api";
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
  error = ref(""),
  done = ref(""),
  purpose = ref(""),
  tokenReady = ref(false);
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
    ? "登入資訊管家"
    : mode.value === "forgot"
      ? "忘記密碼"
      : mode.value === "password"
        ? "設定個人密碼"
        : purpose.value === "verify"
          ? "驗證您的信箱"
          : "設定新密碼",
);
watch(
  () => route.fullPath,
  async () => {
    error.value = "";
    done.value = "";
    password.value = "";
    newPassword.value = "";
    confirmPassword.value = "";
    tokenReady.value = false;
    if (mode.value === "token") {
      try {
        const d = await api(
          "auth/token/" + encodeURIComponent(String(route.params.raw)) + "/",
        );
        purpose.value = d.purpose;
        tokenReady.value = true;
      } catch (e) {
        error.value = errorText(e);
      }
    }
  },
  { immediate: true },
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
    } else if (mode.value === "forgot") {
      const d = await post("auth/forgot/", { username: username.value });
      done.value = d.message;
    } else if (mode.value === "password") {
      const d = await post("auth/password/", {
        old_password: password.value,
        new_password1: newPassword.value,
        new_password2: confirmPassword.value,
      });
      auth.user = d.user;
      password.value = "";
      newPassword.value = "";
      confirmPassword.value = "";
      ui.notify(d.message);
      await router.push("/");
    } else {
      const d = await post(
        "auth/token/" + encodeURIComponent(String(route.params.raw)) + "/",
        {
          new_password1: newPassword.value,
          new_password2: confirmPassword.value,
        },
      );
      newPassword.value = "";
      confirmPassword.value = "";
      done.value = d.message;
      await auth.load();
      tokenReady.value = false;
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
        ><span class="brand-mark">Z</span><strong>資訊管家</strong></RouterLink
      ><span>企業 IT 服務平台</span>
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
                ? "輸入登入帳號，我們將寄送密碼重設通知。"
                : mode === "password"
                  ? "請設定只有您知道的密碼，完成後即可繼續。"
                  : purpose === "verify"
                    ? "確認後，這個信箱即可使用密碼復原功能。"
                    : "連結只能使用一次，請設定新的個人密碼。"
          }}
        </p>
        <FieldErrors :message="error" />
        <div v-if="done" class="alert success">
          <CheckCircle2 :size="18" />{{ done }}
        </div>
        <form v-if="!done" @submit.prevent="submit">
          <label v-if="mode === 'login' || mode === 'forgot'"
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
          ><template
            v-if="
              mode === 'password' ||
              (mode === 'token' && purpose === 'reset' && tokenReady)
            "
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
          ><button
            class="btn primary full"
            :disabled="busy || (mode === 'token' && !tokenReady)"
          >
            <span v-if="busy" class="spinner"></span
            >{{
              busy
                ? "處理中…"
                : mode === "login"
                  ? "登入"
                  : mode === "forgot"
                    ? "寄送重設通知"
                    : mode === "password"
                      ? "設定密碼並繼續"
                      : purpose === "verify"
                        ? "確認驗證信箱"
                        : "儲存新密碼"
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
                ? "未設定Email或無法收信，請聯絡資訊公司管理者。"
                : "密碼與驗證資訊不會儲存在瀏覽器快取。"
          }}</span>
        </div>
      </section>
      <p class="auth-footer">ZY-Info · 資訊管家</p>
    </main>
  </div>
</template>

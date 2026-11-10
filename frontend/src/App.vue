<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from "vue";
import { useRoute, useRouter, RouterLink, RouterView } from "vue-router";
import {
  LayoutDashboard,
  Plus,
  Building2,
  Users,
  SlidersHorizontal,
  Bell,
  ScrollText,
  LogOut,
  Menu,
  X,
  Download,
  RefreshCw,
  WifiOff,
  ChevronRight,
  KeyRound,
} from "@lucide/vue";
import { registerSW } from "virtual:pwa-register";
import { useAuth } from "./stores/auth";
import { useUi } from "./stores/ui";
import { api, errorText } from "./api";
const auth = useAuth(),
  ui = useUi(),
  route = useRoute(),
  router = useRouter();
const open = ref(false),
  online = ref(navigator.onLine),
  unread = ref(0),
  needRefresh = ref(false),
  installPrompt = ref<any>(null),
  installHelp = ref(false);
const authScreen = computed(
  () => route.meta.public || route.path.includes("/password"),
);
const navigation = computed(() =>
  [
    { path: "/", label: "案件總覽", icon: LayoutDashboard, show: true },
    {
      path: "/tickets/new/",
      label: "新增報修",
      icon: Plus,
      show: !auth.isEngineer,
    },
    { path: "/notifications/", label: "通知中心", icon: Bell, show: true },
    { path: "/users/", label: "帳號管理", icon: Users, show: auth.isManager },
    {
      path: "/companies/",
      label: "公司管理",
      icon: Building2,
      show: auth.isAdmin,
    },
    {
      path: "/versions/",
      label: "報修表單",
      icon: SlidersHorizontal,
      show: auth.isAdmin,
    },
    {
      path: "/audit/",
      label: "操作紀錄",
      icon: ScrollText,
      show: auth.isAdmin,
    },
  ].filter((x) => x.show),
);
function active(path: string) {
  return path === "/"
    ? route.path === "/"
    : path === "/tickets/new/"
      ? route.path === path
      : route.path.startsWith(path);
}
function reload() {
  window.location.reload();
}
function connectivity() {
  online.value = navigator.onLine;
}
function beforeUnload(e: BeforeUnloadEvent) {
  if (ui.dirty) {
    e.preventDefault();
    e.returnValue = "";
  }
}
function installEvent(e: Event) {
  e.preventDefault();
  installPrompt.value = e;
}
async function install() {
  if (installPrompt.value) {
    await installPrompt.value.prompt();
    installPrompt.value = null;
  } else installHelp.value = true;
}
async function logout() {
  if (ui.dirty && !confirm("仍有尚未送出的內容，確定登出？")) return;
  ui.dirty = false;
  try {
    await auth.logout();
    unread.value = 0;
    await router.push("/accounts/login/");
  } catch (e) {
    ui.notify(errorText(e), "error");
  }
}
function expired() {
  auth.user = null;
  auth.ready = false;
  unread.value = 0;
  ui.notify("登入已失效，請重新登入", "error");
  router.push("/accounts/login/");
}
function passwordRequired() {
  router.push("/accounts/password/");
}
let updateSW: ((reload?: boolean) => Promise<void>) | undefined;
async function update() {
  if (ui.dirty) {
    ui.notify("請先送出或處理尚未完成的表單，再更新應用程式", "error");
    return;
  }
  await updateSW?.(true);
}
let interval: ReturnType<typeof setInterval>;
async function loadUnread() {
  if (auth.user && !auth.user.must_change_password && online.value) {
    try {
      const d = await api("notifications/");
      unread.value = d.unread;
    } catch {
      /* Request handler already reports an expired session. */
    }
  }
}
watch(
  () => route.fullPath,
  () => {
    open.value = false;
    loadUnread();
  },
);
onMounted(() => {
  window.addEventListener("online", connectivity);
  window.addEventListener("offline", connectivity);
  window.addEventListener("beforeunload", beforeUnload);
  window.addEventListener("beforeinstallprompt", installEvent);
  window.addEventListener("session-expired", expired);
  window.addEventListener("password-required", passwordRequired);
  updateSW = registerSW({
    onNeedRefresh() {
      needRefresh.value = true;
    },
  });
  interval = setInterval(loadUnread, 60000);
  loadUnread();
});
onBeforeUnmount(() => {
  clearInterval(interval);
  window.removeEventListener("online", connectivity);
  window.removeEventListener("offline", connectivity);
  window.removeEventListener("beforeunload", beforeUnload);
  window.removeEventListener("beforeinstallprompt", installEvent);
  window.removeEventListener("session-expired", expired);
  window.removeEventListener("password-required", passwordRequired);
});
</script>
<template>
  <div v-if="!online" class="connectivity-banner">
    <WifiOff
      :size="16"
    />目前離線，案件查詢與送出需連上網路；未送出的內容仍留在目前畫面。
  </div>
  <div v-if="needRefresh" class="update-banner">
    <RefreshCw :size="16" /><span>有新版本可使用，完成目前工作後再更新。</span
    ><button @click="update">立即更新</button
    ><button class="quiet" @click="needRefresh = false">稍後</button>
  </div>
  <div v-if="ui.message" class="toast" :class="ui.tone" role="status">
    {{ ui.message
    }}<button aria-label="關閉提示" @click="ui.message = ''">
      <X :size="16" />
    </button>
  </div>
  <template v-if="authScreen"><RouterView /></template>
  <div v-else-if="auth.user" class="app-shell">
    <div class="sidebar-backdrop" v-if="open" @click="open = false"></div>
    <aside class="sidebar" :class="{ open }">
      <RouterLink to="/" class="brand"
        ><span class="brand-mark">Z</span>
        <div>資訊管家<small>ZY INFO · SERVICE DESK</small></div></RouterLink
      >
      <p class="nav-section">工作空間</p>
      <nav>
        <RouterLink
          v-for="item in navigation"
          :key="item.path"
          :to="item.path"
          :class="{ active: active(item.path) }"
          ><component :is="item.icon" :size="19" /><span>{{ item.label }}</span
          ><span
            v-if="item.path === '/notifications/' && unread"
            class="nav-count"
            >{{ unread }}</span
          ></RouterLink
        >
      </nav>
      <div class="sidebar-bottom">
        <button @click="install"><Download :size="17" />安裝到裝置</button
        ><RouterLink to="/accounts/password/"
          ><KeyRound :size="17" />修改密碼</RouterLink
        ><button @click="logout"><LogOut :size="17" />登出系統</button
        ><small>ZY-Info © 2026</small>
      </div>
    </aside>
    <div class="workspace">
      <header class="topbar">
        <button
          class="icon-button menu-toggle"
          aria-label="開啟選單"
          @click="open = !open"
        >
          <Menu :size="22" />
        </button>
        <div class="breadcrumb">
          <span>工作空間</span><ChevronRight :size="14" /><strong>{{
            navigation.find((x) => active(x.path))?.label || "案件詳情"
          }}</strong>
        </div>
        <div class="topbar-right">
          <span class="company-chip"
            ><Building2 :size="14" />{{ auth.user.company_name }}</span
          ><RouterLink
            to="/notifications/"
            class="icon-button notification-button"
            aria-label="通知中心"
            ><Bell :size="19" /><i v-if="unread"></i
          ></RouterLink>
          <div class="avatar">{{ auth.user.display_name.slice(0, 1) }}</div>
          <div class="user-info">
            <strong>{{ auth.user.display_name }}</strong
            ><small>{{ auth.user.role_label }}</small>
          </div>
        </div>
      </header>
      <main class="main-content"><RouterView /></main>
      <footer class="app-footer">資訊管家 · 讓每一個問題都有進度。</footer>
    </div>
  </div>
  <div v-else class="boot-screen">
    <span class="brand-mark">Z</span>
    <p>
      {{
        online ? "正在載入工作空間…" : "尚未連線，請恢復網路後再開啟工作空間。"
      }}
    </p>
    <button v-if="!online" class="btn" @click="reload">重新連線</button>
  </div>
  <div
    v-if="installHelp"
    class="modal-backdrop"
    @click.self="installHelp = false"
  >
    <section class="dialog">
      <button
        class="dialog-close icon-button"
        aria-label="關閉"
        @click="installHelp = false"
      >
        <X :size="20" />
      </button>
      <h2>安裝資訊管家</h2>
      <p>在支援的Chrome或Edge瀏覽器，從網址列或選單選擇「安裝應用程式」。</p>
      <p>
        iPhone／iPad可在Safari分享選單選擇「加入主畫面」。安裝方式依裝置及瀏覽器而異。
      </p>
      <p class="muted">正式網址需使用HTTPS。安裝後仍需網路連線處理案件。</p>
      <button class="btn" @click="installHelp = false">了解</button>
    </section>
  </div>
</template>

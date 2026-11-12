<script setup lang="ts">
import {
  computed,
  onMounted,
  onBeforeUnmount,
  reactive,
  ref,
  watch,
} from "vue";
import { useRoute, useRouter, RouterLink, RouterView } from "vue-router";
import {
  Building2,
  Bell,
  LogOut,
  Menu,
  X,
  Download,
  RefreshCw,
  WifiOff,
  ChevronRight,
} from "@lucide/vue";
import { navigationModules, moduleOwnsPath } from "./navigation";
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
const modules = computed(() => navigationModules(auth.user?.role || ""));
const navigation = computed(() =>
  modules.value.flatMap((module) => module.items),
);
const activeModule = computed(() =>
  modules.value.find((module) => moduleOwnsPath(module, route.path)),
);
const expanded = reactive<Record<string, boolean>>({});
function moduleOpen(id: string) {
  return (
    expanded[id] ??
    (activeModule.value?.id === id || modules.value.length === 1)
  );
}
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
    if (activeModule.value) expanded[activeModule.value.id] = true;
    loadUnread();
  },
);
onMounted(() => {
  window.addEventListener("notifications-updated", loadUnread);
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
  window.removeEventListener("notifications-updated", loadUnread);
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
        <div>
          {{ auth.platform.platform_name }}<small>{{ auth.platform.company_name }}｜銷售・維修・資訊服務</small>
        </div></RouterLink
      >
      <div class="module-navigation">
        <section v-for="module in modules" :key="module.id" class="nav-module">
          <button
            type="button"
            class="module-toggle"
            :class="{ current: activeModule?.id === module.id }"
            :aria-expanded="moduleOpen(module.id)"
            :aria-controls="'module-' + module.id"
            @click="expanded[module.id] = !moduleOpen(module.id)"
          >
            <component :is="module.icon" :size="18" /><span>{{
              module.label
            }}</span>
            <ChevronRight
              :size="16"
              class="module-caret"
              :class="{ expanded: moduleOpen(module.id) }"
            />
          </button>
          <nav
            v-show="moduleOpen(module.id)"
            :id="'module-' + module.id"
            :aria-label="module.label"
            class="module-links"
          >
            <RouterLink
              v-for="item in module.items"
              :key="item.path"
              :to="item.path"
              :class="{ active: active(item.path) }"
              :aria-current="active(item.path) ? 'page' : undefined"
            >
              <component :is="item.icon" :size="19" /><span>{{
                item.label
              }}</span>
              <span
                v-if="item.path === '/notifications/' && unread"
                class="nav-count"
                >{{ unread }}</span
              >
            </RouterLink>
          </nav>
        </section>
      </div>
      <div class="sidebar-bottom">
        <button @click="install"><Download :size="17" />安裝到裝置</button
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
          <span>{{ activeModule?.label || auth.platform.platform_name }}</span
          ><ChevronRight :size="14" /><strong>{{
            route.path === "/settings/profile/"
              ? "個人設定"
              : navigation.find((x) => active(x.path))?.label || "案件詳情"
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
          <RouterLink
            to="/settings/profile/"
            class="avatar"
            aria-label="個人設定"
            title="個人設定"
            >{{ auth.user.display_name.slice(0, 1) }}</RouterLink
          >
          <RouterLink
            to="/settings/profile/"
            class="user-info"
            aria-label="編輯個人資料"
          >
            <strong>{{ auth.user.display_name }}</strong
            ><small>{{ auth.user.role_label }}</small>
          </RouterLink>
        </div>
      </header>
      <main class="main-content"><RouterView /></main>
      <footer class="app-footer">
        {{ auth.platform.platform_name }} · 讓每一個問題都有進度。
        <span v-if="auth.platform.contact_phone"> · {{ auth.platform.contact_phone }}</span>
        <span v-if="auth.platform.contact_email"> · {{ auth.platform.contact_email }}</span>
      </footer>
    </div>
  </div>
  <div v-else class="boot-screen">
    <span class="brand-mark">Z</span>
    <p>
      {{
        online
          ? "正在載入贊耀服務平台…"
          : "尚未連線，請恢復網路後再開啟贊耀服務平台。"
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
      <h2>安裝贊耀服務平台</h2>
      <p>在支援的Chrome或Edge瀏覽器，從網址列或選單選擇「安裝應用程式」。</p>
      <p>
        iPhone／iPad可在Safari分享選單選擇「加入主畫面」。安裝方式依裝置及瀏覽器而異。
      </p>
      <p class="muted">正式網址需使用HTTPS。安裝後仍需網路連線處理案件。</p>
      <button class="btn" @click="installHelp = false">了解</button>
    </section>
  </div>
</template>

<style scoped>
.sidebar .brand {
  margin: 0 4px 28px;
  font-size: 17px;
}
.sidebar .brand-mark {
  flex-shrink: 0;
}
.sidebar .brand div {
  min-width: 0;
}
.sidebar .brand small {
  line-height: 1.6;
  letter-spacing: 0;
}
.module-navigation {
  overflow-y: auto;
  min-height: 0;
}
.nav-module + .nav-module {
  margin-top: 8px;
}
.module-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 44px;
  padding: 10px 8px;
  border: 0;
  border-radius: 8px;
  background: #1e3a5f;
  color: #f8fafc;
  font: inherit;
  font-size: 13px;
  font-weight: 650;
  text-align: left;
}
.module-toggle span {
  flex: 1;
}
.module-toggle.current {
  color: #f8fafc;
}
.module-toggle:hover {
  background: #24476f;
}
.module-toggle:focus-visible {
  outline: 2px solid #22d3ee;
  outline-offset: -2px;
}
.module-caret {
  flex-shrink: 0;
  transition: transform 0.15s;
}
.module-caret.expanded {
  transform: rotate(90deg);
}
.module-links {
  margin: 5px 0 0 12px;
}
</style>

import { createRouter, createWebHistory } from "vue-router";
import { useAuth } from "../stores/auth";
import { useUi } from "../stores/ui";
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/accounts/login/",
      alias: "/login",
      component: () => import("../views/AuthView.vue"),
      meta: { public: true },
    },
    {
      path: "/accounts/forgot/",
      alias: "/forgot",
      component: () => import("../views/AuthView.vue"),
      meta: { public: true },
    },
    {
      path: "/accounts/token/:raw/",
      component: () => import("../views/AuthView.vue"),
      meta: { public: true },
    },
    {
      path: "/accounts/password/",
      alias: "/password",
      component: () => import("../views/AuthView.vue"),
    },
    { path: "/", component: () => import("../views/DashboardView.vue") },
    {
      path: "/tickets/new/",
      component: () => import("../views/TicketCreateView.vue"),
      meta: { roles: ["reporter", "company_admin", "it_admin"] },
    },
    {
      path: "/tickets/:id/",
      component: () => import("../views/TicketDetailView.vue"),
    },
    {
      path: "/companies/:id?/",
      component: () => import("../views/CompaniesView.vue"),
      meta: { roles: ["it_admin"] },
    },
    {
      path: "/users/:id?/",
      component: () => import("../views/UsersView.vue"),
      meta: { roles: ["it_admin", "company_admin"] },
    },
    {
      path: "/versions/",
      component: () => import("../views/VersionsView.vue"),
      meta: { roles: ["it_admin"] },
    },
    {
      path: "/notifications/",
      component: () => import("../views/ActivityView.vue"),
    },
    {
      path: "/audit/",
      component: () => import("../views/ActivityView.vue"),
      meta: { roles: ["it_admin"] },
    },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});
router.beforeEach(async (to, from) => {
  const auth = useAuth();
  const ui = useUi();
  if (
    ui.dirty &&
    to.fullPath !== from.fullPath &&
    !confirm("仍有尚未送出的內容，確定離開？")
  )
    return false;
  ui.dirty = false;
  if (!auth.ready) {
    try {
      await auth.load();
    } catch {
      return to.meta.public ? true : false;
    }
  }
  if (!to.meta.public && !auth.user) return "/accounts/login/";
  if (
    auth.user?.must_change_password &&
    !to.meta.public &&
    !to.path.includes("/password")
  )
    return "/accounts/password/";
  if (
    to.meta.roles &&
    auth.user &&
    !(to.meta.roles as string[]).includes(auth.user.role)
  )
    return "/";
  if (auth.user && to.path.includes("/login"))
    return auth.user.must_change_password ? "/accounts/password/" : "/";
});
export default router;

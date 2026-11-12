import type { Component } from "vue";
import {
  LayoutDashboard,
  Plus,
  Building2,
  Users,
  SlidersHorizontal,
  Bell,
  Wrench,
  Settings,
} from "@lucide/vue";
export type NavigationItem = {
  path: string;
  label: string;
  icon: Component;
  roles?: string[];
};
export type NavigationModule = {
  id: string;
  label: string;
  icon: Component;
  routes: string[];
  items: NavigationItem[];
};
// Add future systems here, with their own route prefixes and role-filtered items.
const definitions: NavigationModule[] = [
  {
    id: "repairs",
    label: "報修系統入口",
    icon: Wrench,
    routes: [
      "/",
      "/tickets/",
      "/notifications/",
      "/users/",
      "/companies/",
      "/versions/",
      "/settings/system/",
    ],
    items: [
      { path: "/", label: "案件總覽", icon: LayoutDashboard },
      { path: "/tickets/new/", label: "新增報修", icon: Plus },
      { path: "/notifications/", label: "通知中心", icon: Bell },
      {
        path: "/users/",
        label: "帳號管理",
        icon: Users,
        roles: ["it_admin", "company_admin"],
      },
      {
        path: "/companies/",
        label: "公司管理",
        icon: Building2,
        roles: ["it_admin"],
      },
      {
        path: "/versions/",
        label: "報修表單",
        icon: SlidersHorizontal,
        roles: ["it_admin"],
      },
      {
        path: "/settings/system/",
        label: "系統設定",
        icon: Settings,
        roles: ["it_admin"],
      },
    ],
  },
];
export function navigationModules(role: string): NavigationModule[] {
  return definitions
    .map((module) => ({
      ...module,
      items: module.items.filter(
        (item) => !item.roles || item.roles.includes(role),
      ),
    }))
    .filter((module) => module.items.length > 0);
}
export function moduleOwnsPath(
  module: NavigationModule,
  path: string,
): boolean {
  return module.routes.some((prefix) =>
    prefix === "/" ? path === "/" : path.startsWith(prefix),
  );
}

import { defineStore } from "pinia";
import { api, post } from "../api";
export type User = {
  id: number;
  username: string;
  display_name: string;
  role: string;
  role_label: string;
  company_id: number | null;
  company_name: string;
  email: string;
  email_verified: boolean;
  must_change_password: boolean;
  office: string;
};
export const useAuth = defineStore("auth", {
  state: () => ({ user: null as User | null, ready: false }),
  getters: {
    isAdmin: (s) => s.user?.role === "it_admin",
    isManager: (s) =>
      ["it_admin", "company_admin"].includes(s.user?.role || ""),
  },
  actions: {
    async load() {
      const d = await api("auth/session/");
      this.user = d.user;
      this.ready = true;
    },
    async login(username: string, password: string) {
      const d = await post("auth/login/", { username, password });
      this.user = d.user;
      this.ready = true;
    },
    async logout() {
      await post("auth/logout/", {});
      this.user = null;
      this.ready = false;
      await this.load();
    },
  },
});

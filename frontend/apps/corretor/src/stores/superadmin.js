import { defineStore } from "pinia";
import adminApi, { setAdminAccessToken } from "../api/adminClient";

export const useSuperadminAuthStore = defineStore("superadminAuth", {
  state: () => ({
    accessToken: null,
    error: null,
    loading: false,
  }),
  getters: {
    isAuthenticated: (state) => !!state.accessToken,
  },
  actions: {
    async login({ email, senha }) {
      this.loading = true;
      this.error = null;
      try {
        const { data } = await adminApi.post("/auth/login", { email, senha });
        this.accessToken = data.access_token;
        setAdminAccessToken(data.access_token);
        return true;
      } catch (err) {
        this.error = err.response?.data?.detail ?? "Não foi possível entrar.";
        return false;
      } finally {
        this.loading = false;
      }
    },
    logout() {
      this.accessToken = null;
      setAdminAccessToken(null);
    },
  },
});

import { defineStore } from "pinia";
import api, { setAccessToken } from "../api/client";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    user: null,
    accessToken: null,
    error: null,
    loading: false,
  }),
  getters: {
    isAuthenticated: (state) => !!state.accessToken,
    isAdmin: (state) => state.user?.papel === "admin",
  },
  actions: {
    async signup({ nomeTenant, nome, email, senha }) {
      return this._authenticate(() =>
        api.post("/auth/signup", { nome_tenant: nomeTenant, nome, email, senha })
      );
    },
    async login({ email, senha, codigoTotp }) {
      return this._authenticate(() =>
        api.post("/auth/login", { email, senha, codigo_totp: codigoTotp || undefined })
      );
    },
    async logout() {
      try {
        await api.post("/auth/logout");
      } finally {
        this.user = null;
        this.accessToken = null;
        setAccessToken(null);
      }
    },
    async _authenticate(request) {
      this.loading = true;
      this.error = null;
      try {
        const { data } = await request();
        this.user = data.user;
        this.accessToken = data.access_token;
        setAccessToken(data.access_token);
        return true;
      } catch (err) {
        this.error = err.response?.data?.detail ?? "Não foi possível completar a operação.";
        return false;
      } finally {
        this.loading = false;
      }
    },
  },
});

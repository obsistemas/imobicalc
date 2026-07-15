<script setup>
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import api, { setAccessToken } from "../api/client";
import { useAuthStore } from "../stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const form = reactive({ nome: "", senha: "" });
const error = ref("");
const loading = ref(false);

async function onSubmit() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await api.post(`/convites/${route.params.token}/aceitar`, form);
    auth.user = data.user;
    auth.accessToken = data.access_token;
    setAccessToken(data.access_token);
    router.push({ name: "home" });
  } catch (err) {
    error.value =
      err.response?.status === 410
        ? "Este convite expirou ou já foi utilizado."
        : "Não foi possível aceitar o convite.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-900">
    <div class="w-full max-w-sm rounded-xl bg-white p-8 shadow-sm dark:bg-slate-800">
      <h1 class="mb-6 text-xl font-semibold text-slate-900 dark:text-white">Aceitar convite</h1>

      <form class="space-y-4" @submit.prevent="onSubmit">
        <div>
          <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300" for="nome">
            Seu nome
          </label>
          <input
            id="nome"
            v-model="form.nome"
            type="text"
            required
            minlength="2"
            class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white"
          />
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300" for="senha">
            Crie uma senha
          </label>
          <input
            id="senha"
            v-model="form.senha"
            type="password"
            required
            minlength="8"
            maxlength="72"
            class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white"
          />
        </div>

        <p v-if="error" class="text-sm text-red-600" role="alert">{{ error }}</p>

        <button
          type="submit"
          :disabled="loading"
          class="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {{ loading ? "Entrando…" : "Aceitar e entrar" }}
        </button>
      </form>
    </div>
  </div>
</template>

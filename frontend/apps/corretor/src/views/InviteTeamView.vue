<script setup>
import { reactive, ref } from "vue";
import api from "../api/client";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const form = reactive({ email: "" });
const status = ref(null); // null | "ok" | "erro"
const mensagem = ref("");
const loading = ref(false);

async function onSubmit() {
  loading.value = true;
  status.value = null;
  try {
    await api.post("/users/convites", { email: form.email });
    status.value = "ok";
    mensagem.value = `Convite enviado para ${form.email}.`;
    form.email = "";
  } catch (err) {
    status.value = "erro";
    if (err.response?.status === 403) {
      mensagem.value = "Ative o 2FA antes de convidar corretores.";
    } else if (err.response?.status === 409) {
      mensagem.value = err.response.data?.detail ?? "Já existe convite ou usuário com este e-mail.";
    } else {
      mensagem.value = "Não foi possível enviar o convite.";
    }
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="mx-auto max-w-md p-6">
    <h1 class="mb-4 text-xl font-semibold text-slate-900 dark:text-white">Convidar corretor</h1>

    <p v-if="!auth.isAdmin" class="text-sm text-amber-600">
      Apenas admin pode convidar novos corretores.
    </p>

    <form v-else class="space-y-4" @submit.prevent="onSubmit">
      <div>
        <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300" for="email">
          E-mail do corretor
        </label>
        <input
          id="email"
          v-model="form.email"
          type="email"
          required
          class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white"
        />
      </div>

      <p v-if="status === 'ok'" class="text-sm text-emerald-700 dark:text-emerald-400">{{ mensagem }}</p>
      <p v-if="status === 'erro'" class="text-sm text-red-600" role="alert">{{ mensagem }}</p>

      <button
        type="submit"
        :disabled="loading"
        class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {{ loading ? "Enviando…" : "Enviar convite" }}
      </button>
    </form>
  </div>
</template>

<script setup>
import { reactive } from "vue";
import { useRouter } from "vue-router";
import { useSuperadminAuthStore } from "../stores/superadmin";

const auth = useSuperadminAuthStore();
const router = useRouter();

const form = reactive({ email: "", senha: "" });

async function onSubmit() {
  const ok = await auth.login(form);
  if (ok) {
    router.push({ name: "admin-dashboard" });
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-slate-950 px-4">
    <div class="w-full max-w-sm rounded-xl bg-slate-900 p-8 shadow-sm">
      <h1 class="mb-1 text-xl font-semibold text-white">Painel da plataforma</h1>
      <p class="mb-6 text-sm text-slate-400">Acesso restrito ao dono da plataforma — não é o login de imobiliária.</p>

      <form class="space-y-4" @submit.prevent="onSubmit">
        <div>
          <label class="mb-1 block text-sm font-medium text-slate-300" for="email">E-mail</label>
          <input
            id="email"
            v-model="form.email"
            type="email"
            required
            autocomplete="username"
            class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium text-slate-300" for="senha">Senha</label>
          <input
            id="senha"
            v-model="form.senha"
            type="password"
            required
            autocomplete="current-password"
            class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        <p v-if="auth.error" class="text-sm text-red-400" role="alert">{{ auth.error }}</p>

        <button
          type="submit"
          :disabled="auth.loading"
          class="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
        >
          {{ auth.loading ? "Entrando…" : "Entrar" }}
        </button>
      </form>
    </div>
  </div>
</template>

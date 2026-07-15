<script setup>
import { reactive } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();

const form = reactive({
  nomeTenant: "",
  nome: "",
  email: "",
  senha: "",
});

async function onSubmit() {
  const ok = await auth.signup(form);
  if (ok) {
    router.push({ name: "home" });
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-900">
    <div class="w-full max-w-sm rounded-xl bg-white p-8 shadow-sm dark:bg-slate-800">
      <h1 class="mb-1 text-xl font-semibold text-slate-900 dark:text-white">Criar sua conta</h1>
      <p class="mb-6 text-sm text-slate-500 dark:text-slate-400">
        7 dias grátis, sem cartão de crédito.
      </p>

      <form class="space-y-4" @submit.prevent="onSubmit">
        <div>
          <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300" for="nome_tenant">
            Nome da imobiliária / carteira
          </label>
          <input
            id="nome_tenant"
            v-model="form.nomeTenant"
            type="text"
            required
            minlength="2"
            class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white"
          />
        </div>

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
          <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300" for="email">
            E-mail
          </label>
          <input
            id="email"
            v-model="form.email"
            type="email"
            required
            class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white"
          />
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300" for="senha">
            Senha
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

        <p v-if="auth.error" class="text-sm text-red-600" role="alert">{{ auth.error }}</p>

        <button
          type="submit"
          :disabled="auth.loading"
          class="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
        >
          {{ auth.loading ? "Criando conta…" : "Criar conta" }}
        </button>
      </form>

      <p class="mt-6 text-center text-sm text-slate-500 dark:text-slate-400">
        Já tem conta?
        <router-link class="font-medium text-primary" :to="{ name: 'login' }">Entrar</router-link>
      </p>
    </div>
  </div>
</template>

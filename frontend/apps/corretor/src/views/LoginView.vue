<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();

const form = reactive({
  email: "",
  senha: "",
  codigoTotp: "",
});

const showTotpField = ref(false);

async function onSubmit() {
  const ok = await auth.login(form);
  if (ok) {
    router.push({ name: "home" });
  } else {
    // Não dá pra saber pelo 401 se foi senha errada ou 2FA ausente/errado — revela o
    // campo de código para o usuário tentar de novo caso tenha 2FA ativo.
    showTotpField.value = true;
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-900">
    <div class="w-full max-w-sm rounded-xl bg-white p-8 shadow-sm dark:bg-slate-800">
      <h1 class="mb-6 text-xl font-semibold text-slate-900 dark:text-white">Entrar</h1>

      <form class="space-y-4" @submit.prevent="onSubmit">
        <div>
          <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300" for="email">
            E-mail
          </label>
          <input
            id="email"
            v-model="form.email"
            type="email"
            required
            autocomplete="username"
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
            autocomplete="current-password"
            class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white"
          />
        </div>

        <div v-if="showTotpField">
          <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300" for="codigo_totp">
            Código de autenticação (2FA) ou recovery code
          </label>
          <input
            id="codigo_totp"
            v-model="form.codigoTotp"
            type="text"
            inputmode="numeric"
            autocomplete="one-time-code"
            class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white"
          />
        </div>

        <p v-if="auth.error" class="text-sm text-red-600" role="alert">
          {{ auth.error }}
          <span v-if="!showTotpField">Se sua conta tem 2FA ativo, informe o código.</span>
        </p>

        <button
          type="submit"
          :disabled="auth.loading"
          class="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
        >
          {{ auth.loading ? "Entrando…" : "Entrar" }}
        </button>
      </form>

      <p class="mt-6 text-center text-sm text-slate-500 dark:text-slate-400">
        Ainda não tem conta?
        <router-link class="font-medium text-primary" :to="{ name: 'signup' }">Criar conta grátis</router-link>
      </p>
    </div>
  </div>
</template>

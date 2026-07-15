<script setup>
import { ref } from "vue";
import api from "../api/client";

const step = ref("intro"); // intro -> qrcode -> done
const qrcodeSrc = ref("");
const codigo = ref("");
const recoveryCodes = ref([]);
const error = ref("");
const loading = ref(false);

async function iniciarSetup() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await api.post("/auth/2fa/setup");
    qrcodeSrc.value = `data:image/png;base64,${data.qrcode_png_base64}`;
    step.value = "qrcode";
  } catch {
    error.value = "Não foi possível iniciar o setup de 2FA. Tente novamente.";
  } finally {
    loading.value = false;
  }
}

async function confirmarCodigo() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await api.post("/auth/2fa/verify", { codigo: codigo.value });
    recoveryCodes.value = data.recovery_codes;
    step.value = "done";
  } catch {
    error.value = "Código inválido. Confira o app autenticador e tente de novo.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="mx-auto max-w-md p-6">
    <h1 class="mb-4 text-xl font-semibold text-slate-900 dark:text-white">
      Autenticação de dois fatores (2FA)
    </h1>

    <div v-if="step === 'intro'" class="space-y-4">
      <p class="text-sm text-slate-600 dark:text-slate-300">
        Como <strong>admin</strong>, você precisa ativar o 2FA para convidar corretores,
        mudar de plano ou ver faturas.
      </p>
      <button
        class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        :disabled="loading"
        @click="iniciarSetup"
      >
        {{ loading ? "Gerando…" : "Começar" }}
      </button>
    </div>

    <div v-else-if="step === 'qrcode'" class="space-y-4">
      <p class="text-sm text-slate-600 dark:text-slate-300">
        Escaneie o QR code com seu app autenticador (Google Authenticator, Authy, etc.) e
        informe o código de 6 dígitos gerado.
      </p>
      <img :src="qrcodeSrc" alt="QR code do 2FA" class="mx-auto h-48 w-48 rounded-md border" />
      <input
        v-model="codigo"
        type="text"
        inputmode="numeric"
        maxlength="6"
        placeholder="000000"
        class="w-full rounded-md border border-slate-300 px-3 py-2 text-center text-lg tracking-widest dark:border-slate-600 dark:bg-slate-700 dark:text-white"
      />
      <p v-if="error" class="text-sm text-red-600" role="alert">{{ error }}</p>
      <button
        class="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        :disabled="loading || codigo.length !== 6"
        @click="confirmarCodigo"
      >
        {{ loading ? "Confirmando…" : "Ativar 2FA" }}
      </button>
    </div>

    <div v-else class="space-y-4">
      <p class="text-sm font-medium text-emerald-700 dark:text-emerald-400">
        2FA ativado! Guarde estes recovery codes — cada um só funciona uma vez e é a única
        forma de entrar se você perder o app autenticador.
      </p>
      <ul class="grid grid-cols-2 gap-2 rounded-md bg-slate-100 p-4 font-mono text-sm dark:bg-slate-700 dark:text-white">
        <li v-for="code in recoveryCodes" :key="code">{{ code }}</li>
      </ul>
      <router-link :to="{ name: 'home' }" class="inline-block text-sm font-medium text-primary">
        Concluir
      </router-link>
    </div>
  </div>
</template>

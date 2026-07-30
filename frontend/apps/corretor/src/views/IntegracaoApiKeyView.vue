<script setup>
import { onMounted, ref } from "vue";
import api from "../api/client";

const status = ref(null);
const chaveGerada = ref("");
const loading = ref(true);
const gerando = ref(false);
const erro = ref("");

async function carregarStatus() {
  loading.value = true;
  erro.value = "";
  try {
    const { data } = await api.get("/leads/integracao/api-key");
    status.value = data;
  } catch {
    erro.value = "Não foi possível carregar o status da API key.";
  } finally {
    loading.value = false;
  }
}

async function gerar() {
  if (
    status.value?.existe &&
    !confirm("Gerar uma nova chave invalida a anterior imediatamente. Continuar?")
  ) {
    return;
  }
  gerando.value = true;
  erro.value = "";
  try {
    const { data } = await api.post("/leads/integracao/api-key");
    chaveGerada.value = data.api_key;
    await carregarStatus();
  } catch {
    erro.value = "Não foi possível gerar a API key.";
  } finally {
    gerando.value = false;
  }
}

function formatarData(valor) {
  return valor ? new Date(valor).toLocaleString("pt-BR") : "—";
}

// A URL do feed usa o mesmo host que o navegador já está acessando — é sempre o subdomínio do
// tenant logado, o mesmo mecanismo de resolução por Host header da página pública do imóvel.
const feedUrl = `${window.location.origin}/api/v1/imoveis/publico/feed.xml`;

onMounted(carregarStatus);
</script>

<template>
  <div class="mx-auto max-w-2xl p-6">
    <h1 class="mb-2 text-xl font-semibold text-slate-900 dark:text-white">Integração — Webhook de Leads</h1>
    <p class="mb-6 text-sm text-slate-500 dark:text-slate-400">
      Use esta chave para conectar landing pages e ferramentas de campanha ao endpoint
      <code class="rounded bg-slate-100 px-1 py-0.5 dark:bg-slate-800">POST /api/v1/webhooks/leads</code>
      (header <code class="rounded bg-slate-100 px-1 py-0.5 dark:bg-slate-800">X-API-Key</code>).
    </p>

    <p v-if="erro" class="mb-4 text-sm text-red-600" role="alert">{{ erro }}</p>
    <p v-if="loading">Carregando…</p>

    <template v-else>
      <div class="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
        <p class="text-sm text-slate-700 dark:text-slate-300">
          Status: <strong>{{ status.existe ? "chave ativa" : "nenhuma chave gerada" }}</strong>
        </p>
        <p v-if="status.existe" class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Gerada em {{ formatarData(status.created_at) }} · último uso: {{ formatarData(status.last_used_at) }}
        </p>

        <button
          class="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
          :disabled="gerando"
          @click="gerar"
        >
          {{ gerando ? "Gerando…" : status.existe ? "Gerar nova chave (invalida a atual)" : "Gerar chave" }}
        </button>
      </div>

      <div
        v-if="chaveGerada"
        class="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-4 dark:border-amber-700 dark:bg-amber-900/20"
      >
        <p class="text-sm font-medium text-amber-800 dark:text-amber-300">
          Copie agora — esta chave não será mostrada novamente:
        </p>
        <code class="mt-2 block break-all rounded bg-white p-2 text-sm dark:bg-slate-800 dark:text-white">
          {{ chaveGerada }}
        </code>
      </div>
    </template>

    <div class="mt-8 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
      <h2 class="text-lg font-semibold text-slate-900 dark:text-white">Feed de anúncios (ZAP/Viva Real)</h2>
      <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
        Cadastre esta URL no Canal Pro (Grupo OLX), na opção "Desenvolvedor Próprio", para
        publicar e atualizar seus imóveis disponíveis automaticamente no ZAP e Viva Real.
      </p>
      <code class="mt-3 block break-all rounded bg-slate-100 p-2 text-sm dark:bg-slate-800 dark:text-white">
        {{ feedUrl }}
      </code>
      <p class="mt-3 text-sm text-amber-700 dark:text-amber-400">
        Antes de cadastrar de verdade no Canal Pro, valide o XML no
        <a href="https://developers.grupozap.com/feeds/xml_validator/" target="_blank" rel="noopener" class="underline">
          Validador XML oficial do Grupo OLX
        </a>.
      </p>
    </div>
  </div>
</template>

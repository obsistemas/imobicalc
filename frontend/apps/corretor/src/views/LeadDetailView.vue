<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import api from "../api/client";

const route = useRoute();
const leadId = route.params.id;

const lead = ref(null);
const notas = ref([]);
const loading = ref(true);
const erro = ref("");

const novoEstagio = ref("");
const movendo = ref(false);
const erroMovimentacao = ref("");

const textoNota = ref("");
const salvandoNota = ref(false);

const ESTAGIO_COR = {
  novo: "bg-blue-100 text-blue-800",
  contatado: "bg-amber-100 text-amber-800",
  visita: "bg-purple-100 text-purple-800",
  proposta: "bg-indigo-100 text-indigo-800",
  fechado: "bg-emerald-100 text-emerald-800",
  perdido: "bg-red-100 text-red-800",
};
const ESTAGIOS = ["novo", "contatado", "visita", "proposta", "fechado", "perdido"];
const ESTAGIOS_TERMINAIS = ["fechado", "perdido"];

const ehTerminal = computed(() => lead.value && ESTAGIOS_TERMINAIS.includes(lead.value.estagio));
const opcoesEstagio = computed(() => ESTAGIOS.filter((e) => e !== lead.value?.estagio));

async function carregar() {
  loading.value = true;
  erro.value = "";
  try {
    const [leadResp, notasResp] = await Promise.all([
      api.get(`/leads/${leadId}`),
      api.get(`/leads/${leadId}/notas`),
    ]);
    lead.value = leadResp.data;
    notas.value = notasResp.data;
  } catch {
    erro.value = "Não foi possível carregar o lead.";
  } finally {
    loading.value = false;
  }
}

async function moverEstagio() {
  if (!novoEstagio.value) return;
  movendo.value = true;
  erroMovimentacao.value = "";
  try {
    const { data } = await api.put(`/leads/${leadId}/estagio`, { estagio: novoEstagio.value });
    lead.value = data;
    novoEstagio.value = "";
    const { data: notasAtualizadas } = await api.get(`/leads/${leadId}/notas`);
    notas.value = notasAtualizadas;
  } catch (err) {
    erroMovimentacao.value = err.response?.data?.detail ?? "Não foi possível mover o estágio.";
  } finally {
    movendo.value = false;
  }
}

async function adicionarNota() {
  if (!textoNota.value.trim()) return;
  salvandoNota.value = true;
  try {
    await api.post(`/leads/${leadId}/notas`, { texto: textoNota.value });
    textoNota.value = "";
    const { data } = await api.get(`/leads/${leadId}/notas`);
    notas.value = data;
  } catch {
    // erro ao salvar nota fica implícito — o campo simplesmente não é limpo
  } finally {
    salvandoNota.value = false;
  }
}

onMounted(carregar);
</script>

<template>
  <div class="mx-auto max-w-2xl p-6">
    <p v-if="loading">Carregando…</p>
    <p v-else-if="erro" class="text-sm text-red-600" role="alert">{{ erro }}</p>

    <template v-else-if="lead">
      <div class="mb-6 flex items-center justify-between">
        <h1 class="text-xl font-semibold text-slate-900 dark:text-white">{{ lead.nome }}</h1>
        <span class="rounded-full px-3 py-1 text-sm font-medium" :class="ESTAGIO_COR[lead.estagio]">
          {{ lead.estagio }}
        </span>
      </div>

      <p class="text-sm text-slate-600 dark:text-slate-300">
        {{ lead.email || "sem e-mail" }} · {{ lead.telefone || "sem telefone" }} · origem: {{ lead.origem }}
      </p>

      <div class="mt-6 rounded-lg border border-slate-200 p-4 dark:border-slate-700">
        <p v-if="ehTerminal" class="text-sm text-slate-500 dark:text-slate-400">
          Lead em estágio terminal — não pode ser reaberto.
        </p>
        <div v-else class="flex flex-wrap items-end gap-3">
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Mover para</label>
            <select v-model="novoEstagio" class="input">
              <option value="" disabled>Selecione…</option>
              <option v-for="opcao in opcoesEstagio" :key="opcao" :value="opcao">{{ opcao }}</option>
            </select>
          </div>
          <button
            :disabled="!novoEstagio || movendo"
            class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            @click="moverEstagio"
          >
            {{ movendo ? "Movendo…" : "Mover estágio" }}
          </button>
        </div>
        <p v-if="erroMovimentacao" class="mt-2 text-sm text-red-600" role="alert">{{ erroMovimentacao }}</p>
      </div>

      <div class="mt-8">
        <h2 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Notas e histórico
        </h2>

        <form class="mb-4 flex gap-2" @submit.prevent="adicionarNota">
          <input v-model="textoNota" placeholder="Adicionar nota…" class="input flex-1" />
          <button
            type="submit"
            :disabled="salvandoNota"
            class="rounded-md border border-primary px-4 py-2 text-sm font-medium text-primary disabled:opacity-50"
          >
            Adicionar
          </button>
        </form>

        <ul class="space-y-2">
          <li v-for="nota in notas" :key="nota.id" class="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-700">
            <div class="flex items-center justify-between">
              <span :class="nota.automatica ? 'text-slate-500 dark:text-slate-400 italic' : 'text-slate-900 dark:text-white'">
                {{ nota.texto }}
              </span>
              <span class="text-xs text-slate-400">{{ new Date(nota.created_at).toLocaleString("pt-BR") }}</span>
            </div>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>

<style scoped>
.input {
  @apply rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white;
}
</style>

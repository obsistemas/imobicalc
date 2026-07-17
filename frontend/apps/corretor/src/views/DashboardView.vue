<script setup>
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Title,
  Tooltip,
} from "chart.js";
import { computed, onMounted, ref } from "vue";
import { Bar, Doughnut } from "vue-chartjs";
import api from "../api/client";

ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, ArcElement);

const MESES_NOMES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
const CORES_ORIGEM = ["#6366f1", "#f59e0b", "#10b981", "#ef4444", "#64748b"];

const meses = ref(12);
const resumo = ref(null);
const vendas = ref([]);
const leadsOrigem = ref([]);
const loading = ref(true);
const erro = ref("");

async function carregar() {
  loading.value = true;
  erro.value = "";
  try {
    const params = { meses: meses.value };
    const [resumoResp, vendasResp, origemResp] = await Promise.all([
      api.get("/dashboard/resumo", { params }),
      api.get("/dashboard/vendas-por-mes", { params }),
      api.get("/dashboard/leads-por-origem", { params }),
    ]);
    resumo.value = resumoResp.data;
    vendas.value = vendasResp.data;
    leadsOrigem.value = origemResp.data;
  } catch {
    erro.value = "Não foi possível carregar o dashboard.";
  } finally {
    loading.value = false;
  }
}

function formatarMoeda(valor) {
  if (valor === null || valor === undefined) return "—";
  return Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatarDias(valor) {
  return valor === null || valor === undefined ? "—" : `${Math.round(valor)} dias`;
}

const dadosVendas = computed(() => ({
  labels: vendas.value.map((v) => `${MESES_NOMES[v.mes - 1]}/${String(v.ano).slice(2)}`),
  datasets: [{ label: "Imóveis vendidos", data: vendas.value.map((v) => v.quantidade), backgroundColor: "#6366f1" }],
}));

const dadosOrigem = computed(() => ({
  labels: leadsOrigem.value.map((o) => o.origem),
  datasets: [{ data: leadsOrigem.value.map((o) => o.quantidade), backgroundColor: CORES_ORIGEM }],
}));

const opcoesGrafico = { responsive: true, maintainAspectRatio: false };

onMounted(carregar);
</script>

<template>
  <div class="mx-auto max-w-5xl p-6">
    <div class="mb-6 flex items-center justify-between">
      <h1 class="text-xl font-semibold text-slate-900 dark:text-white">Dashboard</h1>
      <div class="flex items-center gap-3">
        <select v-model.number="meses" class="input" @change="carregar">
          <option :value="3">Últimos 3 meses</option>
          <option :value="6">Últimos 6 meses</option>
          <option :value="12">Últimos 12 meses</option>
        </select>
        <button class="rounded-md border border-primary px-3 py-2 text-sm font-medium text-primary" @click="carregar">
          Atualizar
        </button>
      </div>
    </div>

    <p v-if="erro" class="text-sm text-red-600" role="alert">{{ erro }}</p>
    <p v-if="loading">Carregando…</p>

    <template v-else-if="resumo">
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <router-link
          v-for="(quantidade, status) in resumo.imoveis_por_status"
          :key="status"
          :to="{ name: 'imoveis', query: { status } }"
          class="rounded-xl border border-slate-200 p-4 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
        >
          <p class="text-2xl font-bold text-slate-900 dark:text-white">{{ quantidade }}</p>
          <p class="text-sm capitalize text-slate-500 dark:text-slate-400">Imóveis {{ status }}</p>
        </router-link>

        <router-link
          :to="{ name: 'leads', query: { estagio: 'novo' } }"
          class="rounded-xl border p-4 hover:bg-slate-50 dark:hover:bg-slate-800"
          :class="
            resumo.leads_sem_contato > 0
              ? 'border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-900/20'
              : 'border-slate-200 dark:border-slate-700'
          "
        >
          <p class="text-2xl font-bold text-slate-900 dark:text-white">{{ resumo.leads_sem_contato }}</p>
          <p class="text-sm text-slate-500 dark:text-slate-400">Leads sem contato há dias</p>
        </router-link>

        <router-link
          :to="{ name: 'leads' }"
          class="rounded-xl border border-slate-200 p-4 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
        >
          <p class="text-2xl font-bold text-slate-900 dark:text-white">{{ resumo.leads_ativos }}</p>
          <p class="text-sm text-slate-500 dark:text-slate-400">Leads ativos</p>
        </router-link>

        <div class="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
          <p class="text-2xl font-bold text-slate-900 dark:text-white">{{ (resumo.taxa_conversao * 100).toFixed(0) }}%</p>
          <p class="text-sm text-slate-500 dark:text-slate-400">Taxa de conversão</p>
        </div>

        <div class="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
          <p class="text-2xl font-bold text-slate-900 dark:text-white">{{ formatarMoeda(resumo.ticket_medio) }}</p>
          <p class="text-sm text-slate-500 dark:text-slate-400">Ticket médio</p>
        </div>

        <div class="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
          <p class="text-2xl font-bold text-slate-900 dark:text-white">
            {{ formatarDias(resumo.tempo_medio_venda_imovel_dias) }}
          </p>
          <p class="text-sm text-slate-500 dark:text-slate-400">Tempo médio de venda</p>
        </div>

        <div class="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
          <p class="text-2xl font-bold text-slate-900 dark:text-white">
            {{ formatarDias(resumo.tempo_medio_fechamento_lead_dias) }}
          </p>
          <p class="text-sm text-slate-500 dark:text-slate-400">Tempo médio de fechamento</p>
        </div>
      </div>

      <div class="mt-8 grid gap-6 lg:grid-cols-2">
        <div class="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
          <h2 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Vendas por mês
          </h2>
          <div class="h-64">
            <Bar :data="dadosVendas" :options="opcoesGrafico" />
          </div>
        </div>

        <div class="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
          <h2 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Leads por origem
          </h2>
          <div class="h-64">
            <Doughnut v-if="leadsOrigem.length" :data="dadosOrigem" :options="opcoesGrafico" />
            <p v-else class="text-sm text-slate-500 dark:text-slate-400">Nenhum lead no período.</p>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.input {
  @apply rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white;
}
</style>

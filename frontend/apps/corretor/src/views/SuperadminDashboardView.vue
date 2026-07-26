<script setup>
import { onMounted, ref } from "vue";
import adminApi from "../api/adminClient";
import { useSuperadminAuthStore } from "../stores/superadmin";

const auth = useSuperadminAuthStore();

const uso = ref(null);
const faturamento = ref(null);
const loading = ref(true);
const erro = ref("");

const STATUS_LABEL = {
  trial: "Trial",
  active: "Ativos",
  past_due: "Inadimplentes",
  suspended: "Suspensos",
  cancelled: "Cancelados",
};

function formatarMoeda(valor) {
  return Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

async function carregar() {
  loading.value = true;
  erro.value = "";
  try {
    const [usoResp, faturamentoResp] = await Promise.all([
      adminApi.get("/uso/plataforma"),
      adminApi.get("/faturamento/consolidado"),
    ]);
    uso.value = usoResp.data;
    faturamento.value = faturamentoResp.data;
  } catch {
    erro.value = "Não foi possível carregar o dashboard.";
  } finally {
    loading.value = false;
  }
}

onMounted(carregar);
</script>

<template>
  <div class="min-h-screen bg-slate-950 p-6 text-white">
    <div class="mx-auto max-w-5xl">
      <div class="mb-6 flex items-center justify-between">
        <h1 class="text-xl font-semibold">Dashboard da plataforma</h1>
        <nav class="flex items-center gap-4 text-sm">
          <router-link :to="{ name: 'admin-tenants' }" class="text-primary">Tenants</router-link>
          <router-link :to="{ name: 'admin-auditoria' }" class="text-primary">Auditoria</router-link>
          <button class="text-slate-400 hover:text-white" @click="auth.logout()">Sair</button>
        </nav>
      </div>

      <p v-if="erro" class="text-sm text-red-400" role="alert">{{ erro }}</p>
      <p v-if="loading">Carregando…</p>

      <template v-else-if="uso && faturamento">
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div v-for="(quantidade, status) in uso.tenants_por_status" :key="status" class="rounded-xl border border-slate-800 p-4">
            <p class="text-2xl font-bold">{{ quantidade }}</p>
            <p class="text-sm text-slate-400">{{ STATUS_LABEL[status] ?? status }}</p>
          </div>
        </div>

        <div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div class="rounded-xl border border-slate-800 p-4">
            <p class="text-2xl font-bold">{{ formatarMoeda(faturamento.mrr) }}</p>
            <p class="text-sm text-slate-400">MRR (licenças ativas)</p>
          </div>
          <div class="rounded-xl border border-slate-800 p-4">
            <p class="text-2xl font-bold">{{ formatarMoeda(faturamento.receita_paga_mes_atual) }}</p>
            <p class="text-sm text-slate-400">Receita paga no mês</p>
          </div>
          <div class="rounded-xl border border-slate-800 p-4">
            <p class="text-2xl font-bold">{{ uso.total_usuarios }}</p>
            <p class="text-sm text-slate-400">Usuários na plataforma</p>
          </div>
        </div>

        <div class="mt-8 grid gap-4 sm:grid-cols-3">
          <div class="rounded-xl border border-slate-800 p-4">
            <p class="text-2xl font-bold">{{ uso.total_imoveis }}</p>
            <p class="text-sm text-slate-400">Imóveis ativos</p>
          </div>
          <div class="rounded-xl border border-slate-800 p-4">
            <p class="text-2xl font-bold">{{ uso.total_leads }}</p>
            <p class="text-sm text-slate-400">Leads</p>
          </div>
          <div class="rounded-xl border border-slate-800 p-4">
            <p class="text-2xl font-bold">{{ uso.total_avaliacoes }}</p>
            <p class="text-sm text-slate-400">Avaliações</p>
          </div>
        </div>

        <div class="mt-8">
          <h2 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Invoices por status</h2>
          <div class="flex flex-wrap gap-4">
            <div v-for="(quantidade, status) in faturamento.invoices_por_status" :key="status" class="rounded-lg border border-slate-800 px-4 py-2 text-sm">
              <span class="font-semibold">{{ quantidade }}</span> {{ status }}
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

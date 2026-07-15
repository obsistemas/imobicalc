<script setup>
import { onMounted, ref } from "vue";
import api from "../api/client";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const license = ref(null);
const planos = ref([]);
const loading = ref(true);
const upgrading = ref(null); // uuid do plano em andamento
const erro = ref("");

async function carregar() {
  loading.value = true;
  try {
    const [licenseResp, planosResp] = await Promise.all([api.get("/license"), api.get("/plans")]);
    license.value = licenseResp.data;
    planos.value = planosResp.data;
  } catch {
    erro.value = "Não foi possível carregar os planos.";
  } finally {
    loading.value = false;
  }
}

async function upgrade(planoId) {
  upgrading.value = planoId;
  erro.value = "";
  try {
    const { data } = await api.post("/license/upgrade", { plan_id: planoId });
    license.value = data;
  } catch (err) {
    erro.value = err.response?.status === 403 ? "Apenas admin pode mudar de plano." : "Não foi possível mudar de plano.";
  } finally {
    upgrading.value = null;
  }
}

function formatarLimite(valor) {
  return valor === null ? "Ilimitado" : valor;
}

onMounted(carregar);
</script>

<template>
  <div class="mx-auto max-w-3xl p-6">
    <h1 class="mb-1 text-xl font-semibold text-slate-900 dark:text-white">Plano e assinatura</h1>
    <p v-if="license" class="mb-6 text-sm text-slate-500 dark:text-slate-400">
      Plano atual: <strong>{{ license.plan.nome }}</strong> — status:
      <span
        class="rounded-full px-2 py-0.5 text-xs font-medium"
        :class="{
          'bg-amber-100 text-amber-800': license.status === 'trial',
          'bg-emerald-100 text-emerald-800': license.status === 'active',
          'bg-red-100 text-red-800': ['past_due', 'suspended'].includes(license.status),
        }"
      >
        {{ license.status }}
      </span>
      <span v-if="license.status === 'trial' && license.trial_termina_em">
        — trial termina em {{ new Date(license.trial_termina_em).toLocaleDateString("pt-BR") }}
      </span>
    </p>

    <p v-if="erro" class="mb-4 text-sm text-red-600" role="alert">{{ erro }}</p>
    <p v-if="loading">Carregando…</p>

    <div v-else class="grid gap-4 sm:grid-cols-3">
      <div
        v-for="plano in planos"
        :key="plano.id"
        class="rounded-xl border border-slate-200 p-5 dark:border-slate-700"
        :class="{ 'border-primary ring-1 ring-primary': license?.plan?.nome === plano.nome }"
      >
        <h2 class="text-lg font-semibold capitalize text-slate-900 dark:text-white">{{ plano.nome }}</h2>
        <p class="mt-1 text-2xl font-bold text-slate-900 dark:text-white">
          {{ plano.nome === "enterprise" ? "sob consulta" : `R$ ${plano.preco_mensal}/mês` }}
        </p>
        <ul class="mt-4 space-y-1 text-sm text-slate-600 dark:text-slate-300">
          <li>{{ formatarLimite(plano.max_users) }} usuário(s)</li>
          <li>{{ formatarLimite(plano.max_imoveis) }} imóveis</li>
        </ul>
        <button
          v-if="auth.isAdmin && license?.plan?.nome !== plano.nome"
          class="mt-4 w-full rounded-md bg-primary px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          :disabled="upgrading === plano.id"
          @click="upgrade(plano.id)"
        >
          {{ upgrading === plano.id ? "Mudando…" : "Escolher este plano" }}
        </button>
        <p v-else-if="license?.plan?.nome === plano.nome" class="mt-4 text-center text-sm text-slate-400">
          Plano atual
        </p>
      </div>
    </div>
  </div>
</template>

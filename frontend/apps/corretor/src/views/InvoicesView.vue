<script setup>
import { onMounted, ref } from "vue";
import api from "../api/client";

const faturas = ref([]);
const loading = ref(true);
const erro = ref("");

const statusLabel = {
  pending: "Pendente",
  paid: "Paga",
  failed: "Falhou",
  refunded: "Estornada",
};

onMounted(async () => {
  try {
    const { data } = await api.get("/invoices");
    faturas.value = data;
  } catch {
    erro.value = "Apenas admin pode ver as faturas.";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="mx-auto max-w-2xl p-6">
    <h1 class="mb-4 text-xl font-semibold text-slate-900 dark:text-white">Faturas</h1>

    <p v-if="erro" class="text-sm text-red-600" role="alert">{{ erro }}</p>
    <p v-else-if="loading">Carregando…</p>
    <p v-else-if="faturas.length === 0" class="text-sm text-slate-500 dark:text-slate-400">
      Nenhuma fatura ainda — tenants em trial não têm cobrança.
    </p>

    <table v-else class="w-full text-left text-sm">
      <thead class="text-slate-500 dark:text-slate-400">
        <tr>
          <th class="py-2">Ciclo</th>
          <th class="py-2">Valor</th>
          <th class="py-2">Status</th>
          <th class="py-2">Vencimento</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="fatura in faturas" :key="fatura.id" class="border-t border-slate-100 dark:border-slate-700">
          <td class="py-2">{{ fatura.ciclo_mes }}/{{ fatura.ciclo_ano }}</td>
          <td class="py-2">R$ {{ fatura.valor }}</td>
          <td class="py-2">{{ statusLabel[fatura.status] ?? fatura.status }}</td>
          <td class="py-2">{{ new Date(fatura.vencimento).toLocaleDateString("pt-BR") }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

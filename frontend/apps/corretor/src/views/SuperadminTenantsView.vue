<script setup>
import { onMounted, ref } from "vue";
import adminApi from "../api/adminClient";
import { useSuperadminAuthStore } from "../stores/superadmin";

const auth = useSuperadminAuthStore();

const tenants = ref([]);
const loading = ref(true);
const erro = ref("");
const acaoEmAndamentoId = ref(null);

async function carregar() {
  loading.value = true;
  erro.value = "";
  try {
    const { data } = await adminApi.get("/tenants");
    tenants.value = data;
  } catch {
    erro.value = "Não foi possível carregar os tenants.";
  } finally {
    loading.value = false;
  }
}

async function alternarStatus(tenant) {
  const acao = tenant.status === "suspended" ? "reativar" : "suspender";
  if (acao === "suspender" && !confirm(`Suspender "${tenant.nome}"? O acesso de todos os usuários é bloqueado imediatamente.`)) {
    return;
  }
  acaoEmAndamentoId.value = tenant.id;
  try {
    await adminApi.post(`/tenants/${tenant.id}/${acao}`);
    await carregar();
  } catch {
    erro.value = `Não foi possível ${acao} o tenant.`;
  } finally {
    acaoEmAndamentoId.value = null;
  }
}

onMounted(carregar);
</script>

<template>
  <div class="min-h-screen bg-slate-950 p-6 text-white">
    <div class="mx-auto max-w-5xl">
      <div class="mb-6 flex items-center justify-between">
        <h1 class="text-xl font-semibold">Tenants</h1>
        <nav class="flex items-center gap-4 text-sm">
          <router-link :to="{ name: 'admin-dashboard' }" class="text-primary">Dashboard</router-link>
          <router-link :to="{ name: 'admin-auditoria' }" class="text-primary">Auditoria</router-link>
          <button class="text-slate-400 hover:text-white" @click="auth.logout()">Sair</button>
        </nav>
      </div>

      <p v-if="erro" class="text-sm text-red-400" role="alert">{{ erro }}</p>
      <p v-if="loading">Carregando…</p>

      <table v-else class="w-full text-left text-sm">
        <thead class="text-slate-400">
          <tr class="border-b border-slate-800">
            <th class="py-2">Nome</th>
            <th class="py-2">Slug</th>
            <th class="py-2">Status</th>
            <th class="py-2">Plano</th>
            <th class="py-2">Criado em</th>
            <th class="py-2"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="tenant in tenants" :key="tenant.id" class="border-b border-slate-900">
            <td class="py-2">{{ tenant.nome }}</td>
            <td class="py-2 text-slate-400">{{ tenant.slug }}</td>
            <td class="py-2">
              <span
                class="rounded-full px-2 py-0.5 text-xs"
                :class="tenant.status === 'suspended' ? 'bg-red-900 text-red-300' : 'bg-slate-800 text-slate-300'"
              >
                {{ tenant.status }}
              </span>
            </td>
            <td class="py-2 text-slate-400">{{ tenant.plano ?? "—" }}</td>
            <td class="py-2 text-slate-400">{{ new Date(tenant.criado_em).toLocaleDateString("pt-BR") }}</td>
            <td class="py-2 text-right">
              <button
                :disabled="acaoEmAndamentoId === tenant.id"
                class="rounded-md border border-slate-700 px-3 py-1 text-xs hover:bg-slate-800 disabled:opacity-50"
                @click="alternarStatus(tenant)"
              >
                {{ tenant.status === "suspended" ? "Reativar" : "Suspender" }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import adminApi from "../api/adminClient";
import { useSuperadminAuthStore } from "../stores/superadmin";

const auth = useSuperadminAuthStore();

const logs = ref([]);
const loading = ref(true);
const erro = ref("");

const filtros = reactive({
  tenant_id: "",
  acao: "",
  desde: "",
  ate: "",
});

async function carregar() {
  loading.value = true;
  erro.value = "";
  try {
    const params = Object.fromEntries(Object.entries(filtros).filter(([, v]) => v));
    const { data } = await adminApi.get("/auditoria/logs", { params });
    logs.value = data;
  } catch {
    erro.value = "Não foi possível carregar os logs.";
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
        <h1 class="text-xl font-semibold">Auditoria (todos os tenants)</h1>
        <nav class="flex items-center gap-4 text-sm">
          <router-link :to="{ name: 'admin-dashboard' }" class="text-primary">Dashboard</router-link>
          <router-link :to="{ name: 'admin-tenants' }" class="text-primary">Tenants</router-link>
          <button class="text-slate-400 hover:text-white" @click="auth.logout()">Sair</button>
        </nav>
      </div>

      <form class="mb-6 flex flex-wrap items-end gap-3 text-sm" @submit.prevent="carregar">
        <div>
          <label class="mb-1 block text-slate-400" for="tenant_id">Tenant ID</label>
          <input id="tenant_id" v-model="filtros.tenant_id" class="input" placeholder="uuid" />
        </div>
        <div>
          <label class="mb-1 block text-slate-400" for="acao">Ação</label>
          <input id="acao" v-model="filtros.acao" class="input" placeholder="ex.: tenant_suspenso_por_superadmin" />
        </div>
        <div>
          <label class="mb-1 block text-slate-400" for="desde">Desde</label>
          <input id="desde" v-model="filtros.desde" type="date" class="input" />
        </div>
        <div>
          <label class="mb-1 block text-slate-400" for="ate">Até</label>
          <input id="ate" v-model="filtros.ate" type="date" class="input" />
        </div>
        <button type="submit" class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white">Filtrar</button>
      </form>

      <p v-if="erro" class="text-sm text-red-400" role="alert">{{ erro }}</p>
      <p v-if="loading">Carregando…</p>

      <table v-else class="w-full text-left text-sm">
        <thead class="text-slate-400">
          <tr class="border-b border-slate-800">
            <th class="py-2">Quando</th>
            <th class="py-2">Tenant</th>
            <th class="py-2">Ação</th>
            <th class="py-2">Entidade</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in logs" :key="log.id" class="border-b border-slate-900">
            <td class="py-2 text-slate-400">{{ new Date(log.created_at).toLocaleString("pt-BR") }}</td>
            <td class="py-2 text-slate-400">{{ log.tenant_id }}</td>
            <td class="py-2">{{ log.acao }}</td>
            <td class="py-2 text-slate-400">{{ log.entidade }}:{{ log.entidade_id }}</td>
          </tr>
          <tr v-if="logs.length === 0">
            <td colspan="4" class="py-4 text-center text-slate-500">Nenhum log encontrado para o filtro atual.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.input {
  @apply rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary;
}
</style>

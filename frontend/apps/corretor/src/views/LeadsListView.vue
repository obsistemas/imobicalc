<script setup>
import { onMounted, reactive, ref } from "vue";
import api from "../api/client";

const leads = ref([]);
const loading = ref(true);
const erro = ref("");

const filtros = reactive({ estagio: "", origem: "" });

const ESTAGIO_COR = {
  novo: "bg-blue-100 text-blue-800",
  contatado: "bg-amber-100 text-amber-800",
  visita: "bg-purple-100 text-purple-800",
  proposta: "bg-indigo-100 text-indigo-800",
  fechado: "bg-emerald-100 text-emerald-800",
  perdido: "bg-red-100 text-red-800",
};

async function carregar() {
  loading.value = true;
  erro.value = "";
  try {
    const params = Object.fromEntries(Object.entries(filtros).filter(([, v]) => v !== ""));
    const { data } = await api.get("/leads", { params });
    leads.value = data;
  } catch {
    erro.value = "Não foi possível carregar os leads.";
  } finally {
    loading.value = false;
  }
}

onMounted(carregar);
</script>

<template>
  <div class="mx-auto max-w-4xl p-6">
    <div class="mb-6 flex items-center justify-between">
      <h1 class="text-xl font-semibold text-slate-900 dark:text-white">Leads</h1>
      <router-link :to="{ name: 'lead-novo' }" class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white">
        + Novo lead
      </router-link>
    </div>

    <form class="mb-6 grid gap-3 sm:grid-cols-3" @submit.prevent="carregar">
      <select v-model="filtros.estagio" class="input">
        <option value="">Estágio (todos)</option>
        <option value="novo">Novo</option>
        <option value="contatado">Contatado</option>
        <option value="visita">Visita</option>
        <option value="proposta">Proposta</option>
        <option value="fechado">Fechado</option>
        <option value="perdido">Perdido</option>
      </select>
      <select v-model="filtros.origem" class="input">
        <option value="">Origem (todas)</option>
        <option value="site">Site</option>
        <option value="indicacao">Indicação</option>
        <option value="portal">Portal</option>
        <option value="redes_sociais">Redes sociais</option>
        <option value="outro">Outro</option>
      </select>
      <button type="submit" class="rounded-md border border-primary px-4 py-2 text-sm font-medium text-primary">
        Filtrar
      </button>
    </form>

    <p v-if="erro" class="text-sm text-red-600" role="alert">{{ erro }}</p>
    <p v-if="loading">Carregando…</p>

    <template v-else>
      <p v-if="leads.length === 0" class="text-sm text-slate-500 dark:text-slate-400">Nenhum lead encontrado.</p>

      <ul v-else class="space-y-2">
        <li v-for="lead in leads" :key="lead.id">
          <router-link
            :to="{ name: 'lead-detalhe', params: { id: lead.id } }"
            class="flex items-center justify-between rounded-lg border border-slate-200 p-4 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            <div>
              <p class="font-medium text-slate-900 dark:text-white">{{ lead.nome }}</p>
              <p class="text-sm text-slate-500 dark:text-slate-400">{{ lead.email || lead.telefone || "sem contato" }} — {{ lead.origem }}</p>
            </div>
            <span class="rounded-full px-2 py-0.5 text-xs font-medium" :class="ESTAGIO_COR[lead.estagio]">
              {{ lead.estagio }}
            </span>
          </router-link>
        </li>
      </ul>
    </template>
  </div>
</template>

<style scoped>
.input {
  @apply rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white;
}
</style>

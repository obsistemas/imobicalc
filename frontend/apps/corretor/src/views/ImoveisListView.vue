<script setup>
import { onMounted, reactive, ref, watch } from "vue";
import api from "../api/client";

const imoveis = ref([]);
const total = ref(0);
const loading = ref(true);
const erro = ref("");

const filtros = reactive({
  status: "",
  tipo: "",
  bairro: "",
  cidade: "",
  valor_min: "",
  valor_max: "",
});

const pagina = reactive({ skip: 0, limit: 20 });

async function carregar() {
  loading.value = true;
  erro.value = "";
  try {
    const params = Object.fromEntries(
      Object.entries({ ...filtros, ...pagina }).filter(([, v]) => v !== "" && v !== null)
    );
    const { data } = await api.get("/imoveis", { params });
    imoveis.value = data.items;
    total.value = data.total;
  } catch {
    erro.value = "Não foi possível carregar os imóveis.";
  } finally {
    loading.value = false;
  }
}

function aplicarFiltros() {
  pagina.skip = 0;
  carregar();
}

function proximaPagina() {
  if (pagina.skip + pagina.limit < total.value) {
    pagina.skip += pagina.limit;
  }
}

function paginaAnterior() {
  pagina.skip = Math.max(0, pagina.skip - pagina.limit);
}

function formatarValor(valor) {
  if (valor === null || valor === undefined) return "—";
  return Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

watch(() => pagina.skip, carregar);
onMounted(carregar);
</script>

<template>
  <div class="mx-auto max-w-5xl p-6">
    <div class="mb-6 flex items-center justify-between">
      <h1 class="text-xl font-semibold text-slate-900 dark:text-white">Imóveis</h1>
      <router-link
        :to="{ name: 'imovel-novo' }"
        class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white"
      >
        + Novo imóvel
      </router-link>
    </div>

    <form class="mb-6 grid gap-3 sm:grid-cols-3 lg:grid-cols-6" @submit.prevent="aplicarFiltros">
      <select v-model="filtros.status" class="input">
        <option value="">Status (todos)</option>
        <option value="disponivel">Disponível</option>
        <option value="reservado">Reservado</option>
        <option value="vendido">Vendido</option>
        <option value="alugado">Alugado</option>
      </select>
      <select v-model="filtros.tipo" class="input">
        <option value="">Tipo (todos)</option>
        <option value="apartamento">Apartamento</option>
        <option value="casa">Casa</option>
        <option value="terreno">Terreno</option>
        <option value="comercial">Comercial</option>
        <option value="galpao">Galpão</option>
      </select>
      <input v-model="filtros.bairro" placeholder="Bairro" class="input" />
      <input v-model="filtros.cidade" placeholder="Cidade" class="input" />
      <input v-model="filtros.valor_min" type="number" placeholder="Valor mín." class="input" />
      <input v-model="filtros.valor_max" type="number" placeholder="Valor máx." class="input" />
      <button type="submit" class="col-span-full rounded-md border border-primary px-4 py-2 text-sm font-medium text-primary sm:col-span-1">
        Filtrar
      </button>
    </form>

    <p v-if="erro" class="text-sm text-red-600" role="alert">{{ erro }}</p>
    <p v-if="loading">Carregando…</p>

    <template v-else>
      <p v-if="total === 0" class="text-sm text-slate-500 dark:text-slate-400">Nenhum imóvel encontrado.</p>

      <div v-else class="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
        <table class="w-full text-left text-sm">
          <thead class="bg-slate-50 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            <tr>
              <th class="px-4 py-2">Título</th>
              <th class="px-4 py-2">Tipo</th>
              <th class="px-4 py-2">Bairro/Cidade</th>
              <th class="px-4 py-2">Valor</th>
              <th class="px-4 py-2">Status</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-700">
            <tr
              v-for="imovel in imoveis"
              :key="imovel.id"
              class="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800"
              @click="$router.push({ name: 'imovel-editar', params: { id: imovel.id } })"
            >
              <td class="px-4 py-2 text-slate-900 dark:text-white">{{ imovel.titulo }}</td>
              <td class="px-4 py-2 capitalize text-slate-600 dark:text-slate-300">{{ imovel.tipo }}</td>
              <td class="px-4 py-2 text-slate-600 dark:text-slate-300">{{ imovel.bairro }}, {{ imovel.cidade }}</td>
              <td class="px-4 py-2 text-slate-600 dark:text-slate-300">{{ formatarValor(imovel.valor_anunciado) }}</td>
              <td class="px-4 py-2 capitalize text-slate-600 dark:text-slate-300">{{ imovel.status }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="mt-4 flex items-center justify-between text-sm text-slate-500 dark:text-slate-400">
        <span>{{ total }} imóve{{ total === 1 ? "l" : "is" }} no total</span>
        <div class="flex gap-2">
          <button :disabled="pagina.skip === 0" class="rounded-md border border-slate-300 px-3 py-1 disabled:opacity-50 dark:border-slate-600" @click="paginaAnterior">
            Anterior
          </button>
          <button :disabled="pagina.skip + pagina.limit >= total" class="rounded-md border border-slate-300 px-3 py-1 disabled:opacity-50 dark:border-slate-600" @click="proximaPagina">
            Próxima
          </button>
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

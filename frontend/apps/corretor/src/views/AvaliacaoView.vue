<script setup>
import { onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";
import api from "../api/client";

const route = useRoute();
const imovelId = route.params.id;

const metodo = ref("comparativo");
const form = reactive({
  padrao_construtivo: "normal",
  renda_mensal_bruta: "",
  despesas_operacionais_mensais: "",
  taxa_capitalizacao_anual: "",
  observacoes: "",
});

const calculando = ref(false);
const erro = ref("");
const resultado = ref(null);

const historico = ref([]);
const carregandoHistorico = ref(true);

const METODO_LABEL = { comparativo: "Comparativo direto", reproducao: "Reprodução/reposição (custo)", renda: "Renda/capitalização" };

function formatarMoeda(valor) {
  return Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

async function carregarHistorico() {
  carregandoHistorico.value = true;
  try {
    const { data } = await api.get(`/imoveis/${imovelId}/avaliacoes`);
    historico.value = data;
  } catch {
    // histórico é complementar — falha silenciosa não bloqueia a tela de avaliação
  } finally {
    carregandoHistorico.value = false;
  }
}

function payload() {
  const dados = { metodo: metodo.value, observacoes: form.observacoes || null };
  if (metodo.value === "reproducao") {
    dados.padrao_construtivo = form.padrao_construtivo;
  }
  if (metodo.value === "renda") {
    dados.renda_mensal_bruta = form.renda_mensal_bruta === "" ? null : Number(form.renda_mensal_bruta);
    dados.despesas_operacionais_mensais =
      form.despesas_operacionais_mensais === "" ? null : Number(form.despesas_operacionais_mensais);
    dados.taxa_capitalizacao_anual =
      form.taxa_capitalizacao_anual === "" ? null : Number(form.taxa_capitalizacao_anual);
  }
  return dados;
}

async function calcular() {
  calculando.value = true;
  erro.value = "";
  resultado.value = null;
  try {
    const { data } = await api.post(`/imoveis/${imovelId}/avaliacoes`, payload());
    resultado.value = data;
    await carregarHistorico();
  } catch (err) {
    erro.value = err.response?.data?.detail ?? "Não foi possível calcular a avaliação.";
  } finally {
    calculando.value = false;
  }
}

onMounted(carregarHistorico);
</script>

<template>
  <div class="mx-auto max-w-3xl p-6">
    <h1 class="mb-6 text-xl font-semibold text-slate-900 dark:text-white">Avaliar imóvel</h1>

    <form class="space-y-6" @submit.prevent="calcular">
      <div>
        <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Método</label>
        <select v-model="metodo" class="input">
          <option value="comparativo">Comparativo direto</option>
          <option value="reproducao">Reprodução/reposição (custo)</option>
          <option value="renda">Renda/capitalização</option>
        </select>
      </div>

      <p v-if="metodo === 'comparativo'" class="text-sm text-slate-500 dark:text-slate-400">
        Usa o preço de mercado (R$/m²) cadastrado para a região e tipo do imóvel, homogeneizado pela idade e
        conservação já registradas no cadastro. Sem inputs adicionais.
      </p>

      <div v-if="metodo === 'reproducao'">
        <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Padrão construtivo</label>
        <select v-model="form.padrao_construtivo" class="input">
          <option value="baixo">Baixo</option>
          <option value="normal">Normal</option>
          <option value="alto">Alto</option>
        </select>
      </div>

      <div v-if="metodo === 'renda'" class="grid gap-4 sm:grid-cols-2">
        <div>
          <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Renda mensal bruta (R$)</label>
          <input v-model="form.renda_mensal_bruta" type="number" step="0.01" required class="input" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Despesas operacionais mensais (R$)</label>
          <input v-model="form.despesas_operacionais_mensais" type="number" step="0.01" required class="input" />
        </div>
        <div class="sm:col-span-2">
          <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
            Taxa de capitalização anual (padrão 8%)
          </label>
          <input v-model="form.taxa_capitalizacao_anual" type="number" step="0.001" placeholder="0.08" class="input" />
        </div>
      </div>

      <div>
        <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Observações (opcional)</label>
        <textarea v-model="form.observacoes" rows="2" class="input"></textarea>
      </div>

      <p v-if="erro" class="text-sm text-red-600" role="alert">{{ erro }}</p>

      <button type="submit" :disabled="calculando" class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
        {{ calculando ? "Calculando…" : "Calcular avaliação" }}
      </button>
    </form>

    <!-- Resultado: valor + faixa de confiança + observações sempre juntos, nunca só o número (Artigo II). -->
    <div v-if="resultado" class="mt-8 rounded-xl border border-primary/30 bg-primary/5 p-5 dark:bg-primary/10">
      <p class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {{ METODO_LABEL[resultado.metodo] }}
      </p>
      <p class="mt-1 text-2xl font-bold text-slate-900 dark:text-white">{{ formatarMoeda(resultado.valor_estimado) }}</p>
      <p class="text-sm text-slate-600 dark:text-slate-300">
        Faixa de confiança: {{ formatarMoeda(resultado.valor_min) }} – {{ formatarMoeda(resultado.valor_max) }}
      </p>
      <p v-if="resultado.observacoes" class="mt-3 text-sm text-amber-700 dark:text-amber-400">
        {{ resultado.observacoes }}
      </p>
    </div>

    <div class="mt-10">
      <h2 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        Histórico de avaliações
      </h2>
      <p v-if="carregandoHistorico">Carregando…</p>
      <p v-else-if="historico.length === 0" class="text-sm text-slate-500 dark:text-slate-400">
        Nenhuma avaliação registrada ainda para este imóvel.
      </p>
      <ul v-else class="space-y-2">
        <li
          v-for="item in historico"
          :key="item.id"
          class="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-700"
        >
          <div class="flex items-center justify-between">
            <span class="font-medium text-slate-900 dark:text-white">{{ METODO_LABEL[item.metodo] }}</span>
            <span class="text-slate-500 dark:text-slate-400">{{ new Date(item.created_at).toLocaleString("pt-BR") }}</span>
          </div>
          <div class="mt-1 text-slate-700 dark:text-slate-300">
            {{ formatarMoeda(item.valor_estimado) }}
            <span class="text-slate-500 dark:text-slate-400">
              (faixa: {{ formatarMoeda(item.valor_min) }} – {{ formatarMoeda(item.valor_max) }})
            </span>
          </div>
          <p v-if="item.observacoes" class="mt-1 text-amber-700 dark:text-amber-400">{{ item.observacoes }}</p>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.input {
  @apply w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white;
}
</style>

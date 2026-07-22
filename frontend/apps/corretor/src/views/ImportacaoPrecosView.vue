<script setup>
import { ref } from "vue";
import api from "../api/client";

const arquivo = ref(null);
const enviando = ref(false);
const erro = ref("");
const relatorio = ref(null);

function onArquivoSelecionado(event) {
  arquivo.value = event.target.files[0] ?? null;
  relatorio.value = null;
  erro.value = "";
}

async function enviar() {
  if (!arquivo.value) return;
  enviando.value = true;
  erro.value = "";
  relatorio.value = null;
  try {
    const formData = new FormData();
    formData.append("arquivo", arquivo.value);
    // Sem header de Content-Type manual: o browser precisa gerar o boundary do multipart
    // sozinho a partir do FormData — se a gente fixar o header aqui, o boundary fica faltando
    // e o backend não consegue parsear o arquivo.
    const { data } = await api.post("/admin/precos-mercado/importar", formData);
    relatorio.value = data;
  } catch (err) {
    erro.value = err.response?.status === 403
      ? "Apenas admin pode importar preços de mercado."
      : "Não foi possível importar o arquivo.";
  } finally {
    enviando.value = false;
  }
}
</script>

<template>
  <div class="mx-auto max-w-2xl p-6">
    <h1 class="mb-1 text-xl font-semibold text-slate-900 dark:text-white">Importar preços de mercado</h1>
    <p class="mb-6 text-sm text-slate-500 dark:text-slate-400">
      Arquivo CSV com colunas <code>bairro,cidade,estado,tipo,preco_m2,fonte</code>. Linha com
      bairro+cidade+tipo já cadastrado atualiza o preço; combinação nova cria um registro. Uma
      linha com erro não impede a importação das demais.
    </p>

    <form class="space-y-4" @submit.prevent="enviar">
      <input
        type="file"
        accept=".csv,text/csv"
        class="block w-full text-sm text-slate-600 file:mr-4 file:rounded-md file:border-0 file:bg-primary file:px-4 file:py-2 file:text-sm file:font-medium file:text-white dark:text-slate-300"
        @change="onArquivoSelecionado"
      />

      <p v-if="erro" class="text-sm text-red-600" role="alert">{{ erro }}</p>

      <button
        type="submit"
        :disabled="!arquivo || enviando"
        class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {{ enviando ? "Importando…" : "Importar" }}
      </button>
    </form>

    <div v-if="relatorio" class="mt-8 rounded-xl border border-slate-200 p-5 dark:border-slate-700">
      <p class="text-sm text-slate-700 dark:text-slate-300">
        {{ relatorio.total_linhas }} linha(s) processada(s) —
        <span class="text-emerald-700 dark:text-emerald-400">{{ relatorio.criados }} criado(s)</span>,
        <span class="text-primary">{{ relatorio.atualizados }} atualizado(s)</span>,
        <span :class="relatorio.erros.length ? 'text-red-600' : 'text-slate-500'">{{ relatorio.erros.length }} erro(s)</span>
      </p>

      <ul v-if="relatorio.erros.length" class="mt-3 space-y-1 text-sm">
        <li v-for="e in relatorio.erros" :key="e.linha" class="text-red-600">
          Linha {{ e.linha }}: {{ e.motivo }}
        </li>
      </ul>
    </div>
  </div>
</template>

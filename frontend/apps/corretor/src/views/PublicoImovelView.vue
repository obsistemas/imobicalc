<script setup>
import { onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";
import api from "../api/client";

const route = useRoute();

const imovel = ref(null);
const loading = ref(true);
const erro = ref("");

const form = reactive({ nome: "", telefone: "", email: "" });
const enviando = ref(false);
const enviado = ref(false);
const erroFormulario = ref("");

const TIPO_LABEL = {
  apartamento: "Apartamento",
  casa: "Casa",
  terreno: "Terreno",
  comercial: "Comercial",
  galpao: "Galpão",
};

function formatarMoeda(valor) {
  return Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

async function carregar() {
  loading.value = true;
  erro.value = "";
  try {
    const { data } = await api.get(`/imoveis/publico/${route.params.id}`);
    imovel.value = data;
  } catch {
    erro.value = "Imóvel não encontrado ou não está mais disponível.";
  } finally {
    loading.value = false;
  }
}

async function enviarInteresse() {
  erroFormulario.value = "";
  if (!form.telefone && !form.email) {
    erroFormulario.value = "Informe ao menos telefone ou e-mail.";
    return;
  }
  enviando.value = true;
  try {
    await api.post("/leads/publico", { ...form, imovel_id: route.params.id });
    enviado.value = true;
  } catch {
    erroFormulario.value = "Não foi possível enviar seu interesse. Tente novamente.";
  } finally {
    enviando.value = false;
  }
}

onMounted(carregar);
</script>

<template>
  <div class="min-h-screen bg-slate-50 px-4 py-10 dark:bg-slate-900">
    <div class="mx-auto max-w-2xl">
      <p v-if="erro" class="rounded-lg bg-white p-6 text-center text-sm text-red-600 shadow-sm dark:bg-slate-800">
        {{ erro }}
      </p>
      <p v-else-if="loading" class="text-center text-slate-500 dark:text-slate-400">Carregando…</p>

      <template v-else-if="imovel">
        <div v-if="imovel.fotos?.length" class="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
          <img
            v-for="url in imovel.fotos"
            :key="url"
            :src="url"
            class="h-32 w-full rounded-lg object-cover shadow-sm"
            alt="Foto do imóvel"
          />
        </div>

        <div class="rounded-xl bg-white p-6 shadow-sm dark:bg-slate-800">
          <p class="text-xs font-medium uppercase tracking-wide text-primary">
            {{ TIPO_LABEL[imovel.tipo] ?? imovel.tipo }}
          </p>
          <h1 class="mt-1 text-2xl font-semibold text-slate-900 dark:text-white">{{ imovel.titulo }}</h1>
          <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">{{ imovel.bairro }}, {{ imovel.cidade }} — {{ imovel.estado }}</p>

          <p v-if="imovel.valor_anunciado" class="mt-4 text-3xl font-bold text-slate-900 dark:text-white">
            {{ formatarMoeda(imovel.valor_anunciado) }}
          </p>

          <div class="mt-4 flex flex-wrap gap-4 text-sm text-slate-600 dark:text-slate-300">
            <span>{{ imovel.area_total }} m²</span>
            <span v-if="imovel.quartos">{{ imovel.quartos }} quarto(s)</span>
            <span v-if="imovel.banheiros">{{ imovel.banheiros }} banheiro(s)</span>
            <span v-if="imovel.vagas">{{ imovel.vagas }} vaga(s)</span>
          </div>

          <p v-if="imovel.descricao" class="mt-4 whitespace-pre-line text-sm text-slate-700 dark:text-slate-300">
            {{ imovel.descricao }}
          </p>
        </div>

        <div class="mt-6 rounded-xl bg-white p-6 shadow-sm dark:bg-slate-800">
          <h2 class="text-lg font-semibold text-slate-900 dark:text-white">Tenho interesse</h2>

          <template v-if="enviado">
            <p class="mt-3 text-sm text-green-700 dark:text-green-400">
              Recebemos seu contato! Alguém vai falar com você em breve.
            </p>
          </template>

          <form v-else class="mt-4 space-y-4" @submit.prevent="enviarInteresse">
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300" for="nome">Nome</label>
              <input id="nome" v-model="form.nome" type="text" required class="input" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300" for="telefone">
                Telefone/WhatsApp
              </label>
              <input id="telefone" v-model="form.telefone" type="text" class="input" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300" for="email">E-mail</label>
              <input id="email" v-model="form.email" type="email" class="input" />
            </div>
            <p v-if="erroFormulario" class="text-sm text-red-600" role="alert">{{ erroFormulario }}</p>
            <button
              type="submit"
              :disabled="enviando"
              class="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
            >
              {{ enviando ? "Enviando…" : "Enviar interesse" }}
            </button>
          </form>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.input {
  @apply w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white;
}
</style>

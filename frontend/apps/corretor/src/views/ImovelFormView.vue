<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import api from "../api/client";

const route = useRoute();
const router = useRouter();

const imovelId = computed(() => route.params.id ?? null);
const editando = computed(() => !!imovelId.value);

const form = reactive({
  titulo: "",
  descricao: "",
  cep: "",
  bairro: "",
  cidade: "",
  estado: "",
  tipo: "apartamento",
  area_total: null,
  area_util: null,
  quartos: null,
  banheiros: null,
  suites: null,
  vagas: null,
  andar: null,
  idade_anos: null,
  conservacao: null,
  valor_anunciado: null,
  matricula: "",
  iptu_quitado: null,
  escritura_ok: null,
  status: "disponivel",
});

const logradouro = ref("");
const loading = ref(false);
const salvando = ref(false);
const erro = ref("");

async function carregarImovel() {
  loading.value = true;
  try {
    const { data } = await api.get(`/imoveis/${imovelId.value}`);
    Object.assign(form, data);
    logradouro.value = data.logradouro ?? "";
  } catch {
    erro.value = "Não foi possível carregar o imóvel.";
  } finally {
    loading.value = false;
  }
}

const CAMPOS_NUMERICOS_OPCIONAIS = ["area_util", "quartos", "banheiros", "suites", "vagas", "andar", "idade_anos", "valor_anunciado"];

function payload() {
  const dados = { ...form, area_total: Number(form.area_total) };
  for (const campo of CAMPOS_NUMERICOS_OPCIONAIS) {
    dados[campo] = dados[campo] === "" || dados[campo] === null || dados[campo] === undefined ? null : Number(dados[campo]);
  }
  return dados;
}

async function onSubmit() {
  salvando.value = true;
  erro.value = "";
  try {
    if (editando.value) {
      const { data } = await api.put(`/imoveis/${imovelId.value}`, payload());
      logradouro.value = data.logradouro ?? "";
    } else {
      const { data } = await api.post("/imoveis", payload());
      logradouro.value = data.logradouro ?? "";
    }
    router.push({ name: "imoveis" });
  } catch (err) {
    if (err.response?.status === 402) {
      erro.value = "Limite de imóveis do plano atingido — faça upgrade para cadastrar mais imóveis.";
    } else if (err.response?.status === 422) {
      erro.value = "Confira os campos obrigatórios (título, CEP, bairro, cidade, estado, tipo, área total).";
    } else {
      erro.value = "Não foi possível salvar o imóvel.";
    }
  } finally {
    salvando.value = false;
  }
}

onMounted(() => {
  if (editando.value) carregarImovel();
});
</script>

<template>
  <div class="mx-auto max-w-3xl p-6">
    <h1 class="mb-6 text-xl font-semibold text-slate-900 dark:text-white">
      {{ editando ? "Editar imóvel" : "Novo imóvel" }}
    </h1>

    <p v-if="loading">Carregando…</p>

    <form v-else class="space-y-8" @submit.prevent="onSubmit">
      <section>
        <h2 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Localização
        </h2>
        <div class="grid gap-4 sm:grid-cols-2">
          <div class="sm:col-span-2">
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Título</label>
            <input v-model="form.titulo" required maxlength="200" class="input" />
          </div>
          <div class="sm:col-span-2">
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Descrição</label>
            <textarea v-model="form.descricao" rows="3" class="input"></textarea>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">CEP</label>
            <input v-model="form.cep" required placeholder="00000-000" class="input" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Logradouro</label>
            <input :value="logradouro" disabled class="input opacity-70" placeholder="Preenchido via CEP" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Bairro</label>
            <input v-model="form.bairro" required class="input" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Cidade</label>
            <input v-model="form.cidade" required class="input" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Estado (UF)</label>
            <input v-model="form.estado" required maxlength="2" class="input uppercase" />
          </div>
        </div>
      </section>

      <section>
        <h2 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Características
        </h2>
        <div class="grid gap-4 sm:grid-cols-3">
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Tipo</label>
            <select v-model="form.tipo" required class="input">
              <option value="apartamento">Apartamento</option>
              <option value="casa">Casa</option>
              <option value="terreno">Terreno</option>
              <option value="comercial">Comercial</option>
              <option value="galpao">Galpão</option>
            </select>
          </div>
          <div v-if="editando">
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Status</label>
            <select v-model="form.status" class="input">
              <option value="disponivel">Disponível</option>
              <option value="reservado">Reservado</option>
              <option value="vendido">Vendido</option>
              <option value="alugado">Alugado</option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Área total (m²)</label>
            <input v-model="form.area_total" type="number" step="0.01" required class="input" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Área útil (m²)</label>
            <input v-model="form.area_util" type="number" step="0.01" class="input" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Quartos</label>
            <input v-model="form.quartos" type="number" min="0" class="input" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Banheiros</label>
            <input v-model="form.banheiros" type="number" min="0" class="input" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Suítes</label>
            <input v-model="form.suites" type="number" min="0" class="input" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Vagas</label>
            <input v-model="form.vagas" type="number" min="0" class="input" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Andar</label>
            <input v-model="form.andar" type="number" class="input" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Idade (anos)</label>
            <input v-model="form.idade_anos" type="number" min="0" class="input" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Conservação</label>
            <select v-model="form.conservacao" class="input">
              <option :value="null">—</option>
              <option value="otima">Ótima</option>
              <option value="boa">Boa</option>
              <option value="regular">Regular</option>
              <option value="ruim">Ruim</option>
            </select>
          </div>
        </div>
      </section>

      <section>
        <h2 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Valores</h2>
        <div class="grid gap-4 sm:grid-cols-2">
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Valor anunciado (R$)</label>
            <input v-model="form.valor_anunciado" type="number" step="0.01" class="input" />
          </div>
        </div>
      </section>

      <section>
        <h2 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Documentação
        </h2>
        <div class="grid gap-4 sm:grid-cols-2">
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Matrícula</label>
            <input v-model="form.matricula" class="input" />
          </div>
          <div class="flex items-center gap-6 sm:col-span-2">
            <label class="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
              <input v-model="form.iptu_quitado" type="checkbox" />
              IPTU quitado
            </label>
            <label class="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
              <input v-model="form.escritura_ok" type="checkbox" />
              Escritura em ordem
            </label>
          </div>
        </div>
      </section>

      <p v-if="erro" class="text-sm text-red-600" role="alert">{{ erro }}</p>

      <button
        type="submit"
        :disabled="salvando"
        class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {{ salvando ? "Salvando…" : "Salvar imóvel" }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.input {
  @apply w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white;
}
</style>

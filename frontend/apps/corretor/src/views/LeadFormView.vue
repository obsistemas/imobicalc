<script setup>
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import api from "../api/client";

const router = useRouter();

const form = reactive({
  nome: "",
  email: "",
  telefone: "",
  origem: "site",
  imovel_id: "",
});

const imoveis = ref([]);
const salvando = ref(false);
const erro = ref("");

async function carregarImoveis() {
  try {
    const { data } = await api.get("/imoveis", { params: { limit: 100 } });
    imoveis.value = data.items;
  } catch {
    // lista de imóveis é só uma conveniência do formulário — falha não bloqueia o cadastro do lead
  }
}

async function onSubmit() {
  salvando.value = true;
  erro.value = "";
  try {
    const payload = {
      nome: form.nome,
      email: form.email || null,
      telefone: form.telefone || null,
      origem: form.origem,
      imovel_id: form.imovel_id || null,
    };
    const { data } = await api.post("/leads", payload);
    router.push({ name: "lead-detalhe", params: { id: data.id } });
  } catch {
    erro.value = "Não foi possível cadastrar o lead.";
  } finally {
    salvando.value = false;
  }
}

onMounted(carregarImoveis);
</script>

<template>
  <div class="mx-auto max-w-md p-6">
    <h1 class="mb-6 text-xl font-semibold text-slate-900 dark:text-white">Novo lead</h1>

    <form class="space-y-4" @submit.prevent="onSubmit">
      <div>
        <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Nome</label>
        <input v-model="form.nome" required class="input" />
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">E-mail</label>
        <input v-model="form.email" type="email" class="input" />
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Telefone</label>
        <input v-model="form.telefone" class="input" />
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Origem</label>
        <select v-model="form.origem" required class="input">
          <option value="site">Site</option>
          <option value="indicacao">Indicação</option>
          <option value="portal">Portal</option>
          <option value="redes_sociais">Redes sociais</option>
          <option value="outro">Outro</option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Imóvel de interesse (opcional)</label>
        <select v-model="form.imovel_id" class="input">
          <option value="">Nenhum</option>
          <option v-for="imovel in imoveis" :key="imovel.id" :value="imovel.id">
            {{ imovel.titulo }} — {{ imovel.bairro }}
          </option>
        </select>
      </div>

      <p v-if="erro" class="text-sm text-red-600" role="alert">{{ erro }}</p>

      <button type="submit" :disabled="salvando" class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
        {{ salvando ? "Salvando…" : "Cadastrar lead" }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.input {
  @apply w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white;
}
</style>

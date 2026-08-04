<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import api from "../api/client";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const form = reactive({ email: "", papel: "corretor", assistenteDeId: "" });
const status = ref(null); // null | "ok" | "erro"
const mensagem = ref("");
const loading = ref(false);
const usuarios = ref([]);

const corretores = computed(() => usuarios.value.filter((u) => u.papel === "corretor"));

onMounted(async () => {
  if (!auth.isDono && !auth.isGerente) return;
  try {
    const { data } = await api.get("/users");
    usuarios.value = data;
  } catch {
    // GET /users é só para popular o seletor de corretor do convite de assistente — falha
    // silenciosa aqui não impede convidar gerente/corretor, só desabilita o convite de assistente.
  }
});

async function onSubmit() {
  loading.value = true;
  status.value = null;
  try {
    await api.post("/users/convites", {
      email: form.email,
      papel: form.papel,
      assistente_de_id: form.papel === "assistente" ? form.assistenteDeId : undefined,
    });
    status.value = "ok";
    mensagem.value = `Convite enviado para ${form.email}.`;
    form.email = "";
    form.assistenteDeId = "";
  } catch (err) {
    status.value = "erro";
    if (err.response?.status === 403) {
      mensagem.value = "Ative o 2FA antes de convidar a equipe.";
    } else if (err.response?.status === 409) {
      mensagem.value = err.response.data?.detail ?? "Já existe convite ou usuário com este e-mail.";
    } else if (err.response?.status === 422) {
      mensagem.value = err.response.data?.detail ?? "Dados do convite inválidos.";
    } else {
      mensagem.value = "Não foi possível enviar o convite.";
    }
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="mx-auto max-w-md p-6">
    <h1 class="mb-4 text-xl font-semibold text-slate-900 dark:text-white">Convidar para a equipe</h1>

    <p v-if="!auth.isDono" class="text-sm text-amber-600">
      Apenas o dono pode convidar novos membros da equipe.
    </p>

    <form v-else class="space-y-4" @submit.prevent="onSubmit">
      <div>
        <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300" for="email">
          E-mail
        </label>
        <input
          id="email"
          v-model="form.email"
          type="email"
          required
          class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white"
        />
      </div>

      <div>
        <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300" for="papel">
          Papel
        </label>
        <select
          id="papel"
          v-model="form.papel"
          class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white"
        >
          <option value="gerente">Gerente</option>
          <option value="corretor">Corretor</option>
          <option value="assistente">Assistente</option>
        </select>
      </div>

      <div v-if="form.papel === 'assistente'">
        <label class="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300" for="assistente-de">
          Atende o corretor
        </label>
        <select
          id="assistente-de"
          v-model="form.assistenteDeId"
          required
          class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-slate-600 dark:bg-slate-700 dark:text-white"
        >
          <option value="" disabled>Selecione um corretor</option>
          <option v-for="c in corretores" :key="c.uuid" :value="c.uuid">{{ c.nome }} ({{ c.email }})</option>
        </select>
        <p v-if="corretores.length === 0" class="mt-1 text-xs text-amber-600">
          Nenhum corretor ativo na equipe ainda — convide um corretor antes de vincular um assistente.
        </p>
      </div>

      <p v-if="status === 'ok'" class="text-sm text-emerald-700 dark:text-emerald-400">{{ mensagem }}</p>
      <p v-if="status === 'erro'" class="text-sm text-red-600" role="alert">{{ mensagem }}</p>

      <button
        type="submit"
        :disabled="loading"
        class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {{ loading ? "Enviando…" : "Enviar convite" }}
      </button>
    </form>
  </div>
</template>

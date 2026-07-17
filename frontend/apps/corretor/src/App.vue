<script setup>
import { onBeforeUnmount, ref, watch } from "vue";
import { useNotificacoes } from "./composables/useNotificacoes";
import { useAuthStore } from "./stores/auth";

const auth = useAuthStore();
const toast = ref(null);
let timeoutToast = null;

function onMensagem(mensagem) {
  if (mensagem.tipo === "lead_novo") {
    toast.value = `Novo lead: ${mensagem.lead.nome}`;
    clearTimeout(timeoutToast);
    timeoutToast = setTimeout(() => (toast.value = null), 6000);
  }
}

const { conectar, desconectar } = useNotificacoes(onMensagem);

watch(
  () => auth.isAuthenticated,
  (autenticado) => {
    if (autenticado) conectar();
    else desconectar();
  },
  { immediate: true }
);

onBeforeUnmount(desconectar);
</script>

<template>
  <router-view />
  <div
    v-if="toast"
    class="fixed bottom-4 right-4 z-50 max-w-xs rounded-lg bg-slate-900 px-4 py-3 text-sm text-white shadow-lg dark:bg-slate-700"
    role="status"
  >
    {{ toast }}
  </div>
</template>

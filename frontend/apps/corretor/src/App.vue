<script setup>
import { onBeforeUnmount, ref, watch } from "vue";
import { useNotificacoes } from "./composables/useNotificacoes";
import { useAuthStore } from "./stores/auth";

const auth = useAuthStore();
const toast = ref(null);
let timeoutToast = null;

function formatarMoeda(valor) {
  return Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function onMensagem(mensagem) {
  if (mensagem.tipo === "lead_novo") {
    toast.value = `Novo lead: ${mensagem.lead.nome}`;
  } else if (mensagem.tipo === "imovel_subprecificado") {
    const percentual = Math.round(mensagem.imovel.percentual_abaixo * 100);
    toast.value = `"${mensagem.imovel.titulo}" está ${percentual}% abaixo do mercado (esperado ${formatarMoeda(mensagem.imovel.valor_esperado)})`;
  } else {
    return;
  }
  clearTimeout(timeoutToast);
  timeoutToast = setTimeout(() => (toast.value = null), 6000);
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

import { ref } from "vue";
import { useAuthStore } from "../stores/auth";

const _MAX_ESPERA_MS = 30000;

export function useNotificacoes(onMensagem) {
  const conectado = ref(false);
  let ws = null;
  let tentativas = 0;
  let timeoutReconexao = null;
  let desconectadoManualmente = false;

  function conectar() {
    const auth = useAuthStore();
    if (!auth.accessToken) return;

    desconectadoManualmente = false;
    const protocolo = window.location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${protocolo}://${window.location.host}/api/v1/ws/notificacoes?token=${auth.accessToken}`);

    ws.onopen = () => {
      conectado.value = true;
      tentativas = 0;
    };

    ws.onmessage = (event) => {
      try {
        onMensagem(JSON.parse(event.data));
      } catch {
        // mensagem não-JSON — ignora
      }
    };

    ws.onclose = () => {
      conectado.value = false;
      if (!desconectadoManualmente) agendarReconexao();
    };

    ws.onerror = () => {
      ws?.close();
    };
  }

  function agendarReconexao() {
    tentativas += 1;
    const espera = Math.min(1000 * 2 ** tentativas, _MAX_ESPERA_MS);
    clearTimeout(timeoutReconexao);
    timeoutReconexao = setTimeout(conectar, espera);
  }

  function desconectar() {
    desconectadoManualmente = true;
    clearTimeout(timeoutReconexao);
    ws?.close();
    ws = null;
    conectado.value = false;
  }

  return { conectado, conectar, desconectar };
}

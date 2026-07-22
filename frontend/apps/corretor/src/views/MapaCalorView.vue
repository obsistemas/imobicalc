<script setup>
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.heat";
import { onMounted, onBeforeUnmount, ref } from "vue";
import api from "../api/client";

const containerMapa = ref(null);
const loading = ref(true);
const erro = ref("");
const totalPontos = ref(0);
let mapa = null;

// Coordenada central aproximada do Brasil — usada só até termos pontos reais para enquadrar.
const CENTRO_BRASIL = [-14.2, -51.9];

async function carregar() {
  loading.value = true;
  erro.value = "";
  try {
    const { data } = await api.get("/precos-mercado/mapa-calor");
    totalPontos.value = data.length;

    if (!mapa) {
      mapa = L.map(containerMapa.value).setView(CENTRO_BRASIL, 4);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap",
        maxZoom: 18,
      }).addTo(mapa);
    }

    if (data.length > 0) {
      const pontos = data.map((p) => [Number(p.latitude), Number(p.longitude), Number(p.preco_m2)]);
      L.heatLayer(pontos, { radius: 35, blur: 25, max: Math.max(...data.map((p) => Number(p.preco_m2))) }).addTo(mapa);
      mapa.fitBounds(pontos.map(([lat, lng]) => [lat, lng]), { padding: [30, 30] });
    }
  } catch {
    erro.value = "Não foi possível carregar o mapa de calor.";
  } finally {
    loading.value = false;
  }
}

onMounted(carregar);
onBeforeUnmount(() => {
  mapa?.remove();
});
</script>

<template>
  <div class="mx-auto max-w-5xl p-6">
    <h1 class="mb-1 text-xl font-semibold text-slate-900 dark:text-white">Mapa de calor de preços</h1>
    <p class="mb-6 text-sm text-slate-500 dark:text-slate-400">
      Preço médio do m² por bairro/cidade cadastrado na base de preços de mercado.
    </p>

    <p v-if="erro" class="text-sm text-red-600" role="alert">{{ erro }}</p>
    <p v-if="loading">Carregando…</p>
    <p v-else-if="totalPontos === 0" class="text-sm text-slate-500 dark:text-slate-400">
      Nenhum preço de mercado com coordenada geocodificada ainda — cadastre ou importe preços
      (com bairro e cidade preenchidos) para o mapa aparecer.
    </p>

    <div ref="containerMapa" class="h-[32rem] w-full rounded-xl border border-slate-200 dark:border-slate-700"></div>
  </div>
</template>

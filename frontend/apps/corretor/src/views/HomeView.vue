<script setup>
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
</script>

<template>
  <div class="min-h-screen bg-slate-50 dark:bg-slate-900">
    <header class="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4 dark:border-slate-700 dark:bg-slate-800">
      <span class="font-semibold text-slate-900 dark:text-white">Proptech Avaliador</span>
      <div class="flex items-center gap-4 text-sm text-slate-600 dark:text-slate-300">
        <router-link :to="{ name: 'imoveis' }" class="text-primary">Imóveis</router-link>
        <router-link :to="{ name: 'leads' }" class="text-primary">Leads</router-link>
        <router-link :to="{ name: 'plano' }" class="text-primary">Plano</router-link>
        <router-link v-if="auth.isAdmin" :to="{ name: 'faturas' }" class="text-primary">Faturas</router-link>
        <router-link v-if="auth.isAdmin" :to="{ name: 'convidar-corretor' }" class="text-primary">
          Convidar corretor
        </router-link>
        <router-link v-if="auth.isAdmin && !auth.user?.totp_enabled" :to="{ name: '2fa-setup' }" class="text-primary">
          Ativar 2FA
        </router-link>
        <span>{{ auth.user?.nome }}</span>
        <button class="text-primary" @click="auth.logout()">Sair</button>
      </div>
    </header>
    <main class="p-6 text-slate-700 dark:text-slate-200">
      <p>
        Dashboard chega na próxima feature do roadmap (specs/005+). Enquanto isso, use o menu
        <router-link :to="{ name: 'imoveis' }" class="text-primary">Imóveis</router-link> para cadastrar e avaliar sua
        carteira, e <router-link :to="{ name: 'leads' }" class="text-primary">Leads</router-link> para acompanhar o
        pipeline de vendas.
      </p>
    </main>
  </div>
</template>

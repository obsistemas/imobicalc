import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";
import AcceptInviteView from "../views/AcceptInviteView.vue";
import AvaliacaoView from "../views/AvaliacaoView.vue";
import HomeView from "../views/HomeView.vue";
import ImovelFormView from "../views/ImovelFormView.vue";
import ImoveisListView from "../views/ImoveisListView.vue";
import InviteTeamView from "../views/InviteTeamView.vue";
import InvoicesView from "../views/InvoicesView.vue";
import LoginView from "../views/LoginView.vue";
import PlanoView from "../views/PlanoView.vue";
import SignupView from "../views/SignupView.vue";
import TwoFactorSetupView from "../views/TwoFactorSetupView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView, meta: { public: true } },
    { path: "/signup", name: "signup", component: SignupView, meta: { public: true } },
    {
      path: "/convites/:token/aceitar",
      name: "aceitar-convite",
      component: AcceptInviteView,
      meta: { public: true },
    },
    { path: "/", name: "home", component: HomeView },
    { path: "/imoveis", name: "imoveis", component: ImoveisListView },
    { path: "/imoveis/novo", name: "imovel-novo", component: ImovelFormView },
    { path: "/imoveis/:id/editar", name: "imovel-editar", component: ImovelFormView },
    { path: "/imoveis/:id/avaliar", name: "imovel-avaliar", component: AvaliacaoView },
    { path: "/2fa/setup", name: "2fa-setup", component: TwoFactorSetupView },
    { path: "/equipe/convidar", name: "convidar-corretor", component: InviteTeamView },
    { path: "/plano", name: "plano", component: PlanoView },
    { path: "/faturas", name: "faturas", component: InvoicesView },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: "login" };
  }
  return true;
});

export default router;

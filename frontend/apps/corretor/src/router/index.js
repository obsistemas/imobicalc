import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { useSuperadminAuthStore } from "../stores/superadmin";
import AcceptInviteView from "../views/AcceptInviteView.vue";
import AvaliacaoView from "../views/AvaliacaoView.vue";
import DashboardView from "../views/DashboardView.vue";
import HomeView from "../views/HomeView.vue";
import ImovelFormView from "../views/ImovelFormView.vue";
import ImoveisListView from "../views/ImoveisListView.vue";
import ImportacaoPrecosView from "../views/ImportacaoPrecosView.vue";
import IntegracaoApiKeyView from "../views/IntegracaoApiKeyView.vue";
import InviteTeamView from "../views/InviteTeamView.vue";
import InvoicesView from "../views/InvoicesView.vue";
import LeadDetailView from "../views/LeadDetailView.vue";
import LeadFormView from "../views/LeadFormView.vue";
import LeadsListView from "../views/LeadsListView.vue";
import LoginView from "../views/LoginView.vue";
import MapaCalorView from "../views/MapaCalorView.vue";
import PlanoView from "../views/PlanoView.vue";
import PublicoImovelView from "../views/PublicoImovelView.vue";
import SignupView from "../views/SignupView.vue";
import SuperadminAuditoriaView from "../views/SuperadminAuditoriaView.vue";
import SuperadminDashboardView from "../views/SuperadminDashboardView.vue";
import SuperadminLoginView from "../views/SuperadminLoginView.vue";
import SuperadminTenantsView from "../views/SuperadminTenantsView.vue";
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
    { path: "/dashboard", name: "dashboard", component: DashboardView },
    { path: "/imoveis", name: "imoveis", component: ImoveisListView },
    { path: "/imoveis/novo", name: "imovel-novo", component: ImovelFormView },
    { path: "/imoveis/:id/editar", name: "imovel-editar", component: ImovelFormView },
    { path: "/imoveis/:id/avaliar", name: "imovel-avaliar", component: AvaliacaoView },
    { path: "/leads", name: "leads", component: LeadsListView },
    { path: "/leads/novo", name: "lead-novo", component: LeadFormView },
    { path: "/leads/:id", name: "lead-detalhe", component: LeadDetailView },
    { path: "/precos-mercado/mapa-calor", name: "mapa-calor", component: MapaCalorView },
    { path: "/precos-mercado/importar", name: "importar-precos", component: ImportacaoPrecosView },
    { path: "/2fa/setup", name: "2fa-setup", component: TwoFactorSetupView },
    { path: "/equipe/convidar", name: "convidar-corretor", component: InviteTeamView },
    { path: "/plano", name: "plano", component: PlanoView },
    { path: "/faturas", name: "faturas", component: InvoicesView },
    { path: "/integracao/api-key", name: "integracao-api-key", component: IntegracaoApiKeyView },
    {
      path: "/publico/imoveis/:id",
      name: "publico-imovel",
      component: PublicoImovelView,
      meta: { public: true },
    },
    { path: "/admin/login", name: "admin-login", component: SuperadminLoginView, meta: { public: true, superadmin: true } },
    { path: "/admin", name: "admin-dashboard", component: SuperadminDashboardView, meta: { superadmin: true } },
    { path: "/admin/tenants", name: "admin-tenants", component: SuperadminTenantsView, meta: { superadmin: true } },
    { path: "/admin/auditoria", name: "admin-auditoria", component: SuperadminAuditoriaView, meta: { superadmin: true } },
  ],
});

router.beforeEach((to) => {
  // Rotas /admin/* usam uma sessão própria (007-superadmin), separada do login de
  // imobiliária — nunca compartilham o mesmo guard nem o mesmo storage de token.
  if (to.meta.superadmin) {
    const superadminAuth = useSuperadminAuthStore();
    if (!to.meta.public && !superadminAuth.isAuthenticated) {
      return { name: "admin-login" };
    }
    return true;
  }

  const auth = useAuthStore();
  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: "login" };
  }
  return true;
});

export default router;

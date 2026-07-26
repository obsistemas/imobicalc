import axios from "axios";

// Cliente separado do `api/client.js` (tenant): o painel superadmin (007-superadmin) usa um
// token JWT diferente (sem tenant_id, papel=superadmin) e não tem refresh token — reaproveitar
// o cliente do tenant faria um 401 do painel disparar o /auth/refresh de tenant, que é errado
// aqui. Em caso de 401/403, só limpa o token e deixa a rota expirar (usuário loga de novo).
const adminApi = axios.create({
  baseURL: "/api/v1/admin",
});

let adminAccessToken = null;

export function setAdminAccessToken(token) {
  adminAccessToken = token;
}

export function getAdminAccessToken() {
  return adminAccessToken;
}

adminApi.interceptors.request.use((config) => {
  if (adminAccessToken) {
    config.headers.Authorization = `Bearer ${adminAccessToken}`;
  }
  return config;
});

export default adminApi;

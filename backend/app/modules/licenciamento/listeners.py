from app.core.events import on
from app.modules.licenciamento import service


@on("tenant_criado")
async def _criar_license_para_novo_tenant(*, session, tenant, **_kwargs) -> None:
    await service.ensure_plans_seeded(session)
    plano_padrao = await service.get_plan_by_nome(session, service.DEFAULT_PLAN_NOME)
    await service.create_license(session, tenant=tenant, plan=plano_padrao)

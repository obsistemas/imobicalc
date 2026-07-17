import json

from redis.asyncio import Redis

from app.core.events import on
from app.modules.leads.models import Lead


def _canal_tenant(tenant_id) -> str:
    return f"tenant.{tenant_id}.notificacoes"


@on("lead_criado")
async def _notificar_lead_criado(*, tenant_id, redis: Redis, lead: Lead, **_kwargs) -> None:
    payload = {
        "tipo": "lead_novo",
        "lead": {
            "id": str(lead.uuid),
            "nome": lead.nome,
            "origem": lead.origem.value,
            "estagio": lead.estagio.value,
        },
    }
    await redis.publish(_canal_tenant(tenant_id), json.dumps(payload))

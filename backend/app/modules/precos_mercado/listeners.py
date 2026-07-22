import json
from decimal import Decimal

from redis.asyncio import Redis

from app.core.events import on
from app.modules.imoveis.models import Imovel


def _canal_tenant(tenant_id) -> str:
    return f"tenant.{tenant_id}.notificacoes"


@on("imovel_subprecificado")
async def _notificar_imovel_subprecificado(
    *, tenant_id, redis: Redis, imovel: Imovel, valor_esperado: Decimal, percentual_abaixo: float, **_kwargs
) -> None:
    payload = {
        "tipo": "imovel_subprecificado",
        "imovel": {
            "id": str(imovel.uuid),
            "titulo": imovel.titulo,
            "valor_anunciado": str(imovel.valor_anunciado),
            "valor_esperado": str(valor_esperado),
            "percentual_abaixo": round(percentual_abaixo, 4),
        },
    }
    await redis.publish(_canal_tenant(tenant_id), json.dumps(payload))

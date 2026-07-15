"""Régua de dunning (RN6): transições de estado da license ocorrem só aqui, num job
agendado para meia-noite (America/Sao_Paulo) — nunca de forma síncrona numa requisição de
usuário. `calcular_novo_status` é uma função pura para ser fácil de testar sem infra."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import settings
from app.core.tenant_context import system_scope, tenant_scope
from app.modules.auditoria import service as auditoria_service
from app.modules.licenciamento.models import License, LicenseStatus
from app.modules.licenciamento.service import sync_tenant_status


def _as_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def calcular_novo_status(license_: License, agora: datetime) -> LicenseStatus:
    """Recalcula o estado esperado da license a partir de datas já persistidas — nunca
    incrementa contador, então rodar duas vezes no mesmo dia nunca duplica efeito."""
    if license_.status == LicenseStatus.TRIAL:
        if agora >= _as_aware(license_.trial_termina_em):
            return LicenseStatus.PAST_DUE
        return LicenseStatus.TRIAL

    if license_.status == LicenseStatus.PAST_DUE:
        desde = _as_aware(license_.past_due_desde) if license_.past_due_desde else agora
        limite = desde + timedelta(days=settings.dunning_dias_ate_suspender)
        if agora >= limite:
            return LicenseStatus.SUSPENDED
        return LicenseStatus.PAST_DUE

    # active, suspended, cancelled: não mudam automaticamente aqui — active só cai por
    # falha de pagamento explícita (fora do escopo desta feature: exigiria geração
    # automática de fatura recorrente); suspended->cancelled é ação manual do admin.
    return license_.status


async def executar_dunning(session_factory) -> int:
    """Roda a régua para todas as licenças elegíveis. Retorna quantas transições aplicou.
    Idempotente: reexecuções no mesmo dia recalculam o mesmo resultado."""
    agora = datetime.now(timezone.utc)
    transicoes = 0

    async with session_factory() as session:
        with system_scope():
            result = await session.execute(
                select(License).where(License.status.in_([LicenseStatus.TRIAL, LicenseStatus.PAST_DUE]))
            )
            licenses = list(result.scalars().all())

        for license_ in licenses:
            novo_status = calcular_novo_status(license_, agora)
            if novo_status == license_.status:
                continue

            with tenant_scope(license_.tenant_id):
                antes = {"status": license_.status.value}
                if novo_status == LicenseStatus.PAST_DUE:
                    license_.past_due_desde = agora
                if novo_status == LicenseStatus.SUSPENDED:
                    license_.suspensa_em = agora
                license_.status = novo_status
                await sync_tenant_status(session, license_.tenant_id, novo_status)
                await auditoria_service.record(
                    session,
                    tenant_id=license_.tenant_id,
                    ator_user_id=None,
                    acao="dunning_transition",
                    entidade="license",
                    entidade_id=str(license_.uuid),
                    antes=antes,
                    depois={"status": novo_status.value},
                )
                await session.commit()
            transicoes += 1

    return transicoes

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import tenant_scope
from app.modules.dashboard.calculos import inicio_periodo, media_dias, media_dias_calendario, preencher_serie_vendas
from app.modules.imoveis.models import Imovel, ImovelStatus
from app.modules.leads.models import ESTAGIOS_TERMINAIS, EstagioLead, Lead
from app.modules.tenancy.models import Papel, User


def _filtros_imovel(tenant_id: uuid.UUID, user: User) -> list:
    filtros = [Imovel.tenant_id == tenant_id, Imovel.ativo.is_(True)]
    if user.papel == Papel.CORRETOR:
        filtros.append(Imovel.corretor_id == user.uuid)
    return filtros


def _filtros_lead(tenant_id: uuid.UUID, user: User) -> list:
    filtros = [Lead.tenant_id == tenant_id]
    if user.papel == Papel.CORRETOR:
        filtros.append(Lead.corretor_id == user.uuid)
    return filtros


def _inicio_datetime(inicio_data: date) -> datetime:
    """`Imovel.data_venda` é Date; `Lead.created_at`/`fechado_em` são DateTime(timezone=True) —
    comparar DateTime com um `date` puro é ambíguo entre dialetos (SQLite tolera, Postgres não
    necessariamente da mesma forma). Sempre converte para datetime UTC explícito."""
    return datetime.combine(inicio_data, datetime.min.time(), tzinfo=timezone.utc)


def _aware(dt: datetime) -> datetime:
    # SQLite (usado nos testes) descarta tzinfo mesmo com DateTime(timezone=True); Postgres
    # (produção) preserva. Normaliza para UTC-aware nos dois casos (mesmo padrão de
    # Convite._expires_at_aware em app/modules/tenancy/models.py).
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def obter_resumo(
    session: AsyncSession, *, tenant_id: uuid.UUID, user: User, meses: int = 12, dias_sem_contato: int = 3
) -> dict:
    agora = datetime.now(timezone.utc)
    inicio = inicio_periodo(meses=meses, referencia=agora.date())
    inicio_dt = _inicio_datetime(inicio)
    limite_sem_contato = agora - timedelta(days=dias_sem_contato)

    with tenant_scope(tenant_id):
        filtros_imovel = _filtros_imovel(tenant_id, user)
        filtros_lead = _filtros_lead(tenant_id, user)

        result = await session.execute(
            select(Imovel.status, func.count()).where(*filtros_imovel).group_by(Imovel.status)
        )
        imoveis_por_status = {status.value: total for status, total in result.all()}

        leads_ativos = (
            await session.execute(
                select(func.count())
                .select_from(Lead)
                .where(*filtros_lead, Lead.estagio.notin_(ESTAGIOS_TERMINAIS))
            )
        ).scalar_one()

        leads_sem_contato = (
            await session.execute(
                select(func.count())
                .select_from(Lead)
                .where(*filtros_lead, Lead.estagio == EstagioLead.NOVO, Lead.created_at <= limite_sem_contato)
            )
        ).scalar_one()

        total_leads_periodo = (
            await session.execute(
                select(func.count()).select_from(Lead).where(*filtros_lead, Lead.created_at >= inicio_dt)
            )
        ).scalar_one()
        leads_fechados_periodo = (
            await session.execute(
                select(func.count())
                .select_from(Lead)
                .where(*filtros_lead, Lead.estagio == EstagioLead.FECHADO, Lead.created_at >= inicio_dt)
            )
        ).scalar_one()
        taxa_conversao = (leads_fechados_periodo / total_leads_periodo) if total_leads_periodo > 0 else 0.0

        imoveis_vendidos_periodo = (
            (
                await session.execute(
                    select(Imovel.created_at, Imovel.data_venda, Imovel.valor_anunciado).where(
                        *filtros_imovel, Imovel.status == ImovelStatus.VENDIDO, Imovel.data_venda >= inicio
                    )
                )
            )
            .all()
        )
        valores = [v for _, _, v in imoveis_vendidos_periodo if v is not None]
        ticket_medio = (sum(valores) / len(valores)) if valores else None
        pares_venda = [(_aware(criado).date(), vendido) for criado, vendido, _ in imoveis_vendidos_periodo]
        tempo_medio_venda_imovel_dias = media_dias_calendario(pares_venda)

        leads_fechados_com_data = (
            (
                await session.execute(
                    select(Lead.created_at, Lead.fechado_em).where(
                        *filtros_lead, Lead.fechado_em.is_not(None), Lead.fechado_em >= inicio_dt
                    )
                )
            )
            .all()
        )
        pares_fechamento = [(_aware(criado), _aware(fechado)) for criado, fechado in leads_fechados_com_data]
        tempo_medio_fechamento_lead_dias = media_dias(pares_fechamento)

    return {
        "imoveis_por_status": imoveis_por_status,
        "leads_ativos": leads_ativos,
        "leads_sem_contato": leads_sem_contato,
        "taxa_conversao": taxa_conversao,
        "ticket_medio": ticket_medio,
        "tempo_medio_venda_imovel_dias": tempo_medio_venda_imovel_dias,
        "tempo_medio_fechamento_lead_dias": tempo_medio_fechamento_lead_dias,
    }


async def obter_vendas_por_mes(
    session: AsyncSession, *, tenant_id: uuid.UUID, user: User, meses: int = 12
) -> list[dict]:
    agora = datetime.now(timezone.utc)
    inicio = inicio_periodo(meses=meses, referencia=agora.date())

    with tenant_scope(tenant_id):
        filtros_imovel = _filtros_imovel(tenant_id, user)
        linhas = (
            await session.execute(
                select(Imovel.data_venda, Imovel.valor_anunciado).where(
                    *filtros_imovel, Imovel.status == ImovelStatus.VENDIDO, Imovel.data_venda >= inicio
                )
            )
        ).all()

    contagem: dict[tuple[int, int], tuple[int, Decimal]] = {}
    for data_venda, valor in linhas:
        chave = (data_venda.year, data_venda.month)
        quantidade_atual, valor_atual = contagem.get(chave, (0, Decimal("0")))
        contagem[chave] = (quantidade_atual + 1, valor_atual + (valor or Decimal("0")))

    return preencher_serie_vendas(contagem, meses=meses, referencia=agora.date())


async def obter_leads_por_origem(
    session: AsyncSession, *, tenant_id: uuid.UUID, user: User, meses: int = 12
) -> list[dict]:
    agora = datetime.now(timezone.utc)
    inicio_dt = _inicio_datetime(inicio_periodo(meses=meses, referencia=agora.date()))

    with tenant_scope(tenant_id):
        filtros_lead = _filtros_lead(tenant_id, user)
        result = await session.execute(
            select(Lead.origem, func.count())
            .where(*filtros_lead, Lead.created_at >= inicio_dt)
            .group_by(Lead.origem)
        )
        linhas = result.all()

    return [{"origem": origem.value, "quantidade": quantidade} for origem, quantidade in linhas]

"""Núcleo de permissões (010-rbac-papeis) — funções puras, sem I/O.

Único lugar que decide "o que este usuário pode ver/fazer" por papel. Nenhum módulo (imoveis,
leads, dashboard, ...) deveria reimplementar essa lógica por conta própria (RN2 da spec) — é
exatamente a duplicação que esta feature existe para eliminar.
"""

import uuid

from app.modules.tenancy.models import Papel, User

_VISIBILIDADE_TOTAL = {Papel.DONO, Papel.GERENTE}

# Nunca corresponde a um corretor_id real — usado só quando um assistente não tem
# assistente_de_id definido (RN3: nesse caso ele não deve enxergar nada, nunca "vê tudo",
# que é o que aconteceria se devolvêssemos None nesse caso).
SEM_VINCULO = uuid.UUID(int=0)


def escopo_visibilidade(user: User) -> uuid.UUID | None:
    """None = enxerga todo o tenant. Um UUID = só recursos com corretor_id == esse valor."""
    if user.papel in _VISIBILIDADE_TOTAL:
        return None
    if user.papel == Papel.ASSISTENTE:
        return user.assistente_de_id or SEM_VINCULO
    return user.uuid  # CORRETOR


def corretor_id_efetivo(user: User) -> uuid.UUID:
    """A quem atribuir (corretor_id) um Imovel/Lead recém-criado por este usuário."""
    if user.papel == Papel.ASSISTENTE:
        return user.assistente_de_id or SEM_VINCULO
    return user.uuid


def pode_excluir(owner_id: uuid.UUID | None, user: User) -> bool:
    """Excluir é sempre checado além da visibilidade (RN4) — ver/editar não implica poder
    excluir; assistente é o primeiro papel onde essas duas coisas divergem."""
    if user.papel == Papel.ASSISTENTE:
        return False
    if user.papel in _VISIBILIDADE_TOTAL:
        return True
    return owner_id == user.uuid

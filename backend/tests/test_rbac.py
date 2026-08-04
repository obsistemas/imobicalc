import uuid

from app.core.rbac import SEM_VINCULO, corretor_id_efetivo, escopo_visibilidade, pode_excluir
from app.modules.tenancy.models import Papel, User


def _user(papel: Papel, *, assistente_de_id: uuid.UUID | None = None) -> User:
    u = User(
        tenant_id=uuid.uuid4(),
        nome="Teste",
        email=f"{uuid.uuid4()}@example.com",
        password_hash="x",
        papel=papel,
        assistente_de_id=assistente_de_id,
    )
    u.uuid = uuid.uuid4()
    return u


# --- escopo_visibilidade ------------------------------------------------------------------


def test_dono_ve_tudo():
    assert escopo_visibilidade(_user(Papel.DONO)) is None


def test_gerente_ve_tudo():
    assert escopo_visibilidade(_user(Papel.GERENTE)) is None


def test_corretor_ve_so_o_proprio():
    user = _user(Papel.CORRETOR)
    assert escopo_visibilidade(user) == user.uuid


def test_assistente_com_vinculo_ve_do_corretor_atendido():
    corretor_id = uuid.uuid4()
    user = _user(Papel.ASSISTENTE, assistente_de_id=corretor_id)
    assert escopo_visibilidade(user) == corretor_id


def test_assistente_sem_vinculo_nunca_ve_tudo():
    user = _user(Papel.ASSISTENTE, assistente_de_id=None)
    resultado = escopo_visibilidade(user)
    assert resultado is not None
    assert resultado == SEM_VINCULO


# --- corretor_id_efetivo -------------------------------------------------------------------


def test_corretor_id_efetivo_dono_e_o_proprio_uuid():
    user = _user(Papel.DONO)
    assert corretor_id_efetivo(user) == user.uuid


def test_corretor_id_efetivo_assistente_e_o_corretor_atendido():
    corretor_id = uuid.uuid4()
    user = _user(Papel.ASSISTENTE, assistente_de_id=corretor_id)
    assert corretor_id_efetivo(user) == corretor_id


def test_corretor_id_efetivo_assistente_sem_vinculo_e_sentinela():
    user = _user(Papel.ASSISTENTE, assistente_de_id=None)
    assert corretor_id_efetivo(user) == SEM_VINCULO


# --- pode_excluir --------------------------------------------------------------------------


def test_assistente_nunca_pode_excluir():
    user = _user(Papel.ASSISTENTE, assistente_de_id=uuid.uuid4())
    assert pode_excluir(user.assistente_de_id, user) is False


def test_dono_sempre_pode_excluir():
    user = _user(Papel.DONO)
    assert pode_excluir(uuid.uuid4(), user) is True


def test_gerente_sempre_pode_excluir():
    user = _user(Papel.GERENTE)
    assert pode_excluir(uuid.uuid4(), user) is True


def test_corretor_pode_excluir_so_o_proprio():
    user = _user(Papel.CORRETOR)
    assert pode_excluir(user.uuid, user) is True
    assert pode_excluir(uuid.uuid4(), user) is False

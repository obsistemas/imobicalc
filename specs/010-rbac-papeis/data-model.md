# Modelo de Dados — Feature 010: RBAC 4 Papéis

Uma migração de dado (`admin`→`dono`) e duas colunas novas (`users.assistente_de_id`,
`convites.assistente_de_id`) — nenhuma tabela nova.

## `Papel` (enum, `tenancy/models.py`)

Antes: `ADMIN`, `CORRETOR`. Depois: `DONO`, `GERENTE`, `CORRETOR`, `ASSISTENTE`. Armazenado como
string (`native_enum=False`), então a migração é um `UPDATE`, não uma alteração de tipo de
coluna:

```sql
UPDATE users SET papel = 'dono' WHERE papel = 'admin';
```

`Convite.papel` não precisa de migração de dado (convites pendentes de antes desta feature, se
existirem, continuam `corretor` — não há convite pendente com `admin`, já que isso nunca foi uma
opção no fluxo de convite).

## `users.assistente_de_id`

`UUID NULL`. Guarda o `User.uuid` do corretor que o assistente atende — mesmo padrão de
`corretor_id` em `Imovel`/`Lead` (guarda o `uuid` público, não a PK interna; sem FK literal).
Só é significativo quando `papel=assistente`; `NULL` nos demais papéis.

## `convites.assistente_de_id`

`UUID NULL`, espelha o campo acima — carimbado no convite no momento da criação, copiado para o
`User.assistente_de_id` quando o convite é aceito (`aceitar_convite`).

## Núcleo de permissões: `app/core/rbac.py` (novo, sem tabela)

```python
_VISIBILIDADE_TOTAL = {Papel.DONO, Papel.GERENTE}

def escopo_visibilidade(user: User) -> uuid.UUID | None:
    """None = enxerga tudo do tenant. Um UUID = só recursos com corretor_id == esse valor."""
    if user.papel in _VISIBILIDADE_TOTAL:
        return None
    if user.papel == Papel.ASSISTENTE:
        return user.assistente_de_id or _SENTINELA_SEM_VINCULO  # RN3: nunca cai pra "vê tudo"
    return user.uuid  # CORRETOR

def corretor_id_efetivo(user: User) -> uuid.UUID:
    """A quem atribuir um Imovel/Lead recém-criado por este usuário."""
    if user.papel == Papel.ASSISTENTE:
        return user.assistente_de_id or _SENTINELA_SEM_VINCULO
    return user.uuid

def pode_excluir(owner_id: uuid.UUID, user: User) -> bool:
    if user.papel == Papel.ASSISTENTE:
        return False
    if user.papel in _VISIBILIDADE_TOTAL:
        return True
    return owner_id == user.uuid
```

`_SENTINELA_SEM_VINCULO` é um UUID fixo (`uuid.UUID(int=0)`) que nunca corresponde a um
`corretor_id` real — usado só no caso de borda (RN3) de um assistente sem vínculo, para nunca
comparar contra `None` (que faria `_garante_visivel`/filtros tratarem como "vê tudo").

## Invariantes

- **Invariante (RN2):** `imoveis/service.py`, `leads/service.py` e `dashboard/service.py` nunca
  comparam `user.papel` diretamente para decidir visibilidade — sempre via
  `escopo_visibilidade()`.
- **Invariante (RN4):** a checagem de exclusão (`pode_excluir`) é sempre adicional à de
  visibilidade (`obter_imovel` já chamado antes) — nunca a única guarda.

"""Barramento de eventos de domínio in-process e síncrono.

Módulos nunca importam o service de outro módulo diretamente (ver ARQUITETURA-REFERENCIA.md
§1) — em vez disso, publicam um evento e quem precisar reagir se inscreve como listener.
É síncrono (não uma fila) porque a reação (ex.: criar a license de um tenant novo) precisa
acontecer dentro da mesma transação de banco do evento que a originou.
"""

from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

Listener = Callable[..., Awaitable[None]]

_listeners: dict[str, list[Listener]] = defaultdict(list)


def on(event_name: str) -> Callable[[Listener], Listener]:
    def decorator(fn: Listener) -> Listener:
        _listeners[event_name].append(fn)
        return fn

    return decorator


async def emit(event_name: str, **kwargs: Any) -> None:
    for listener in _listeners[event_name]:
        await listener(**kwargs)

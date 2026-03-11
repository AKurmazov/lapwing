import asyncio
from collections.abc import Callable, Coroutine
from typing import Any
from dataclasses import dataclass

import pytest

from lapwing import Action, ActionBus, DuplicateHandlerError, NoHandlerError


@dataclass
class SomeAction(Action[int]):
    value: int


@dataclass
class OtherAction(Action[str]):
    value: str


async def test_dispatch_returns_correct_result() -> None:
    bus = ActionBus()

    @bus.handler(SomeAction)
    async def handle(action: SomeAction) -> int:
        return action.value * 2

    task = bus.dispatch(SomeAction(value=21))
    result = await task
    assert result == 42


async def test_dispatch_returns_asyncio_task() -> None:
    bus = ActionBus()

    @bus.handler(OtherAction)
    async def handle(action: OtherAction) -> str:
        return f"Hello, {action.value}!"

    task = bus.dispatch(OtherAction(value="Alice"))
    assert isinstance(task, asyncio.Task)
    assert await task == "Hello, Alice!"


async def test_middleware_runs_in_order() -> None:
    order: list[str] = []

    async def first_middleware(
        action: SomeAction, call_next: Callable[[SomeAction], Coroutine[Any, Any, int]]
    ) -> int:
        order.append("first_before")
        result = await call_next(action)
        order.append("first_after")
        return result

    async def second_middleware(
        action: SomeAction, call_next: Callable[[SomeAction], Coroutine[Any, Any, int]]
    ) -> int:
        order.append("second_before")
        result = await call_next(action)
        order.append("second_after")
        return result

    bus = ActionBus(middlewares=[first_middleware, second_middleware])

    @bus.handler(SomeAction)
    async def handle(action: SomeAction) -> int:
        order.append("handler")
        return action.value

    await bus.dispatch(SomeAction(value=1))

    assert order == [
        "first_before",
        "second_before",
        "handler",
        "second_after",
        "first_after",
    ]


async def test_middleware_can_modify_result() -> None:
    async def double_result(
        action: SomeAction, call_next: Callable[[SomeAction], Coroutine[Any, Any, int]]
    ) -> int:
        result = await call_next(action)
        return result * 2

    bus = ActionBus(middlewares=[double_result])

    @bus.handler(SomeAction)
    async def handle(action: SomeAction) -> int:
        return action.value

    result = await bus.dispatch(SomeAction(value=5))
    assert result == 10


def test_duplicate_handler_raises_at_decoration_time() -> None:
    bus = ActionBus()

    @bus.handler(SomeAction)
    async def first_handler(action: SomeAction) -> int:
        return action.value

    with pytest.raises(DuplicateHandlerError) as exc_info:

        @bus.handler(SomeAction)
        async def second_handler(action: SomeAction) -> int:
            return action.value

    assert exc_info.value.action_type is SomeAction


async def test_no_handler_raises_before_task_creation() -> None:
    bus = ActionBus()

    with pytest.raises(NoHandlerError) as exc_info:
        bus.dispatch(SomeAction(value=1))

    assert exc_info.value.action_type is SomeAction

import asyncio
from dataclasses import dataclass

import pytest

from lapwing import Event, EventBus


@dataclass
class SomeEvent(Event):
    id: str


@dataclass
class OtherEvent(Event):
    id: str


async def test_emit_returns_asyncio_task() -> None:
    bus = EventBus()

    @bus.listener(SomeEvent)
    async def on_some_event(event: SomeEvent) -> None:
        pass

    task = bus.emit(SomeEvent(id="123"))
    assert isinstance(task, asyncio.Task)
    await task


async def test_emit_calls_all_listeners() -> None:
    bus = EventBus()
    called: list[str] = []

    @bus.listener(SomeEvent)
    async def listener_a(event: SomeEvent) -> None:
        called.append("a")

    @bus.listener(SomeEvent)
    async def listener_b(event: SomeEvent) -> None:
        called.append("b")

    await bus.emit(SomeEvent(id="1"))
    assert sorted(called) == ["a", "b"]


async def test_emit_with_no_listeners_succeeds() -> None:
    bus = EventBus()
    await bus.emit(SomeEvent(id="1"))


async def test_emit_listener_failure_raises_exception_group() -> None:
    bus = EventBus()

    @bus.listener(SomeEvent)
    async def failing_listener(event: SomeEvent) -> None:
        raise ValueError("listener failed")

    task = bus.emit(SomeEvent(id="1"))
    with pytest.raises(ExceptionGroup) as exc_info:
        await task

    exceptions = exc_info.value.exceptions
    assert len(exceptions) == 1
    assert isinstance(exceptions[0], ValueError)
    assert str(exceptions[0]) == "listener failed"


async def test_emit_multiple_failing_listeners_all_surface() -> None:
    bus = EventBus()

    @bus.listener(SomeEvent)
    async def failing_a(event: SomeEvent) -> None:
        raise RuntimeError("error A")

    @bus.listener(SomeEvent)
    async def failing_b(event: SomeEvent) -> None:
        raise RuntimeError("error B")

    task = bus.emit(SomeEvent(id="1"))
    with pytest.raises(ExceptionGroup) as exc_info:
        await task

    messages = {str(e) for e in exc_info.value.exceptions}
    assert messages == {"error A", "error B"}


async def test_emit_only_triggers_listeners_for_matching_event_type() -> None:
    bus = EventBus()
    called: list[str] = []

    @bus.listener(SomeEvent)
    async def on_some_event(event: SomeEvent) -> None:
        called.append("some")

    @bus.listener(OtherEvent)
    async def on_other_event(event: OtherEvent) -> None:
        called.append("other")

    await bus.emit(SomeEvent(id="1"))
    assert called == ["some"]

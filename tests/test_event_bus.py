import asyncio
from dataclasses import dataclass

import pytest

from lapwing import Event, EventBus, ListenerFunc


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


async def test_middleware_none_and_empty_list_are_equivalent() -> None:
    called_a: list[str] = []
    called_b: list[str] = []

    bus_a = EventBus(middlewares=None)
    bus_b = EventBus(middlewares=[])

    @bus_a.listener(SomeEvent)
    async def listener_a(event: SomeEvent) -> None:
        called_a.append("a")

    @bus_b.listener(SomeEvent)
    async def listener_b(event: SomeEvent) -> None:
        called_b.append("b")

    await bus_a.emit(SomeEvent(id="1"))
    await bus_b.emit(SomeEvent(id="1"))

    assert called_a == ["a"]
    assert called_b == ["b"]


async def test_middleware_receives_event_and_calls_next() -> None:
    called: list[str] = []

    async def mw(event: SomeEvent, next: ListenerFunc) -> None:
        called.append("middleware")
        await next(event)

    bus = EventBus(middlewares=[mw])

    @bus.listener(SomeEvent)
    async def on_event(event: SomeEvent) -> None:
        called.append("listener")

    await bus.emit(SomeEvent(id="1"))
    assert called == ["middleware", "listener"]


async def test_middleware_can_short_circuit() -> None:
    called: list[str] = []

    async def blocking_mw(event: SomeEvent, next: ListenerFunc) -> None:
        called.append("middleware")
        # does not call next

    bus = EventBus(middlewares=[blocking_mw])

    @bus.listener(SomeEvent)
    async def on_event(event: SomeEvent) -> None:
        called.append("listener")

    await bus.emit(SomeEvent(id="1"))
    assert called == ["middleware"]


async def test_middleware_order_is_outermost_first() -> None:
    order: list[str] = []

    async def first_mw(event: SomeEvent, next: ListenerFunc) -> None:
        order.append("first_before")
        await next(event)
        order.append("first_after")

    async def second_mw(event: SomeEvent, next: ListenerFunc) -> None:
        order.append("second_before")
        await next(event)
        order.append("second_after")

    bus = EventBus(middlewares=[first_mw, second_mw])

    @bus.listener(SomeEvent)
    async def on_event(event: SomeEvent) -> None:
        order.append("listener")

    await bus.emit(SomeEvent(id="1"))
    assert order == [
        "first_before",
        "second_before",
        "listener",
        "second_after",
        "first_after",
    ]


async def test_multiple_middlewares_compose_correctly() -> None:
    log: list[str] = []

    async def logger_mw(event: SomeEvent, next: ListenerFunc) -> None:
        log.append(f"log:{event.id}")
        await next(event)

    async def tag_mw(event: SomeEvent, next: ListenerFunc) -> None:
        log.append("tag")
        await next(event)

    bus = EventBus(middlewares=[logger_mw, tag_mw])

    @bus.listener(SomeEvent)
    async def on_event(event: SomeEvent) -> None:
        log.append("listener")

    await bus.emit(SomeEvent(id="42"))
    assert log == ["log:42", "tag", "listener"]


async def test_middleware_applied_independently_per_listener() -> None:
    """Each listener gets its own pipeline — middleware runs once per listener, independently."""
    invocations: list[str] = []

    async def short_circuit_mw(event: SomeEvent, next: ListenerFunc) -> None:
        invocations.append("mw")
        # Never calls next — blocks every listener independently

    bus = EventBus(middlewares=[short_circuit_mw])

    @bus.listener(SomeEvent)
    async def listener_a(event: SomeEvent) -> None:
        invocations.append("a")

    @bus.listener(SomeEvent)
    async def listener_b(event: SomeEvent) -> None:
        invocations.append("b")

    await bus.emit(SomeEvent(id="1"))
    # Middleware ran once per listener (2 times), neither listener was called
    assert invocations == ["mw", "mw"]


async def test_middleware_invoked_once_per_listener_per_emit() -> None:
    """2 listeners × 1 middleware → 2 middleware invocations."""
    invocations: list[str] = []

    async def counting_mw(event: SomeEvent, next: ListenerFunc) -> None:
        invocations.append("mw")
        await next(event)

    bus = EventBus(middlewares=[counting_mw])

    @bus.listener(SomeEvent)
    async def listener_a(event: SomeEvent) -> None:
        pass

    @bus.listener(SomeEvent)
    async def listener_b(event: SomeEvent) -> None:
        pass

    await bus.emit(SomeEvent(id="1"))
    assert len(invocations) == 2


async def test_middleware_not_invoked_with_no_listeners() -> None:
    invocations: list[str] = []

    async def counting_mw(event: SomeEvent, next: ListenerFunc) -> None:
        invocations.append("mw")
        await next(event)

    bus = EventBus(middlewares=[counting_mw])
    await bus.emit(SomeEvent(id="1"))
    assert invocations == []


async def test_multiple_emits_are_independent() -> None:
    """Middleware invocation count accumulates correctly — no pipeline caching."""
    invocations: list[str] = []

    async def counting_mw(event: SomeEvent, next: ListenerFunc) -> None:
        invocations.append("mw")
        await next(event)

    bus = EventBus(middlewares=[counting_mw])

    @bus.listener(SomeEvent)
    async def on_event(event: SomeEvent) -> None:
        pass

    await bus.emit(SomeEvent(id="1"))
    await bus.emit(SomeEvent(id="2"))
    assert len(invocations) == 2


async def test_middleware_exception_surfaces_in_exception_group() -> None:
    async def raising_mw(event: SomeEvent, next: ListenerFunc) -> None:
        raise RuntimeError("middleware error")

    bus = EventBus(middlewares=[raising_mw])

    @bus.listener(SomeEvent)
    async def on_event(event: SomeEvent) -> None:
        pass

    with pytest.raises(ExceptionGroup) as exc_info:
        await bus.emit(SomeEvent(id="1"))

    assert any(
        isinstance(e, RuntimeError) and str(e) == "middleware error"
        for e in exc_info.value.exceptions
    )

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from ._types import Event

type ListenerFunc = Callable[[Any], Coroutine[Any, Any, None]]
type ListenerMiddlewareFunc = Callable[[Any, ListenerFunc], Coroutine[Any, Any, None]]


class EventBus:
    """Broadcasts events to all registered async listeners concurrently."""

    def __init__(self, middlewares: list[ListenerMiddlewareFunc] | None = None) -> None:
        self._listeners: dict[type, list[ListenerFunc]] = {}
        self._middlewares: list[ListenerMiddlewareFunc] = (
            list(reversed(middlewares)) if middlewares else []
        )

    def listener[E: Event](
        self, event_type: type[E]
    ) -> Callable[[ListenerFunc], ListenerFunc]:
        """Registers an async listener for the given event type.

        Multiple listeners may be registered for the same event type.

        Args:
            event_type: The event class this listener will handle.

        Returns:
            A decorator that registers the wrapped function and returns it unchanged.
        """

        def decorator(func: ListenerFunc) -> ListenerFunc:
            self._listeners.setdefault(event_type, []).append(func)
            return func

        return decorator

    def _build_pipeline(self, listener: ListenerFunc) -> ListenerFunc:
        """Wraps listener with registered middlewares.

        Args:
            listener: The innermost listener to wrap.

        Returns:
            A callable representing the full middleware pipeline.
        """
        pipeline: ListenerFunc = listener
        for mw in self._middlewares:
            # Capture current pipeline in closure
            inner = pipeline
            current_mw = mw

            async def step(
                event: Any,
                _inner: ListenerFunc = inner,
                _mw: ListenerMiddlewareFunc = current_mw,
            ) -> None:
                await _mw(event, _inner)

            pipeline = step
        return pipeline

    def emit(self, event: Event) -> asyncio.Task[None]:
        """Emits an event, returning an asyncio.Task.

        All registered listeners run concurrently via asyncio.TaskGroup,
        each wrapped in the middleware pipeline.
        Events with no listeners succeed silently.

        Args:
            event: The event instance to broadcast.

        Returns:
            An asyncio.Task that resolves when all listeners have completed.

        Raises:
            ExceptionGroup: One or more listeners (or their middleware) raised an exception.
        """
        event_type = type(event)
        listeners = self._listeners.get(event_type, [])

        async def run() -> None:
            if not listeners:
                return
            async with asyncio.TaskGroup() as tg:
                for listener in listeners:
                    pipeline = self._build_pipeline(listener)
                    tg.create_task(pipeline(event))

        return asyncio.create_task(run())

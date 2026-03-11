import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from ._types import Event

type ListenerFunc = Callable[[Any], Coroutine[Any, Any, None]]


class EventBus:
    """Broadcasts events to all registered async listeners concurrently."""

    def __init__(self) -> None:
        self._listeners: dict[type, list[ListenerFunc]] = {}

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

    def emit(self, event: Event) -> asyncio.Task[None]:
        """Emits an event, returning an asyncio.Task.

        All registered listeners run concurrently via asyncio.TaskGroup.
        Events with no listeners succeed silently.

        Args:
            event: The event instance to broadcast.

        Returns:
            An asyncio.Task that resolves when all listeners have completed.

        Raises:
            ExceptionGroup: One or more listeners raised an exception.
        """
        event_type = type(event)
        listeners = self._listeners.get(event_type, [])

        async def run() -> None:
            if not listeners:
                return
            async with asyncio.TaskGroup() as tg:
                for listener in listeners:
                    tg.create_task(listener(event))

        return asyncio.create_task(run())

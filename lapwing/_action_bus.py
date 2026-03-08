from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from ._exceptions import DuplicateHandlerError, NoHandlerError
from ._types import Action, T

HandlerFunc = Callable[[Any], Awaitable[Any]]
MiddlewareFunc = Callable[[Any, Callable[[Any], Awaitable[Any]]], Awaitable[Any]]

A = TypeVar("A", bound=Action[Any])


class ActionBus:
    """Dispatches actions to exactly one registered async handler, with optional middlewares."""

    def __init__(self, middlewares: list[MiddlewareFunc] | None = None) -> None:
        """Args:
        middlewares: Pipeline applied to every dispatched action. Middlewares wrap
            each other in list order: ``middlewares[0]`` wraps ``middlewares[1]``,
            which wraps the handler.
        """
        self._handlers: dict[type, HandlerFunc] = {}
        self._middlewares: list[MiddlewareFunc] = (
            list(reversed(middlewares)) if middlewares else []
        )

    def handler(self, action_type: type[A]) -> Callable[[HandlerFunc], HandlerFunc]:
        """Registers a single async handler for the given action type.

        Args:
            action_type: The action class this handler will process.

        Returns:
            A decorator that registers the wrapped function and returns it unchanged.

        Raises:
            DuplicateHandlerError: A handler for action_type is already registered.
        """

        def decorator(func: HandlerFunc) -> HandlerFunc:
            if action_type in self._handlers:
                raise DuplicateHandlerError(action_type)
            self._handlers[action_type] = func
            return func

        return decorator

    def _build_pipeline(self, handler: HandlerFunc) -> HandlerFunc:
        """Wraps handler with registered middlewares.

        Args:
            handler: The innermost handler to wrap.

        Returns:
            A callable representing the full middleware pipeline.
        """
        pipeline: HandlerFunc = handler
        for mw in self._middlewares:
            # Capture current pipeline in closure
            inner = pipeline
            current_mw = mw

            async def step(
                action: Any,
                _inner: HandlerFunc = inner,
                _mw: MiddlewareFunc = current_mw,
            ) -> Any:
                return await _mw(action, _inner)

            pipeline = step
        return pipeline

    def dispatch(self, action: Action[T]) -> asyncio.Task[T]:
        """Dispatches an action, returning an asyncio.Task.

        Raises NoHandlerError eagerly before creating a task if no handler is registered.

        Args:
            action: The action instance to dispatch.

        Returns:
            An asyncio.Task that resolves to the handler's return value.

        Raises:
            NoHandlerError: No handler is registered for the action's type.
        """
        action_type = type(action)
        handler = self._handlers.get(action_type)
        if handler is None:
            raise NoHandlerError(action_type)

        pipeline = self._build_pipeline(handler)

        async def run() -> T:
            return await pipeline(action)

        return asyncio.create_task(run())

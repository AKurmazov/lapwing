# commands — Action/Event Bus Library Design

**Date:** 2026-03-05

## Context

A Python library that decouples "intent to do something" from "actual execution".
Not classic CQRS (no read/write segregation, no event sourcing):

- **Actions**: dispatch to exactly one handler, return a typed result
- **Events**: broadcast to all registered listeners, return nothing

Inspired by C# MediatR + event bus. Async-first (Python 3.14, asyncio). Pydantic models for type safety.

---

## Core Types

### `Action[T]`
- Inherits `BaseModel` and `Generic[T]`
- `T` is the return type (phantom type — no runtime field, type-checker only)
- Users subclass to define action payloads

### `Event`
- Inherits `BaseModel`
- Users subclass to define event payloads

---

## ActionBus

Handles dispatch of one action to exactly one registered handler.

### Registration
```python
@bus.handler(ActionType)
async def handle(action: ActionType) -> ReturnType: ...
```
- Raises `DuplicateHandlerError` immediately at decoration time if a handler is already registered.

### Middleware
```python
@bus.middleware
async def mw(action, call_next):
    result = await call_next(action)
    return result
```
- Middleware wraps the handler in registration order (first registered = outermost).

### Dispatch
```python
task = bus.dispatch(action)  # asyncio.Task[T]
```
- Raises `NoHandlerError` eagerly (before creating a task) if no handler registered.
- Uses `asyncio.create_task(...)` to schedule execution immediately.
- Middleware pipeline runs inside the task coroutine.

---

## EventBus

Broadcasts one event to all registered listeners concurrently.

### Registration
```python
@bus.listener(EventType)
async def on_event(event: EventType) -> None: ...
```
- Multiple listeners can be registered for the same event type.

### Emit
```python
task = bus.emit(event)  # asyncio.Task[None]
```
- Uses `asyncio.create_task(...)` to schedule immediately.
- Internally uses `asyncio.TaskGroup` so each listener runs as its own task.
- If any listener raises, `ExceptionGroup` propagates.
- Events with no listeners silently succeed (no error).

---

## Mediator

Thin facade combining `ActionBus` and `EventBus`.

```python
mediator = Mediator(action_bus, event_bus)
task = mediator.dispatch(action)  # delegates to action_bus
task = mediator.emit(event)       # delegates to event_bus
```

---

## Exceptions

| Exception | When raised |
|-----------|-------------|
| `NoHandlerError` | `dispatch()` called with no handler registered for that action type |
| `DuplicateHandlerError` | `@handler(...)` used twice for the same action type |

---

## File Structure

```
src/commands/
├── __init__.py        # public API exports
├── _types.py          # Action[T], Event base classes
├── _action_bus.py     # ActionBus implementation
├── _event_bus.py      # EventBus implementation
├── _mediator.py       # Mediator facade
└── _exceptions.py     # NoHandlerError, DuplicateHandlerError
```

---

## Dependencies

- `pydantic>=2` — only non-stdlib dependency, for `BaseModel`
- Python `>=3.14` — asyncio, `TaskGroup` (3.11+), `asyncio.create_task`

---

## Design Decisions

1. **`dispatch` is eager about errors**: `NoHandlerError` raised synchronously so callers don't have to await to discover misconfiguration.
2. **`DuplicateHandlerError` at decoration time**: catches bugs at module load, not at runtime.
3. **Phantom type `T`**: `Action[T]` carries return type info for static analysis only; no runtime enforcement needed.
4. **`TaskGroup` in `emit`**: ensures all listeners run concurrently and all exceptions surface together via `ExceptionGroup`.
5. **Middleware stack**: registered middlewares wrap the handler — first registered is outermost, last is innermost (closest to handler). This mirrors typical middleware patterns (e.g., Django, Express).

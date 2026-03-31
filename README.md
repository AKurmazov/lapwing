# lapwing

`lapwing` is a library providing lightweight async message-passing building blocks: an action bus and an event bus.

> **Why lapwing?** The lapwing is a bird renowned for its piercing, far-carrying calls — it detects disturbances and signals them immediately to others nearby. This mirrors the library's purpose: one part of a system raises a signal, and the right listeners respond, without the sender knowing or caring who they are.

## Core Concepts

The library addresses a common architectural need: decoupling the sender of a message from its handler. Instead of calling functions directly, you define typed messages and register handlers separately, keeping concerns isolated and code testable.

All operations are async-first and return `asyncio.Task`, giving the caller control over when to await.

## Key Primitives

**Action**: A subclass carrying a phantom type parameter `T` — used only by the type checker to annotate what the handler returns. Define one per action.

**Event**: A subclass representing something that has happened. Multiple listeners may react to the same event.

**ActionBus**: Dispatches an action to exactly one registered async handler. Raises `NoHandlerError` eagerly if no handler is registered. Supports an optional middleware pipeline.

**EventBus**: Broadcasts an event to all registered async listeners concurrently via `asyncio.TaskGroup`. Succeeds silently if no listeners are registered. Raises `ExceptionGroup` if any listener fails. Supports an optional middleware pipeline applied independently to each listener.

## Usage

### ActionBus

Middlewares wrap the handler pipeline in list order — `middlewares[0]` is outermost.

> **NOTE:** Middlewares apply to all action types on a bus and must preserve the return type of each concrete action's handler.

```python
from dataclasses import dataclass

from lapwing import Action, ActionBus


@dataclass
class CreateUser(Action[int]):
    username: str
    email: str


async def logging_middleware(action, call_next):
    print(f"Dispatching {type(action).__name__}")
    result = await call_next(action)
    print("Done")
    return result


bus = ActionBus(middlewares=[logging_middleware])


@bus.handler(CreateUser)
async def handle_create_user(action: CreateUser) -> int:
    user = await db.insert(action.username, action.email)
    return user.id


user_id = await bus.dispatch(CreateUser(username="alice", email="alice@example.com"))
```

### EventBus

Middlewares wrap each listener independently in list order — `middlewares[0]` is outermost.

> **NOTE:** Middlewares apply to every listener on a bus and must preserve the return type of each concrete event's listener (`None`). Each listener gets its own pipeline; a short-circuit or failure in one does not affect others.

```python
from dataclasses import dataclass

from lapwing import Event, EventBus


@dataclass
class UserCreated(Event):
    user_id: int


async def logging_middleware(event, call_next):
    print(f"Handling {type(event).__name__}")
    await call_next(event)


bus = EventBus(middlewares=[logging_middleware])


@bus.listener(UserCreated)
async def send_welcome_email(event: UserCreated) -> None:
    await mailer.send_welcome(event.user_id)


@bus.listener(UserCreated)
async def write_audit_log(event: UserCreated) -> None:
    await audit.log(f"User {event.user_id} created")


await bus.emit(UserCreated(user_id=42))
```

## Installation

```bash
uv add lapwing
```

## Requirements

Python 3.13+

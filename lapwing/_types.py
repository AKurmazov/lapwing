from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Action(BaseModel, Generic[T]):
    """Base class for all actions.

    T is a phantom type parameter used only by the type checker to annotate
    the return type of the handler that processes this action.
    """

    model_config = {"arbitrary_types_allowed": True}


class Event(BaseModel):
    """Base class for all events."""

from dataclasses import dataclass


@dataclass
class Action[T]:
    """Base class for all actions.

    T is a phantom type parameter used only by the type checker to annotate
    the return type of the handler that processes this action.
    """


@dataclass
class Event:
    """Base class for all events."""

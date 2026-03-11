from typing import Any

from ._types import Action


class NoHandlerError(Exception):
    """No handler is registered for the dispatched action type.

    Attributes:
        action_type: The action class that had no registered handler.
    """

    def __init__(self, action_type: type[Action[Any]]) -> None:
        super().__init__(
            f"No handler registered for action type: {action_type.__name__!r}"
        )
        self.action_type = action_type


class DuplicateHandlerError(Exception):
    """A handler for this action type is already registered.

    Attributes:
        action_type: The action class that was registered more than once.
    """

    def __init__(self, action_type: type[Action[Any]]) -> None:
        super().__init__(
            f"Handler already registered for action type: {action_type.__name__!r}"
        )
        self.action_type = action_type

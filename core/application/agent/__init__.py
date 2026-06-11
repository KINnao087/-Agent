"""Interactive agent application package."""

__all__ = ["CliChatService", "create_cli_chat_service"]


def __getattr__(name: str):
    if name in __all__:
        from .chat_service import CliChatService, create_cli_chat_service

        return {
            "CliChatService": CliChatService,
            "create_cli_chat_service": create_cli_chat_service,
        }[name]
    raise AttributeError(name)

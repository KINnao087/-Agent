from __future__ import annotations

from .token_counter import count_message_tokens


def _has_user_message(messages: list[dict]) -> bool:
    return any(message.get("role") == "user" for message in messages)


def _latest_user_message(messages: list[dict]) -> dict | None:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message
    return None


def _restore_latest_user_if_missing(window: list[dict], source_messages: list[dict], model: str) -> tuple[list[dict], int]:
    """Keep at least one user message for providers that reject user-less requests."""
    if _has_user_message(window):
        total = sum(count_message_tokens(message, model) for message in window)
        return window, total

    latest_user = _latest_user_message(source_messages)
    if latest_user is None:
        total = sum(count_message_tokens(message, model) for message in window)
        return window, total

    selected_ids = {id(message) for message in window}
    selected_ids.add(id(latest_user))
    restored = [
        message
        for message in source_messages
        if id(message) in selected_ids
    ]
    total = sum(count_message_tokens(message, model) for message in restored)
    return restored, total


def calc_total_tokens(messages: list[dict], model: str) -> int:
    """统计会话中所有非 system 消息的 token 总数。"""
    return sum(
        count_message_tokens(message, model)
        for message in messages
        if message.get("role") != "system"
    )


def trim_messages(
    messages: list[dict],
    keep_last: int,
    model: str,
    cached_total_tokens: int | None = None,
    return_total: bool = False,
):
    """在 token 预算内保留 system 消息和最近的上下文窗口。"""
    if cached_total_tokens is not None and cached_total_tokens <= keep_last:
        return (messages, cached_total_tokens) if return_total else messages

    if not messages:
        return ([], 0) if return_total else []

    system_messages = [message for message in messages if message.get("role") == "system"]
    other_messages = [message for message in messages if message.get("role") != "system"]
    if not other_messages:
        return (system_messages, 0) if return_total else system_messages

    window: list[dict] = []
    total = 0
    index = len(other_messages) - 1

    while index >= 0:
        message = other_messages[index]
        role = message.get("role")

        if role == "tool" and index - 1 >= 0 and other_messages[index - 1].get("role") == "assistant":
            pair = [other_messages[index - 1], other_messages[index]]
            pair_tokens = count_message_tokens(pair[0], model) + count_message_tokens(pair[1], model)
            if total + pair_tokens <= keep_last:
                window[0:0] = pair
                total += pair_tokens
                index -= 2
                continue
            break

        message_tokens = count_message_tokens(message, model)
        if total + message_tokens <= keep_last:
            window.insert(0, message)
            total += message_tokens
            index -= 1
            continue

        index -= 1

    if not window:
        last = other_messages[-1]
        if last.get("role") == "tool" and len(other_messages) >= 2 and other_messages[-2].get("role") == "assistant":
            window = [other_messages[-2], other_messages[-1]]
        else:
            window = [last]
        total = sum(
            count_message_tokens(message, model)
            for message in window
            if message.get("role") != "system"
        )

    window, total = _restore_latest_user_if_missing(window, other_messages, model)
    trimmed = system_messages + window
    return (trimmed, total) if return_total else trimmed


def append_message(
    messages: list[dict],
    message: dict,
    total_tokens: int,
    keep_last: int,
    model: str,
    auto_trim: bool = False,
):
    """追加一条消息，并在需要时按预算裁剪历史。"""
    messages.append(message)
    if message.get("role") != "system":
        total_tokens += count_message_tokens(message, model)

    if auto_trim:
        messages, total_tokens = trim_messages(
            messages,
            keep_last=keep_last,
            model=model,
            cached_total_tokens=total_tokens,
            return_total=True,
        )
    return messages, total_tokens

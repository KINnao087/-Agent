from __future__ import annotations

from core.infrastructure.ai.prompts import CLI_AGENT_PROMPT


def test_agent_prompt_requires_fixed_default_full_review_sequence() -> None:
    system_message = CLI_AGENT_PROMPT.invoke({"messages": []}).to_messages()[0].content

    assert "用户未指定专项范围" in system_message
    assert "find_contract_review" in system_message
    assert "check_basic_info" in system_message
    assert "check_text_integrity" in system_message
    assert "check_contract_seals" in system_message
    assert "check_cross_page_seal" in system_message
    assert "check_contract_authenticity" in system_message
    assert "write_review_report" in system_message
    assert "不得省略" in system_message

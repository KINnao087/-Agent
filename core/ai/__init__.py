"""AI 包对外暴露的统一入口。"""

from .agent_loop import run_main_loop
from .config import AgentConfig, DeepSeekApiConfig, load_agent_config
from .json_parser import extract_json_text, parse_json_object
from .llm_client import build_provider, deepseek_chat, normalize_provider_name
from .logger import LogLevel, get_logger, set_log_level
from .message_store import append_message, calc_total_tokens, trim_messages
from .session import AgentRunner, ConversationSession, build_initial_session
from .tasks import run_message_and_get_reply, structure_ocr_json
from .token_counter import count_message_tokens, estimate_tokens

__all__ = [
    "AgentConfig",  # AI 运行总配置对象。
    "AgentRunner",  # 面向业务层的 AI 运行器。
    "ConversationSession",  # 会话上下文对象。
    "DeepSeekApiConfig",  # DeepSeek API 专用配置对象。
    "LogLevel",  # 日志级别枚举。
    "append_message",  # 向消息历史追加一条消息。
    "build_initial_session",  # 构建带初始 system 上下文的会话。
    "build_provider",  # 根据配置创建底层模型 provider。
    "calc_total_tokens",  # 计算当前消息列表的 token 总数。
    "count_message_tokens",  # 统计单条消息的 token 数。
    "deepseek_chat",  # 把一次聊天请求转发给当前 provider。
    "estimate_tokens",  # 估算任意文本的 token 数。
    "extract_json_text",  # 从模型回复中提取 JSON 文本。
    "get_logger",  # 获取具名 logger。
    "load_agent_config",  # 从配置文件加载 AI 配置。
    "normalize_provider_name",  # 归一化 provider 名称。
    "parse_json_object",  # 把模型回复解析成 JSON 对象。
    "run_main_loop",  # 底层任务循环执行入口。
    "run_message_and_get_reply",  # 单轮发送消息并返回 AI 回复文本。
    "set_log_level",  # 设置默认日志级别。
    "structure_ocr_json",  # 将 OCR JSON 交给 AI 并返回结构化 JSON。
    "trim_messages",  # 按 token 上限裁剪消息历史。
]

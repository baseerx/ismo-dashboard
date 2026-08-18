import logging
from typing import Dict, List, Optional

import ollama

from app.config.settings import settings

logger = logging.getLogger(__name__)

_client = ollama.Client(host=settings.OLLAMA_BASE_URL)


def chat_with_tools(
    messages: List[Dict],
    tools: Optional[List[Dict]] = None,
    max_tokens: int = 512,
    temperature: float = 0.3,
) -> Dict:
    """
    Returns the RAW message dict from Ollama (not just the text), so the
    caller can inspect message.get("tool_calls") to decide whether to
    execute tools before producing a final answer.
    """
    logger.info("chat_with_tools: model=%s messages=%d tools=%d",
                settings.MODEL_NAME, len(messages), len(tools) if tools else 0)

    response = _client.chat(
        model=settings.MODEL_NAME,
        messages=messages,
        tools=tools,
        options={"num_predict": max_tokens, "temperature": temperature},
    )
    message = response["message"]

    logger.info("chat_with_tools: response tool_calls=%s content_preview=%r",
                bool(message.get("tool_calls")), (message.get("content") or "")[:150])

    return message


def generate_reply(
    messages: List[Dict[str, str]],
    max_tokens: int = 512,
    temperature: float = 0.3,
) -> str:
    """Plain text reply, no tools - kept for anything that doesn't need tool-calling."""
    message = chat_with_tools(messages, tools=None, max_tokens=max_tokens, temperature=temperature)
    return message["content"]
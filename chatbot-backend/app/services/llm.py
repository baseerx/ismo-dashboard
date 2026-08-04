from typing import Dict, List

import ollama

from app.config.settings import settings

_client = ollama.Client(host=settings.OLLAMA_BASE_URL)


def generate_reply(
    messages: List[Dict[str, str]],
    max_tokens: int = 512,
    temperature: float = 0.3,
) -> str:
    """
    Thin wrapper around the local Ollama chat endpoint for the configured
    chat model (llama3.1:8b by default). Requires Ollama running locally
    with the model pulled: `ollama pull llama3.1:8b`.

    messages: [{"role": "system"|"user"|"assistant", "content": str}, ...]
    """
    response = _client.chat(
        model=settings.MODEL_NAME,
        messages=messages,
        options={
            "num_predict": max_tokens,
            "temperature": temperature,
        },
    )
    return response["message"]["content"]
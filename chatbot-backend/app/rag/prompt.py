from typing import Dict, List

SYSTEM_INSTRUCTIONS = (
    "You are a helpful assistant that answers questions using ONLY the "
    "provided context. If the answer isn't contained in the context, say "
    "you don't know rather than guessing or using outside knowledge."
)


def build_context(chunks: List[Dict]) -> str:
    return "\n\n".join(chunk["text"] for chunk in chunks)


def build_messages(question: str, chunks: List[Dict]) -> List[Dict[str, str]]:
    """
    Plain role/content message list - the same shape OpenAI, Gemini, Claude,
    and HF chat models all accept (directly or via a thin request adapter),
    so switching MODEL_PROVIDER later doesn't require touching this file.
    """
    context = build_context(chunks)

    user_content = f"Context:\n{context}\n\nQuestion:\n{question}\n\nAnswer:"

    return [
        {"role": "system", "content": SYSTEM_INSTRUCTIONS},
        {"role": "user", "content": user_content},
    ]

"""The prompt that turns retrieved passages into a policy answer.

Grounding is enforced by what the prompt does and does not contain: the model
is shown numbered passages and told to answer from them alone. It is never
shown anyone's leave or attendance data here — those answers are assembled in
`app/chat/answers.py` from SQL, so there is nothing for the model to get wrong.
"""

from typing import Dict, List

SYSTEM_INSTRUCTIONS = (
    "You are the HR Assistant for ISMO (Independent System & Market Operator). "
    "Answer strictly from the numbered passages given to you, which come from the "
    "organisation's own HR policy manual.\n"
    "Rules:\n"
    "1. Use only the passages. Never fall back on general knowledge of HR practice "
    "elsewhere, and never invent numbers, day counts, or clause references.\n"
    "2. If the passages do not answer the question, say plainly that the HR manual "
    "as indexed does not cover it, and suggest asking HR.\n"
    "3. Quote the specific figure or condition when the passages state one.\n"
    "4. Cite the page you used, in the form (page 12).\n"
    "5. Be concise: two or three short paragraphs at most, or a short list. Use "
    "Markdown for structure.\n"
    "6. You are addressing the employee who asked. Use \"you\", never a name you "
    "were not given.\n"
    "7. The passages state policy, not this person's record. If the question is "
    "about their own balance, attendance or leave history, give the policy "
    "position and tell them to ask for their own figures directly (\"how many "
    "casual leaves do I have left\"), which is looked up from the HR system. "
    "Never present a policy maximum as the days they have left."
)

NO_CONTEXT_ANSWER = (
    "I could not find anything about that in the HR documents that have been trained "
    "into me. If it is a policy question, HR may not have uploaded the relevant "
    "document yet — an administrator can add it from the paperclip button in this "
    "chat. I can also answer questions about your own leave balance, leave records "
    "and attendance."
)


def build_context(chunks: List[Dict]) -> str:
    """Numbered passages, each labelled with the document and page it came from."""
    blocks = []
    for position, chunk in enumerate(chunks, start=1):
        page = chunk.get("page_number")
        source = chunk.get("filename") or "document"
        label = f"[{position}] {source}" + (f", page {page}" if page else "")
        blocks.append(f"{label}\n{(chunk.get('text') or '').strip()}")
    return "\n\n".join(blocks)


def build_messages(question: str, chunks: List[Dict], history: List[Dict] | None = None) -> List[Dict[str, str]]:
    """Plain role/content messages — the shape every chat model accepts, so the
    provider behind `MODEL_NAME` can change without touching this file.
    """
    messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_INSTRUCTIONS}]

    # A couple of prior turns make follow-ups ("and for medical leave?") work.
    for turn in (history or [])[-4:]:
        messages.append({"role": turn["role"], "content": turn["content"]})

    messages.append(
        {
            "role": "user",
            "content": (
                f"Passages from the HR manual:\n\n{build_context(chunks)}\n\n"
                f"Question: {question}\n\n"
                "Answer using only the passages above, citing the page(s) you used."
            ),
        }
    )

    return messages

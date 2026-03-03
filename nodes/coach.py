"""
Coach node: erklärt Methoden mit vollem Kontext aus der tools.json.
Nutzt ToolsRegistry.format_for_llm() für strukturierte Prompts.
"""

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from state import CoachState
from tools_registry import ToolsRegistry

#_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)

from langchain_community.chat_models import ChatOllama

_llm = ChatOllama(
    model="llama3.1:8b-instruct-q4_K_M",
    temperature=0,
    timeout=60,
    max_retries=1
)

SYSTEM_PROMPT = """\
Du bist ein einfühlsamer und motivierender Lern-Coach für Studierende.
Antworte immer auf Deutsch, kurz und konkret (max. 200 Wörter).

Dir werden strukturierte Informationen zu einer oder mehreren Lernmethoden bereitgestellt.
Nutze diese als Grundlage für deine Antwort – erfinde keine Schritte oder Beispiele dazu.

Wenn du eine Methode erklärst:
- Beantworte die Frage des Nutzers direkt
- Verweise auf konkrete Schritte oder das Beispiel aus der Methode
- Gib wenn nötig einen Tipp oder benenne einen häufigen Fehler
- Bleib motivierend und auf Augenhöhe
"""


def _build_tool_context(state: CoachState) -> str:
    """
    Baut den Kontext-String aus der ToolsRegistry.
    Bevorzugt das chosen_method, fällt auf selected_methods zurück.
    """
    registry = ToolsRegistry.get()
    chosen = state.get("chosen_method")
    methods = state.get("selected_methods") or []

    if chosen:
        # Vollständiger Kontext für die aktive Methode
        return registry.format_for_llm(chosen)

    if methods:
        # Kurzer Kontext für beide zur Auswahl stehenden Methoden
        parts = [registry.format_for_llm(m) for m in methods]
        return "\n\n---\n\n".join(parts)

    return ""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

def coach_explain_node(state: CoachState) -> dict:
    """
    Answer a user question with full method context.
    Robust fixes:
    - If pending_question is empty, fall back to last human message.
    - Ensure the question is present at the end of the prompt sequence.
    - Always return an AIMessage even on LLM error (so API never returns empty).
    """
    # 1) Get question
    question = (state.get("pending_question") or "").strip()
    if not question:
        # fallback: last human message text
        for m in reversed(state.get("messages", [])):
            if isinstance(m, HumanMessage):
                question = (m.content or "").strip()
                break

    tool_context = _build_tool_context(state)

    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    if tool_context:
        messages.append(
            SystemMessage(content=f"## Verfügbare Methoden-Informationen\n\n{tool_context}")
        )

    # 2) Add history (keep last N for context)
    history = [
        m for m in state.get("messages", [])[-8:]
        if isinstance(m, (HumanMessage, AIMessage))
    ]
    messages.extend(history)

    # 3) Ensure question is the last human message in the prompt
    if question:
        if not messages or not isinstance(messages[-1], HumanMessage) or (messages[-1].content or "").strip() != question:
            messages.append(HumanMessage(content=question))
    else:
        # If still empty, ask a clarifying question instead of returning nothing
        return {
            "messages": [AIMessage(content="Welche Methode meinst du genau und was soll ich dazu erklären? (z.B. Ziel, Schritte, Dauer, Beispiel) ")],
            "pending_question": None,
        }

    # 4) Call LLM safely
    try:
        response = _llm.invoke(messages)
        content = (response.content or "").strip()
        if not content:
            content = "Ich konnte gerade keine Antwort generieren. Kannst du die Frage zur Methode noch einmal kurz anders formulieren?"
    except Exception as e:
        content = f"Ich hatte gerade ein technisches Problem beim Generieren der Erklärung ({type(e).__name__}). Bitte versuch es nochmal."

    return {
        "messages": [AIMessage(content=content)],
        "pending_question": None,
    }
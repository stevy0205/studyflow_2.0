"""
Router functions for the Coach Bot graph.
Each function receives the current state and returns a string key
that LangGraph uses to route to the next node.
"""

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from state import CoachState, FeedbackCategory, InputType

#_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0,timeout=30,)

from langchain_community.chat_models import ChatOllama

_llm = ChatOllama(
    model="llama3.1:8b-instruct-q4_K_M",
    temperature=0,
    timeout=30,
    max_retries=1
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _last_human_text(state: CoachState) -> str:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return msg.content.strip().lower()
    return ""


def _classify_via_llm(text: str, prompt: str, options: list[str]) -> str:
    """Call the LLM to classify text into one of the given options."""
    result = _llm.invoke(
        f"{prompt}\n\nText: \"{text}\"\n\n"
        f"Antworte NUR mit einem der folgenden Wörter: {', '.join(options)}"
    )
    answer = result.content.strip().lower()
    for opt in options:
        if opt in answer:
            return opt
    return options[-1]  # fallback to last option


# ── Routers ────────────────────────────────────────────────────────────────────

def route_login(state: CoachState) -> str:
    """Route based on login status."""
    return "logged_in" if state.get("is_logged_in") else "guest"

def route_user_action(state: CoachState) -> str:
    """
    After displaying methods: did the user ask a question or choose a method?
    Checks state['user_action'] first, then classifies the last message.

    Fixes:
    - "erkläre methode 1/2" is treated as QUESTION (not choose_method)
    - choose_method only if input is exactly "1" or "2" OR explicit choose verbs
    - removes substring matching on "1"/"2" that caused loops/misroutes
    """
    action = state.get("user_action")
    if action in ("question", "choose_method"):
        return action

    text = _last_human_text(state)

    # 1) Question intent first (must win)
    if any(q in text for q in ["erklär", "erklaer", "erkläre", "wie", "was", "warum", "?"]):
        # store question so coach_explain_node can use it (optional but recommended)
        state["pending_question"] = text
        return "question"

    # 2) Method selection only if the user sent exactly "1" or "2"
    if text in ("1", "2"):
        methods = state.get("selected_methods", [])
        idx = int(text) - 1
        chosen = methods[idx] if 0 <= idx < len(methods) else (methods[0] if methods else None)
        state["chosen_method"] = chosen
        return "choose_method"

    # 3) Explicit "choose" verbs (no numeric substring matching)
    if any(kw in text for kw in ["wähle", "waehle", "nehme", "starte"]):
        methods = state.get("selected_methods", [])
        # If user wrote "methode 2" etc., handle that here safely
        if "methode 2" in text or "2." in text:
            idx = 1
        else:
            idx = 0
        chosen = methods[idx] if idx < len(methods) else (methods[0] if methods else None)
        state["chosen_method"] = chosen
        return "choose_method"

    return "question"


def route_start_or_question(state: CoachState) -> str:
    """After showing method detail: does the user want to start or ask a question?"""
    text = _last_human_text(state)
    if any(kw in text for kw in ["starten", "start", "los", "beginnen", "ja", "weiter"]):
        return "start"
    return "question"


def route_input_type(state: CoachState) -> str:
    """Classify free-form input during the session as question / feedback / other."""
    input_type = state.get("input_type")
    if input_type in ("question", "feedback", "other"):
        return input_type

    text = _last_human_text(state)
    if not text:
        return "other"

    # Quick keyword check before LLM call
    question_kws = ["wie", "was", "warum", "wann", "erkläre", "hilf", "kannst du", "?"]
    feedback_kws = ["hat", "war", "habe", "bin", "fühle", "lief", "ging", "funktioniert",
                    "super", "toll", "schlecht", "schwer", "gut", "nicht so", "okay"]

    if any(kw in text for kw in question_kws):
        state["pending_question"] = text
        return "question"
    if any(kw in text for kw in feedback_kws):
        return "feedback"

    # Fallback to LLM
    result = _classify_via_llm(
        text,
        "Klassifiziere die folgende Nutzerantwort eines Produktivitäts-Coaching-Chatbots.",
        ["question", "feedback", "other"],
    )
    if result == "question":
        state["pending_question"] = text
    return result


def route_feedback_category(state: CoachState) -> str:
    """Classify the feedback into one of 5 sentiment categories."""
    category = state.get("feedback_category")
    if category in ("positive", "partial_positive", "neutral", "partial_negative", "negative"):
        return category

    text = _last_human_text(state)

    result = _classify_via_llm(
        text,
        (
            "Klassifiziere das folgende Feedback eines Nutzers nach einer Coaching-Übung "
            "in eine der fünf Kategorien."
        ),
        ["positive", "partial_positive", "neutral", "partial_negative", "negative"],
    )
    return result


def route_next_action(state: CoachState) -> str:
    """After feedback processing: what does the user want to do next?"""
    next_action = state.get("next_action")
    if next_action in ("question", "new_method", "end"):
        return next_action

    text = _last_human_text(state)

    if any(kw in text for kw in ["frage", "wie", "was", "erkläre", "?"]):
        state["pending_question"] = text
        return "question"
    if any(kw in text for kw in ["beenden", "fertig", "tschüss", "danke", "bye", "aufhören"]):
        return "end"
    if any(kw in text for kw in ["neue", "nächste", "andere", "methode", "starten",
                                   "wiederholen", "nochmal"]):
        # Pre-select next available method if one was recommended
        next_m = state.get("next_available_method")
        if next_m:
            state["chosen_method"] = next_m
        return "new_method"

    # LLM fallback
    result = _classify_via_llm(
        text,
        "Was möchte der Nutzer als nächstes tun nach einer Coaching-Session?",
        ["question", "new_method", "end"],
    )
    return result

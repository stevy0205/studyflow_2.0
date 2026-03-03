"""
Router functions – komplett ohne LLM-Calls, kein Endlosschleifenrisiko.
Alle Entscheidungen per Keyword-Matching.
"""

from langchain_core.messages import HumanMessage
from state import CoachState


def _last_human_text(state: CoachState) -> str:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return msg.content.strip().lower()
    return ""


# ── Routers ────────────────────────────────────────────────────────────────────

def route_login(state: CoachState) -> str:
    return "logged_in" if state.get("is_logged_in") else "guest"


def route_user_action(state: CoachState) -> str:
    """Nach Methodenauswahl: Frage oder Methode wählen."""
    text = _last_human_text(state)
    choose_kws = ["1", "2", "wähle", "nehme", "starte", "methode 1", "methode 2",
                  "erste", "zweite", "option"]
    if any(kw in text for kw in choose_kws):
        methods = state.get("selected_methods", [])
        idx = 1 if "2" in text or "zweite" in text else 0
        chosen = methods[idx] if idx < len(methods) else (methods[0] if methods else None)
        if chosen:
            state["chosen_method"] = chosen
        return "choose_method"
    return "question"


def route_start_or_question(state: CoachState) -> str:
    """Nach Methoden-Detail: starten oder Frage stellen."""
    text = _last_human_text(state)
    start_kws = ["starten", "start", "los", "beginnen", "ja", "weiter", "ok", "okay",
                 "machen", "probier", "ausführen"]
    if any(kw in text for kw in start_kws):
        return "start"
    return "question"


def route_input_type(state: CoachState) -> str:
    """
    Während der Session: Frage, Feedback oder Beenden.
    KEIN 'other' → verhindert Endlosschleife.
    """
    text = _last_human_text(state)
    if not text:
        return "feedback"  # Sicherheit: nie hängen bleiben

    end_kws = ["beenden", "fertig", "tschüss", "danke", "bye", "aufhören", "stop",
               "schluss", "ende"]
    if any(kw in text for kw in end_kws):
        return "end"

    question_kws = ["wie", "was", "warum", "wann", "erkläre", "erklar", "hilf",
                    "kannst du", "könntest", "?", "bitte erklär", "ich verstehe nicht"]
    if any(kw in text for kw in question_kws):
        state["pending_question"] = text
        return "question"

    # Alles andere → Feedback (nie hängen lassen)
    return "feedback"


def route_feedback_category(state: CoachState) -> str:
    """Feedback in 5 Kategorien einteilen – per Keyword."""
    text = _last_human_text(state)

    positive_kws = ["super", "toll", "klasse", "perfekt", "sehr gut", "ausgezeichnet",
                    "hat gut", "hat sehr", "prima", "wunderbar", "top", "loved", "loved it"]
    partial_pos_kws = ["gut", "ganz gut", "okay", "ganz okay", "hat funktioniert",
                       "teilweise", "meistens", "größtenteils", "einigermaßen"]
    neutral_kws = ["neutral", "weder noch", "mittelmäßig", "so lala", "mittel",
                   "nicht besonders", "geht so"]
    partial_neg_kws = ["nicht so gut", "schwierig", "hatte mühe", "nicht ganz",
                       "weniger gut", "etwas schwer", "kaum", "nicht wirklich"]
    negative_kws = ["schlecht", "nicht funktioniert", "hat nicht", "überhaupt nicht",
                    "gar nicht", "nein", "frustrierend", "schlimm", "unmöglich", "hilft nicht"]

    if any(kw in text for kw in negative_kws):
        return "negative"
    if any(kw in text for kw in partial_neg_kws):
        return "partial_negative"
    if any(kw in text for kw in neutral_kws):
        return "neutral"
    if any(kw in text for kw in positive_kws):
        return "positive"
    if any(kw in text for kw in partial_pos_kws):
        return "partial_positive"

    # Default: neutral
    return "neutral"


def route_next_action(state: CoachState) -> str:
    """Nach Feedback: neue Methode, Frage oder beenden."""
    text = _last_human_text(state)

    end_kws = ["beenden", "fertig", "tschüss", "danke", "bye", "aufhören", "stop",
               "schluss", "ende", "reicht"]
    if any(kw in text for kw in end_kws):
        return "end"

    question_kws = ["wie", "was", "warum", "erkläre", "hilf", "?", "frage"]
    if any(kw in text for kw in question_kws):
        state["pending_question"] = text
        return "question"

    # Default: neue Methode
    next_m = state.get("next_available_method")
    if next_m:
        state["chosen_method"] = next_m
    return "new_method"
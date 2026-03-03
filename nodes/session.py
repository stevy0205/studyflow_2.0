"""
Session nodes: Methode anzeigen, Start-Impuls, Feedback anfordern, warten.
"""

from langchain_core.messages import AIMessage
from state import CoachState
from tools_registry import ToolsRegistry, ENTSCHLUESSE_VORLAGEN


def show_method_detail_node(state: CoachState) -> dict:
    method = state.get("chosen_method")
    if not method:
        methods = state.get("selected_methods", [])
        method = methods[0] if methods else None
    if not method:
        return {"messages": [AIMessage(content="Keine Methode ausgewählt.")]}

    # Schritte: neues Feld "anwendung", altes "schritte"
    schritte = method.get("anwendung") or method.get("schritte") or []
    steps_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(schritte))

    # Erklärung: neues "llm_explanation", altes "ziel"
    erklaerung = method.get("llm_explanation") or method.get("ziel") or ""
    erklaerung_text = f"\n💡 {erklaerung}\n" if erklaerung else ""

    dauer = method.get("dauer", "")
    dauer_text = f" · {dauer}" if dauer else ""
    name = method.get("name", "Methode")

    msg = (
        f"✅ **{name}**{dauer_text}\n\n"
        f"{method.get('kurzbeschreibung', '')}\n"
        f"{erklaerung_text}\n"
        f"**Schritte:**\n{steps_text}\n\n"
        "Hast du noch Fragen, oder sollen wir starten? Tippe **starten** oder stelle eine Frage."
    )
    return {
        "chosen_method": method,
        "method_chosen": True,
        "messages": [AIMessage(content=msg)],
    }


def give_start_impulse_node(state: CoachState) -> dict:
    method = state.get("chosen_method", {})
    schritte = method.get("anwendung") or method.get("schritte") or ["Lege los!"]
    first_step = schritte[0]
    dauer = method.get("dauer", "")
    dauer_text = f"⏱️ Plane dir **{dauer}** ein.\n\n" if dauer else ""
    name = method.get("name", "die Methode")

    # Entschlüsse-Vorlage immer anzeigen
    entschluesse = "\n".join(f"• {v}" for v in ENTSCHLUESSE_VORLAGEN)

    msg = (
        f"🚀 **Los geht's mit {name}!**\n\n"
        f"**Erster Schritt:** {first_step}\n\n"
        f"{dauer_text}"
        f"**📝 Formuliere deinen Entschluss:**\n{entschluesse}\n\n"
    )
    return {
        "session_active": True,
        "messages": [AIMessage(content=msg)],
    }


def request_feedback_node(state: CoachState) -> dict:
    method = state.get("chosen_method", {})
    name = method.get("name", "die Methode")
    msg = (
        f"Wie war deine Erfahrung mit **{name}**? 🙂\n\n"
        "Schreib einfach wie es gelaufen ist – positiv, gemischt oder schwierig."
    )
    return {"messages": [AIMessage(content=msg)]}


def wait_for_input_node(state: CoachState) -> dict:
    """Passiver Node – wartet auf Nutzereingabe."""
    return {}
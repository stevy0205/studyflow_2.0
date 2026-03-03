"""
Session nodes: show method detail, give start impulse, request and wait for feedback.
Alle Methoden-Infos kommen aus der tools.json via ToolsRegistry.
"""

from langchain_core.messages import AIMessage
from state import CoachState
from tools_registry import ToolsRegistry


def show_method_detail_node(state: CoachState) -> dict:
    """Zeigt die vollständige Methode mit Schritten, Tipps und Beispiel aus der JSON."""
    registry = ToolsRegistry.get()
    method = state.get("chosen_method")
    if not method:
        methods = state.get("selected_methods", [])
        method = methods[0] if methods else None

    if not method:
        return {"messages": [AIMessage(content="Keine Methode ausgewählt.")]}

    # Schritte aus JSON
    schritte = method.get("schritte", [])
    steps_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(schritte))

    # Tipps (optional, max. 2 anzeigen)
    tipps = method.get("tipps", [])[:2]
    tipps_text = ("\n**Tipps:**\n" + "\n".join(f"- {t}" for t in tipps)) if tipps else ""

    beispiel = method.get("beispiel", "")
    beispiel_text = f"\n**Beispiel:** {beispiel}" if beispiel else ""

    dauer = method.get("dauer", "?")
    kategorie = method.get("kategorie", "")
    name = method.get("name", "Methode")

    msg = (
        f"✅ **{name}** ({kategorie}, {dauer})\n\n"
        f"{method.get('kurzbeschreibung', '')}\n\n"
        f"**Schritte:**\n{steps_text}"
        f"{tipps_text}"
        f"{beispiel_text}\n\n"
        "Hast du noch Fragen, oder sollen wir starten? Tippe **starten** oder stelle eine Frage."
    )
    return {
        "chosen_method": method,
        "method_chosen": True,
        "messages": [AIMessage(content=msg)],
    }


def give_start_impulse_node(state: CoachState) -> dict:
    """Gibt einen motivierenden Startimpuls mit erstem Schritt und Timer-Hinweis."""
    method = state.get("chosen_method", {})
    schritte = method.get("schritte", ["Lege los!"])
    first_step = schritte[0]
    dauer = method.get("dauer", "?")
    name = method.get("name", "die Methode")

    msg = (
        f"🚀 **Los geht's mit {name}!**\n\n"
        f"**Erster Schritt:** {first_step}\n\n"
        f"⏱️ Plane dir **{dauer}** ein.\n\n"
        "Viel Erfolg! Ich bin hier, wenn du fertig bist oder eine Frage hast."
    )
    return {
        "session_active": True,
        "messages": [AIMessage(content=msg)],
    }


def request_feedback_node(state: CoachState) -> dict:
    """Fragt nach Feedback nach der Session."""
    method = state.get("chosen_method", {})
    name = method.get("name", "die Methode")
    msg = (
        f"Wie war deine Erfahrung mit **{name}**?\n\n"
        "Schreibe einfach, wie es gelaufen ist – positiv, gemischt oder schwierig. "
        "Ich freue mich auf dein Feedback! 🙂"
    )
    return {"messages": [AIMessage(content=msg)]}


def wait_for_input_node(state: CoachState) -> dict:
    """Passiver Node – wartet auf die nächste Nutzereingabe."""
    return {}

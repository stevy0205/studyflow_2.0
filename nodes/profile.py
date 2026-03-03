"""
Profile node – lädt gespeicherte Ergebnisse für eingeloggte User aus der DB.
"""

from langchain_core.messages import AIMessage
from state import CoachState
from database import get_latest_result


def load_profile_node(state: CoachState) -> dict:
    """
    Lädt das letzte Ergebnis des Users aus der DB.
    Falls vorhanden: Scores + Methoden direkt wiederverwenden.
    """
    profile  = state.get("user_profile") or {}
    username = profile.get("username", "")
    name     = profile.get("name", "")

    saved = get_latest_result(username) if username else None

    if saved:
        msg = (
            f"Willkommen zurück, {name}! 👋\n\n"
            f"Ich habe dein letztes Ergebnis geladen (vom {saved['created_at'][:10]}).\n"
            "Du kannst direkt weitermachen oder den Fragebogen neu starten."
        )
        return {
            "user_profile":     profile,
            "area_scores":      saved["area_scores"],
            "top_areas":        saved["top_areas"],
            "selected_methods": saved["selected_methods"],
            "has_saved_result": True,
            "messages":         [AIMessage(content=msg)],
        }

    return {
        "user_profile":     profile,
        "has_saved_result": False,
        "messages": [AIMessage(content=(
            f"Willkommen{', ' + name if name else ''}! "
            "Lass uns starten – ich stelle dir jetzt 24 kurze Fragen."
        ))],
    }

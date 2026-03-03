"""
Auth nodes: login and guest mode.
"""

from langchain_core.messages import AIMessage
from state import CoachState


def login_node(state: CoachState) -> dict:
    """
    Entry node. In a real app this would check a session token / OAuth.
    For the prototype we detect whether the user supplied credentials
    by inspecting the last human message or an injected flag.
    """
    # Caller should inject {"is_logged_in": True/False} before invoking the graph.
    # If not set, default to guest.
    is_logged_in = state.get("is_logged_in", False)
    return {"is_logged_in": is_logged_in}


def guest_node(state: CoachState) -> dict:
    """Start the bot in guest mode – no profile loaded."""
    return {
        "user_profile": None,
        "messages": [AIMessage(content=(
            "Willkommen! Du startest als Gast. "
            "Deine Ergebnisse werden nicht gespeichert. "
            "Lass uns beginnen – ich stelle dir jetzt 24 kurze Fragen."
        ))],
    }

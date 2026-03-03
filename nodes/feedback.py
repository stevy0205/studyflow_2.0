"""
Feedback nodes – 5 Kategorien.
Nächste Methode kommt aus ToolsRegistry.next_method() in AREA_ORDER-Reihenfolge.
"""

from langchain_core.messages import AIMessage
from state import CoachState
from tools_registry import ToolsRegistry


def _get_next(state: CoachState):
    registry = ToolsRegistry.get()
    method = state.get("chosen_method", {})
    used = state.get("used_method_names", [])
    return registry.next_method(method, used_names=used)


def _next_hint(next_m) -> str:
    if not next_m:
        return ""
    return (
        f"\n\nAls nächste Methode würde ich **{next_m['name']}** vorschlagen: "
        f"{next_m.get('kurzbeschreibung', '')}"
    )


def feedback_positive_node(state: CoachState) -> dict:
    method = state.get("chosen_method", {})
    name = method.get("name", "die Methode")
    next_m = _get_next(state)
    used = state.get("used_method_names", [])
    if name not in used:
        used = used + [name]

    msg = (
        f"🎉 Super, dass **{name}** so gut für dich funktioniert hat!\n\n"
        "Es lohnt sich, diese Methode regelmäßig zu wiederholen."
        f"{_next_hint(next_m)}\n\n"
        "Möchtest du **wiederholen**, die **nächste Methode** starten oder **beenden**?"
    )
    return {
        "messages": [AIMessage(content=msg)],
        "next_available_method": next_m,
        "used_method_names": used,
    }


def feedback_partial_positive_node(state: CoachState) -> dict:
    method = state.get("chosen_method", {})
    name = method.get("name", "die Methode")
    next_m = _get_next(state)
    used = state.get("used_method_names", [])
    if name not in used:
        used = used + [name]

    msg = (
        f"👍 Danke! **{name}** hat teilweise gut geklappt.\n\n"
        "Manchmal braucht eine Methode ein paar Wiederholungen. "
        "Ich würde dir empfehlen, es nochmal zu versuchen."
        f"{_next_hint(next_m)}\n\n"
        "Möchtest du **wiederholen**, die **nächste Methode** starten oder **beenden**?"
    )
    return {
        "messages": [AIMessage(content=msg)],
        "next_available_method": next_m,
        "used_method_names": used,
    }


def feedback_neutral_node(state: CoachState) -> dict:
    method = state.get("chosen_method", {})
    name = method.get("name", "die Methode")
    next_m = _get_next(state)
    used = state.get("used_method_names", [])
    if name not in used:
        used = used + [name]

    msg = (
        f"🙂 Danke für dein Feedback zu **{name}**!\n\n"
        "Neutral ist okay – nicht jede Methode passt sofort. "
        "Du könntest es nochmal versuchen oder eine andere Methode testen."
        f"{_next_hint(next_m)}\n\n"
        "Möchtest du **nochmal versuchen**, die **nächste Methode** starten oder **beenden**?"
    )
    return {
        "messages": [AIMessage(content=msg)],
        "next_available_method": next_m,
        "used_method_names": used,
    }


def feedback_partial_negative_node(state: CoachState) -> dict:
    method = state.get("chosen_method", {})
    name = method.get("name", "die Methode")
    next_m = _get_next(state)
    used = state.get("used_method_names", [])
    if name not in used:
        used = used + [name]

    msg = (
        f"💬 Danke für deine Ehrlichkeit! **{name}** hat diesmal nicht ganz gepasst.\n\n"
        "Ich würde dir eine andere Methode empfehlen, die vielleicht besser zu dir passt."
        f"{_next_hint(next_m)}\n\n"
        "Möchtest du die **nächste Methode** starten oder **beenden**?"
    )
    return {
        "messages": [AIMessage(content=msg)],
        "next_available_method": next_m,
        "used_method_names": used,
    }


def feedback_negative_node(state: CoachState) -> dict:
    method = state.get("chosen_method", {})
    name = method.get("name", "die Methode")
    next_m = _get_next(state)
    used = state.get("used_method_names", [])
    if name not in used:
        used = used + [name]

    msg = (
        f"🙏 Schade, dass **{name}** nicht gepasst hat – das ist wichtiges Feedback!\n\n"
        "Wir werden diese Methode nicht wiederholen."
        f"{_next_hint(next_m)}\n\n"
        "Möchtest du die **nächste Methode** ausprobieren oder **beenden**?"
    )
    return {
        "messages": [AIMessage(content=msg)],
        "next_available_method": next_m,
        "used_method_names": used,
    }
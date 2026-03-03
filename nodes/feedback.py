"""
Feedback nodes for the 5 feedback categories.
Each node:
  1. Mirrors the feedback appreciatively
  2. Makes a recommendation (repeat / next method / alternative)
  3. Sets next_action for the router
"""

from langchain_core.messages import AIMessage
from state import CoachState
from tools_registry import ToolsRegistry


def _next_method_for_area(current_method: dict, available_methods: dict) -> dict | None:
    """
    Gibt das nächste noch nicht verwendete Tool im gleichen Bereich zurück.
    Sucht zuerst im available_methods-State, dann direkt in der Registry.
    """
    current_name = current_method.get("name", "")
    current_kategorie = current_method.get("kategorie", "")

    # Aus dem State (bereits gefilterte Liste)
    for area_tools in available_methods.values():
        for m in area_tools:
            if (
                m.get("kategorie") == current_kategorie
                and m.get("name") != current_name
            ):
                return m

    # Fallback direkt aus Registry
    registry = ToolsRegistry.get()
    candidates = registry.by_category(current_kategorie)
    for c in candidates:
        if c.get("name") != current_name:
            return c

    return None


# ─────────────────────────────────────────────────────────────────────────────

def feedback_positive_node(state: CoachState) -> dict:
    method = state.get("chosen_method", {})
    name = method.get("name", "die Methode")
    next_m = _next_method_for_area(method, state.get("available_methods", {}))

    msg = (
        f"🎉 Das klingt super! Toll, dass **{name}** so gut für dich funktioniert hat.\n\n"
        f"Es lohnt sich, diese Methode regelmäßig zu wiederholen – am besten täglich oder wöchentlich.\n\n"
    )
    if next_m:
        msg += (
            f"Als nächstes könntest du auch **{next_m['name']}** ausprobieren "
            f"({next_m['area']}): {next_m['short_description']}\n\n"
        )
    msg += "Möchtest du **wiederholen**, eine **neue Methode** starten oder **beenden**?"

    return {
        "messages": [AIMessage(content=msg)],
        "next_available_method": next_m,
    }


def feedback_partial_positive_node(state: CoachState) -> dict:
    method = state.get("chosen_method", {})
    name = method.get("name", "die Methode")
    next_m = _next_method_for_area(method, state.get("available_methods", {}))

    msg = (
        f"👍 Danke für dein Feedback! Es freut mich, dass **{name}** teilweise gut geklappt hat.\n\n"
        "Manchmal braucht eine Methode ein paar Wiederholungen, bis sie sich natürlich anfühlt. "
        "Ich würde dir empfehlen, es noch einmal zu versuchen.\n\n"
    )
    if next_m:
        msg += (
            f"Alternativ wäre **{next_m['name']}** ({next_m['area']}) eine Option: "
            f"{next_m['short_description']}\n\n"
        )
    msg += "Möchtest du **wiederholen**, eine **neue Methode** starten oder **beenden**?"

    return {
        "messages": [AIMessage(content=msg)],
        "next_available_method": next_m,
    }


def feedback_neutral_node(state: CoachState) -> dict:
    method = state.get("chosen_method", {})
    name = method.get("name", "die Methode")
    next_m = _next_method_for_area(method, state.get("available_methods", {}))

    msg = (
        f"🙂 Danke, dass du dein Feedback teilst! Bei **{name}** war es diesmal noch neutral.\n\n"
        "Das ist völlig okay – nicht jede Methode passt sofort. "
        "Du könntest es nochmal versuchen oder eine andere Methode testen.\n\n"
    )
    if next_m:
        msg += f"**{next_m['name']}** wäre eine Alternative: {next_m['short_description']}\n\n"
    msg += "Möchtest du **nochmal versuchen**, eine **neue Methode** starten oder **beenden**?"

    return {
        "messages": [AIMessage(content=msg)],
        "next_available_method": next_m,
    }


def feedback_partial_negative_node(state: CoachState) -> dict:
    method = state.get("chosen_method", {})
    name = method.get("name", "die Methode")
    next_m = _next_method_for_area(method, state.get("available_methods", {}))

    msg = (
        f"💬 Danke für deine Ehrlichkeit! **{name}** hat diesmal nicht ganz gepasst – das ist wertvoll zu wissen.\n\n"
        "Ich würde dir empfehlen, eine andere Methode auszuprobieren, die vielleicht besser zu dir passt.\n\n"
    )
    if next_m:
        msg += (
            f"**{next_m['name']}** ({next_m['area']}) könnte für dich besser funktionieren: "
            f"{next_m['short_description']}\n\n"
        )
    msg += "Möchtest du eine **neue Methode** starten oder **beenden**?"

    return {
        "messages": [AIMessage(content=msg)],
        "next_available_method": next_m,
    }


def feedback_negative_node(state: CoachState) -> dict:
    method = state.get("chosen_method", {})
    name = method.get("name", "die Methode")
    area = method.get("area", "")
    # Suggest a shorter/different method
    alternatives = [
        m for m in METHODS
        if m["area"] == area
        and m["id"] != method.get("id")
        and m["duration_minutes"] <= method.get("duration_minutes", 999)
    ]
    alt = alternatives[0] if alternatives else None

    msg = (
        f"🙏 Danke für dein offenes Feedback! Schade, dass **{name}** nicht gepasst hat.\n\n"
        "Das ist wichtige Information – wir werden diese Methode nicht wiederholen.\n\n"
    )
    if alt:
        msg += (
            f"Vielleicht passt **{alt['name']}** besser zu dir – sie ist kürzer (~{alt['duration_minutes']} Min.) "
            f"und fokussiert anders: {alt['short_description']}\n\n"
        )
    msg += "Möchtest du eine **alternative Methode** ausprobieren oder **beenden**?"

    return {
        "messages": [AIMessage(content=msg)],
        "next_available_method": alt,
    }

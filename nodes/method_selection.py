"""
Method selection nodes – greift vollständig auf ToolsRegistry (tools.json) zu.
Keine hardcodierten Methoden mehr hier.
"""

from langchain_core.messages import AIMessage
from state import CoachState
from tools_registry import ToolsRegistry


def select_methods_node(state: CoachState) -> dict:
    """
    Wählt für jeden der Top-2-Bereiche das erste noch nicht verwendete Tool
    aus der ToolsRegistry aus.
    """
    registry = ToolsRegistry.get()
    top_areas = state.get("top_areas", [])
    used = state.get("used_method_names", [])

    selected: list[dict] = []
    available: dict[str, list[dict]] = {}

    for area in top_areas[:2]:
        area_tools = registry.top_for_area(area, exclude_names=used)
        available[area] = area_tools
        if area_tools:
            selected.append(area_tools[0])

    return {
        "selected_methods": selected,
        "available_methods": available,
    }


def display_methods_node(state: CoachState) -> dict:
    """Zeigt die 2 ausgewählten Methoden mit Kurzbeschreibung aus der JSON."""
    registry = ToolsRegistry.get()
    methods = state.get("selected_methods", [])

    if not methods:
        return {"messages": [AIMessage(content="Keine passenden Methoden gefunden.")]}

    lines = ["Hier sind deine **2 empfohlenen Methoden**:\n"]
    for i, m in enumerate(methods, 1):
        lines.append(f"**{i}.** {registry.format_short(m)}\n")

    lines.append(
        "\nWas möchtest du tun?\n"
        "- Tippe **1** oder **2**, um eine Methode auszuwählen\n"
        "- Stelle eine **Frage** zu einer der Methoden\n"
    )

    return {
        "messages": [AIMessage(content="\n".join(lines))],
        "method_chosen": False,
        "session_active": False,
    }

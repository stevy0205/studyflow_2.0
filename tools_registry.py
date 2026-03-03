"""
ToolsRegistry – lädt data/tools.json einmalig und stellt Zugriffsmethoden bereit.

Struktur der tools.json (wie im Beispiel):
{
  "Pomodoro-Technik": {
    "kategorie": "unterbrechungen",
    "kurzbeschreibung": "...",
    "ziel": "...",
    "wann_nutzen": [...],
    "schritte": [...],
    "dauer": "...",
    "tipps": [...],
    "haeufige_fehler": [...],
    "varianten": [...],
    "beispiel": "..."
  },
  ...
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# Pfad zur JSON-Datei – relativ zur Projektstruktur
_DEFAULT_PATH = Path(__file__).parent / "data" / "tools.json"


class ToolsRegistry:
    """Singleton-ähnlicher Zugriff auf den Tool-Katalog."""

    _instance: Optional["ToolsRegistry"] = None

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        with open(path, encoding="utf-8") as f:
            self._data: dict[str, dict] = json.load(f)

        # Normalisierung: stelle sicher, dass jeder Eintrag einen "name"-Key hat
        for name, entry in self._data.items():
            entry.setdefault("name", name)

    # ── Klassenmethode für Singleton-Zugriff ──────────────────────────────────

    @classmethod
    def get(cls, path: Path = _DEFAULT_PATH) -> "ToolsRegistry":
        if cls._instance is None:
            cls._instance = cls(path)
        return cls._instance

    # ── Abfrage-Methoden ──────────────────────────────────────────────────────

    def all_tools(self) -> list[dict]:
        """Alle Tools als Liste."""
        return list(self._data.values())

    def by_name(self, name: str) -> Optional[dict]:
        """Tool per exaktem Namen abrufen (case-insensitive)."""
        for key, entry in self._data.items():
            if key.lower() == name.lower():
                return entry
        return None

    def by_category(self, kategorie: str) -> list[dict]:
        """Alle Tools einer Kategorie."""
        return [
            e for e in self._data.values()
            if e.get("kategorie", "").lower() == kategorie.lower()
        ]

    def top_for_area(self, area_key: str, exclude_names: list[str] = None) -> list[dict]:
        """
        Gibt Tools für einen Bereich zurück.
        area_key muss auf eine Kategorie mappen (siehe AREA_TO_CATEGORY).
        """
        exclude_names = [n.lower() for n in (exclude_names or [])]
        kategorie = AREA_TO_CATEGORY.get(area_key.lower(), area_key.lower())
        candidates = self.by_category(kategorie)
        return [c for c in candidates if c["name"].lower() not in exclude_names]

    def format_for_llm(self, tool: dict) -> str:
        """
        Erstellt einen kompakten Kontext-String für den LLM-Coach.
        Enthält alle relevanten Felder – bereit zum Einfügen in den Prompt.
        """
        lines = [
            f"### {tool['name']} ({tool.get('kategorie', '')})",
            f"**Kurzbeschreibung:** {tool.get('kurzbeschreibung', '')}",
            f"**Ziel:** {tool.get('ziel', '')}",
            f"**Dauer:** {tool.get('dauer', '')}",
        ]

        if wann := tool.get("wann_nutzen"):
            lines.append("**Wann nutzen:**")
            lines.extend(f"- {w}" for w in wann)

        if schritte := tool.get("schritte"):
            lines.append("**Schritte:**")
            lines.extend(f"{i+1}. {s}" for i, s in enumerate(schritte))

        if tipps := tool.get("tipps"):
            lines.append("**Tipps:**")
            lines.extend(f"- {t}" for t in tipps)

        if fehler := tool.get("haeufige_fehler"):
            lines.append("**Häufige Fehler:**")
            lines.extend(f"- {fe}" for fe in fehler)

        if varianten := tool.get("varianten"):
            lines.append("**Varianten:**")
            lines.extend(f"- {v}" for v in varianten)

        if beispiel := tool.get("beispiel"):
            lines.append(f"**Beispiel:** {beispiel}")

        return "\n".join(lines)

    def format_short(self, tool: dict) -> str:
        """Kompakte Anzeige für die Methodenauswahl (2-Zeiler)."""
        return (
            f"**{tool['name']}** ({tool.get('dauer', '?')})\n"
            f"{tool.get('kurzbeschreibung', '')}"
        )


# ── Mapping: Fragebogen-Bereich → JSON-Kategorie ──────────────────────────────
# Passe das an, sobald du eigene Bereiche definierst.
AREA_TO_CATEGORY: dict[str, str] = {
    "fokus": "unterbrechungen",
    "unterbrechungen": "unterbrechungen",
    "leistung": "leistung",
    "prokrastination": "prokrastination",
    "emotion": "emotion",
    # Aliase
    "konzentration": "unterbrechungen",
    "performance": "leistung",
    "aufschieben": "prokrastination",
    "stress": "emotion",
}

"""
ToolsRegistry – lädt data/tools.json und gibt Methoden in der
vordefinierten Reihenfolge (aus dem Unterrichtsmaterial) zurück.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

_DEFAULT_PATH = Path(__file__).parent / "data" / "tools.json"

# ── Reihenfolge aus dem Unterrichtsmaterial ────────────────────────────────────
AREA_ORDER: dict[str, list[str]] = {
    "prokrastination": [
        "Entschlüsse fassen",
        "Stoff verteilen",
        "Lernphasen beenden",
    ],
    "unterbrechungen": [
        "30 Min Experiment",
        "Konzentration erhalten",
    ],
    "leistung": [
        "Wissensnetz",
        "Struktur-Lege-Technik",
        "Themen-Zerlegungs-Verfahren",
        "Chunking",
        "Chunking-Wiki",
        "Prüfungssimulation",
        "Wöchentliches Feedback",
        "Prüfungstipps",
        "Präsentation sandwichartig gestalten",
        "Prüfungstipps (Präsentation: 3-Sekunden-Kontrollblick)",
        "Prüfungssimulation (Präsentation: Sandwich + Kontrollblick)",
    ],
    "emotion": [
        "Reguliere deine Basisemotionen (10 Minuten Form)",
        "Reguliere deine Basisemotionen (3 Minuten Form)",
        "Reguliere deine Basisemotionen (Sekundenform)",
        "Prüfungsangst systematisch bewältigen",
    ],
}

# ── Entschlüsse-Vorlagen ───────────────────────────────────────────────────────
ENTSCHLUESSE_VORLAGEN = [
    "Ich beginne mit _____ am _____ um _____ Uhr.",
    "Ich schreibe eine To-Do-Liste am _____ um _____ Uhr.",
    "Ich lerne _____ am _____ von _____ bis _____ Uhr.",
    "Ich fange mit Aufgabe _____ an am _____ um _____ Uhr.",
]


class ToolsRegistry:
    _instance: Optional["ToolsRegistry"] = None

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        with open(path, encoding="utf-8") as f:
            raw: dict = json.load(f)
        self._data: dict[str, dict] = {}
        for name, entry in raw.items():
            if name.startswith("_") or not isinstance(entry, dict):
                continue
            if entry.get("_deprecated"):
                continue
            entry.setdefault("name", name)
            self._data[name] = entry

    @classmethod
    def get(cls, path: Path = _DEFAULT_PATH) -> "ToolsRegistry":
        if cls._instance is None:
            cls._instance = cls(path)
        return cls._instance

    def all_tools(self) -> list[dict]:
        seen, result = [], []
        for names in AREA_ORDER.values():
            for name in names:
                if name in self._data:
                    result.append(self._data[name])
                    seen.append(name)
        for name, tool in self._data.items():
            if name not in seen:
                result.append(tool)
        return result

    def by_name(self, name: str) -> Optional[dict]:
        for key, entry in self._data.items():
            if key.lower() == name.lower():
                return entry
        return None

    def by_category(self, kategorie: str) -> list[dict]:
        """Alle Tools einer Kategorie in AREA_ORDER-Reihenfolge."""
        ordered = AREA_ORDER.get(kategorie.lower(), [])
        result, seen = [], []
        for name in ordered:
            tool = self._data.get(name)
            if tool and tool.get("kategorie", "").lower() == kategorie.lower():
                result.append(tool)
                seen.append(name)
        for tool in self._data.values():
            if tool.get("kategorie", "").lower() == kategorie.lower() and tool["name"] not in seen:
                result.append(tool)
        return result

    def top_for_area(self, area_key: str, exclude_names: list = None) -> list[dict]:
        exclude_names = [n.lower() for n in (exclude_names or [])]
        kategorie = AREA_TO_CATEGORY.get(area_key.lower(), area_key.lower())
        return [c for c in self.by_category(kategorie) if c["name"].lower() not in exclude_names]

    def next_method(self, current_method: dict, used_names: list = None) -> Optional[dict]:
        """Nächste Methode im gleichen Bereich nach AREA_ORDER, exkl. bereits verwendeter."""
        used = [n.lower() for n in (used_names or [])]
        current_name = current_method.get("name", "").lower()
        kategorie = current_method.get("kategorie", "")
        candidates = self.by_category(kategorie)
        current_idx = next(
            (i for i, c in enumerate(candidates) if c["name"].lower() == current_name), -1
        )
        for c in candidates[current_idx + 1:]:
            if c["name"].lower() not in used:
                return c
        for c in candidates:
            if c["name"].lower() not in used and c["name"].lower() != current_name:
                return c
        return None

    def format_for_llm(self, tool: dict) -> str:
        lines = [
            f"### {tool['name']} ({tool.get('kategorie', '')})",
            f"**Beschreibung:** {tool.get('kurzbeschreibung', '')}",
        ]
        ziel = tool.get("llm_explanation") or tool.get("ziel")
        if ziel:
            lines.append(f"**Erklärung:** {ziel}")
        if dauer := tool.get("dauer"):
            lines.append(f"**Dauer:** {dauer}")
        schritte = tool.get("anwendung") or tool.get("schritte") or []
        if schritte:
            lines.append("**Anwendung:**")
            lines.extend(f"{i+1}. {s}" for i, s in enumerate(schritte))
        if tipps := tool.get("tipps"):
            lines.append("**Tipps:**")
            lines.extend(f"- {t}" for t in tipps)
        if para := tool.get("original_paraphrase"):
            lines.append(f"**Hintergrund:** {para[:400]}{'...' if len(para) > 400 else ''}")
        return "\n".join(lines)

    def format_short(self, tool: dict) -> str:
        dauer = f" ({tool.get('dauer')})" if tool.get("dauer") else ""
        return f"**{tool['name']}**{dauer}\n{tool.get('kurzbeschreibung', '')}"


AREA_TO_CATEGORY: dict[str, str] = {
    "fokus":           "unterbrechungen",
    "unterbrechungen": "unterbrechungen",
    "leistung":        "leistung",
    "prokrastination": "prokrastination",
    "emotion":         "emotion",
    "konzentration":   "unterbrechungen",
    "performance":     "leistung",
    "aufschieben":     "prokrastination",
    "stress":          "emotion",
}
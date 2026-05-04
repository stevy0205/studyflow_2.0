# Coach Bot – LangGraph Implementation

Ein konversationeller Coaching-Chatbot welcher Studenten bei Prüfungsängsten oder Problemen beim Lernen unterstützen soll.

## Projektstruktur

```
root/
├── data/
    ├── tools.json         # Tool Beschreibungen
├── frontend/
    ├── templates          # HTML Templates für UI    
├── tests/
    ├── test_llm_judge.py  # LLM Tests
    ├── test_unit.py       # Statische Unit Tests für deterministisches Verhalten
├── graph.py               # Haupt-Graph (StateGraph)
├── state.py               # CoachState TypedDict
├── routers.py             # Alle Router-Funktionen
├── api.py
├── database.py
├── tools_registry.py
└── nodes/
    ├── auth.py            # Login / Gastmodus
    ├── profile.py         # Profil laden
    ├── questionnaire.py   # 24 Fragen + Score-Berechnung
    ├── method_selection.py # Methoden-Katalog + Auswahl
    ├── coach.py           # LLM-Coach-Erklärungen
    ├── session.py         # Session-Flow (Start, Feedback-Anfrage)
    └── feedback.py        # 5 Feedback-Kategorien
```

## Installation

```bash
pip install -r requirements.txt

```

## Verwendung

```bash
python3 uvicorn api:app --reload
```

## Tests

pytest tests/test_llm_judge.py -v -s

pytest tests/test_unit.py -v -s

## Graph-Übersicht

```
Login → Profil laden (oder Gast) → Fragebogen (24 Fragen)
     → Score-Berechnung → Top 2 Bereiche → Methoden auswählen
     → Methoden anzeigen
         ↕ Fragen ←→ Coach erklärt
     → Methode wählen → Methode detailliert anzeigen
         ↕ Fragen ←→ Coach erklärt
     → Start-Impuls → Feedback anfragen → Auf Eingabe warten
         ↕ Fragen ←→ Coach erklärt
         ↓ Feedback
     → [Positiv / Teilweise positiv / Neutral / Teilweise negativ / Negativ]
         → Nächste Aktion: Neue Methode | Frage | Beenden
```

## Anpassen

- **Methoden-Katalog**: `nodes/method_selection.py` → Siehe Tools Registry
- **Fragen**: `nodes/questionnaire.py` → `QUESTIONS` Liste anpassen
- **Bereiche**: `nodes/questionnaire.py` → `AREAS` Liste anpassen
- **LLM-Modell**: `nodes/coach.py` und `routers.py` → `ChatOpenAI(model=...)`
- **Persistenz**: `graph.py` → `MemorySaver()` durch `SqliteSaver` oder `PostgresSaver` ersetzen

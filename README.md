# Coach Bot – LangGraph Implementation

Ein konversationeller Coaching-Chatbot basierend auf dem Flowchart-Diagramm.

## Projektstruktur

```
coach_bot/
├── graph.py               # Haupt-Graph (StateGraph)
├── state.py               # CoachState TypedDict
├── routers.py             # Alle Router-Funktionen
├── requirements.txt
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
export OPENAI_API_KEY=sk-...
```

## Verwendung

```python
from graph import graph

config = {"configurable": {"thread_id": "user-123"}}

# Eingeloggter Nutzer
result = graph.invoke(
    {"is_logged_in": True, "user_profile": {"name": "Anna"}},
    config=config
)

# Gast
result = graph.invoke(
    {"is_logged_in": False},
    config=config
)

# Antwort auf Fragebogen (24 Zahlen, kommagetrennt)
result = graph.invoke(
    {"messages": [{"role": "user", "content": "4,3,5,2,4,3,2,4,3,5,4,3,5,4,3,2,4,5,3,4,5,3,4,5"}]},
    config=config
)
```

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

- **Methoden-Katalog**: `nodes/method_selection.py` → `METHODS` Liste erweitern
- **Fragen**: `nodes/questionnaire.py` → `QUESTIONS` Liste anpassen
- **Bereiche**: `nodes/questionnaire.py` → `AREAS` Liste anpassen
- **LLM-Modell**: `nodes/coach.py` und `routers.py` → `ChatOpenAI(model=...)`
- **Persistenz**: `graph.py` → `MemorySaver()` durch `SqliteSaver` oder `PostgresSaver` ersetzen

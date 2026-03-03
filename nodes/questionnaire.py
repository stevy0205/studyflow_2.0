"""
Questionnaire nodes: collect 24 answers, calculate scores, determine top areas.
"""

from langchain_core.messages import AIMessage, HumanMessage
from state import CoachState

# ── Static questionnaire data ──────────────────────────────────────────────────
AREAS = ["prokrastination", "unterbrechungen", "leistung", "emotion"]

QUESTIONS: list[dict] = [
    # 6 Fragen pro Bereich
    {"text": "Ich schiebe Aufgaben oft auf, obwohl ich weiß, dass ich anfangen sollte.", "area": "prokrastination"},
    {"text": "Ich fange Lernphasen häufig später an als geplant.", "area": "prokrastination"},
    {"text": "Mir fällt es schwer, mich zum Starten zu motivieren.", "area": "prokrastination"},
    {"text": "Ich plane meinen Lernstoff realistisch über mehrere Tage.", "area": "prokrastination"},
    {"text": "Ich beende Lernphasen mit einem klaren Plan für den nächsten Start.", "area": "prokrastination"},
    {"text": "Ich habe konkrete Strategien, wenn ich innerlich Widerstand spüre.", "area": "prokrastination"},

    {"text": "Ich wechsle beim Lernen häufig zwischen Apps, Tabs oder Aufgaben.", "area": "unterbrechungen"},
    {"text": "Das Handy lenkt mich regelmäßig beim Lernen ab.", "area": "unterbrechungen"},
    {"text": "Ich kann Ablenkungen gut ignorieren und bleibe bei der Aufgabe.", "area": "unterbrechungen"},
    {"text": "Ich nutze aktiv Techniken (z.B. Timer, Flugmodus), um fokussiert zu bleiben.", "area": "unterbrechungen"},
    {"text": "Ich bemerke, wenn meine Konzentration nachlässt, und korrigiere das gezielt.", "area": "unterbrechungen"},
    {"text": "Meine Lernphasen sind klar strukturiert mit definierten Pausen.", "area": "unterbrechungen"},

    {"text": "Ich lerne Stoff oft durch aktives Strukturieren statt passives Lesen.", "area": "leistung"},
    {"text": "Ich übe regelmäßig unter Prüfungsbedingungen.", "area": "leistung"},
    {"text": "Ich zerteile komplexe Themen in lernbare Einheiten.", "area": "leistung"},
    {"text": "Ich analysiere meine Fehler nach Übungen systematisch.", "area": "leistung"},
    {"text": "Ich weiß genau, was ich in welchem Thema können muss.", "area": "leistung"},
    {"text": "Ich passe meine Lernstrategie regelmäßig auf Basis meines Fortschritts an.", "area": "leistung"},

    {"text": "Prüfungssituationen lösen bei mir starke Nervosität oder Blockaden aus.", "area": "emotion"},
    {"text": "Emotionaler Stress (Frust, Angst, Druck) beeinträchtigt mein Lernen.", "area": "emotion"},
    {"text": "Ich habe Techniken, um mich vor oder während dem Lernen zu stabilisieren.", "area": "emotion"},
    {"text": "Ich erkenne, wann ich eine Pause oder Regulation brauche.", "area": "emotion"},
    {"text": "Negative Gedanken (\"Ich schaffe das nicht\") machen mir häufig zu schaffen.", "area": "emotion"},
    {"text": "Ich gehe gut mit Rückschlägen und schlechten Lerntagen um.", "area": "emotion"},
]

SCALE_LABELS = "0 = stimme gar nicht zu  |  3 = stimme voll zu"


def questionnaire_node(state: CoachState) -> dict:
    """
    Present all 24 questions.
    In an interactive LangGraph setup this node would stream questions one by one
    and wait for human input via interrupt(). For simplicity we emit them as a
    single assistant message listing all questions and expect the answers in the
    next human turn as a comma-separated string (e.g. "4,3,5,2,...").
    """
    question_lines = "\n".join(
        f"  {i+1}. [{q['area']}] {q['text']}"
        for i, q in enumerate(QUESTIONS)
    )
    msg = (
        f"Beantworte bitte alle 24 Aussagen auf einer Skala von 1–5.\n"
        f"({SCALE_LABELS})\n\n"
        f"{question_lines}\n\n"
        "Schreibe deine Antworten als 24 Zahlen, durch Komma getrennt, z.B.: 2,3,1,2,..."
    )
    return {"messages": [AIMessage(content=msg)]}


def calculate_scores_node(state: CoachState) -> dict:
    """Parse the human's answers and compute per-area scores."""
    # Extract the most recent HumanMessage that looks like answers
    answers_raw = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            answers_raw = msg.content
            break

    try:
        answers = [int(x.strip()) for x in answers_raw.split(",") if x.strip()]
    except ValueError:
        answers = [1] * 24  # Fallback: neutral (Mitte bei 0-3)

    # Pad / truncate to 24
    answers = (answers + [1] * 24)[:24]

    # Summe pro Bereich (6 Fragen × max 3 = max 18)
    area_scores: dict[str, float] = {}
    for i, area in enumerate(AREAS):
        area_scores[area] = sum(answers[i * 6 : (i + 1) * 6])

    return {"questionnaire_answers": answers, "area_scores": area_scores}


def determine_top_areas_node(state: CoachState) -> dict:
    """Determine the top 2 areas with the lowest scores (most improvement potential)."""
    area_scores = state.get("area_scores", {})
    # Sort ascending: lowest score = highest need
    sorted_areas = sorted(area_scores, key=lambda a: area_scores[a])
    top_areas = sorted_areas[:2]

    msg = (
        f"Basierend auf deinen Antworten sind deine wichtigsten Entwicklungsbereiche:\n"
        f"1. **{top_areas[0]}** (Score: {area_scores.get(top_areas[0], '?')})\n"
        f"2. **{top_areas[1]}** (Score: {area_scores.get(top_areas[1], '?')})\n\n"
        "Ich wähle jetzt die passenden Methoden für dich aus..."
    )
    return {
        "top_areas": top_areas,
        "messages": [AIMessage(content=msg)],
    }

"""
LLM-as-a-Judge Tests – bewertet die Qualität der LLM-Calls
Ausführen: pytest tests/test_llm_judge.py -v -s
  (braucht OPENAI_API_KEY als Umgebungsvariable)

Testdaten:
  - SENTIMENT_CASES_SYNTHETIC   → 8 synthetische Fälle (Baseline)
  - SENTIMENT_CASES_REAL        → 22 echte Nutzerfeedbacks aus dem StudyFlow-Piloten
                                   (Feb 2026, 74 Nutzer, anonymisiert als pseudo_id)
  - QUESTION_CASES              → 5 Coach-Antwort-Qualitätstests
  - COACH_RESPONSE_CASES        → 6 neue Tests: reagiert der Bot wie Diethelm?
"""

import os
import sys
import json
import pytest
from pathlib import Path
from dotenv import load_dotenv
sys.path.insert(0, str(Path(__file__).parent.parent))
from openai import AsyncOpenAI
load_dotenv()
client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


# ─────────────────────────────────────────────────────────────────────────────
# Judge-Helper
# ─────────────────────────────────────────────────────────────────────────────

async def judge_sentiment(user_text, predicted, expected):
    resp = await client.chat.completions.create(
        model="gpt-4o-mini", temperature=0, max_tokens=200,
        messages=[{
            "role": "system",
            "content": (
                "Du bewertest ob eine Sentiment-Klassifikation für Feedback zu einer Lernmethode korrekt ist.\n"
                "Kategorien: positive, partial_positive, neutral, partial_negative, negative\n"
                "Antworte als JSON: {\"correct\": true/false, \"reason\": \"kurze Begründung\"}"
            )
        }, {
            "role": "user",
            "content": f"Feedback: \"{user_text}\"\nVorhergesagt: {predicted}\nErwartet: {expected}\nIst die Vorhersage korrekt oder zumindest vertretbar?"
        }]
    )
    try:
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {"correct": False, "reason": "JSON-Parse-Fehler"}


async def judge_answer_quality(question, method_context, answer):
    resp = await client.chat.completions.create(
        model="gpt-4o-mini", temperature=0, max_tokens=300,
        messages=[{
            "role": "system",
            "content": (
                "Du bewertest die Qualität einer Coach-Antwort auf eine Studentenfrage.\n"
                "Kriterien: factual, admits_uncertainty, helpful, not_hallucinating\n"
                "Antworte als JSON: {\"factual\": bool, \"admits_uncertainty\": bool, "
                "\"helpful\": bool, \"not_hallucinating\": bool, \"score\": 0-4, \"reason\": str}"
            )
        }, {
            "role": "user",
            "content": f"Frage: \"{question}\"\n\nMethoden-Kontext:\n{method_context}\n\nCoach-Antwort:\n{answer}"
        }]
    )
    try:
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {"score": 0, "reason": "JSON-Parse-Fehler"}


async def judge_coach_response(user_feedback, tool_id, bot_response, reference_response):
    """
    Vergleicht Bot-Antwort mit echter Diethelm-Antwort als Referenz.
    Bewertet: empathetic, actionable, tone_match, not_generic, score 0-4
    """
    resp = await client.chat.completions.create(
        model="gpt-4o-mini", temperature=0, max_tokens=400,
        messages=[{
            "role": "system",
            "content": (
                "Du bewertest eine KI-Coach-Antwort auf das Feedback eines Studenten.\n"
                "Du hast zusätzlich eine Referenz-Antwort von einem echten menschlichen Coach.\n"
                "Die Bot-Antwort muss nicht identisch sein, aber ähnlich gut:\n"
                "- empathetic: Geht auf das konkrete Erlebnis/Gefühl ein\n"
                "- actionable: Gibt konkrete nächste Schritte\n"
                "- tone_match: Warm, ermutigend, professionell\n"
                "- not_generic: Keine leeren Phrasen ohne Bezug zum Feedback\n"
                "Antworte als JSON: {\"empathetic\": bool, \"actionable\": bool, "
                "\"tone_match\": bool, \"not_generic\": bool, \"score\": 0-4, \"reason\": str}"
            )
        }, {
            "role": "user",
            "content": (
                f"Tool: {tool_id}\n\n"
                f"Nutzerfeedback: \"{user_feedback}\"\n\n"
                f"Referenz-Antwort (echter Coach):\n{reference_response}\n\n"
                f"Bot-Antwort:\n{bot_response}"
            )
        }]
    )
    try:
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {"score": 0, "reason": "JSON-Parse-Fehler"}


# ─────────────────────────────────────────────────────────────────────────────
# System-Under-Test
# ─────────────────────────────────────────────────────────────────────────────

async def call_llm_sentiment(text):
    resp = await client.chat.completions.create(
        model="gpt-4o-mini", temperature=0, max_tokens=10,
        messages=[{
            "role": "system",
            "content": "Du klassifizierst Feedback zu einer Lernmethode. Antworte NUR mit einem Wort: positive, partial_positive, neutral, partial_negative oder negative."
        }, {"role": "user", "content": text}]
    )
    result = resp.choices[0].message.content.strip().lower()
    return result if result in {"positive","partial_positive","neutral","partial_negative","negative"} else "neutral"


async def call_llm_answer(question, method_context):
    resp = await client.chat.completions.create(
        model="gpt-4o-mini", temperature=0.3, max_tokens=400,
        messages=[{
            "role": "system",
            "content": (
                "Du bist ein freundlicher Lerncoach. Beantworte die Frage auf Basis der Methoden-Informationen. "
                "Antworte auf Deutsch, maximal 3-4 Sätze.\n"
                "WICHTIG: Wenn die Antwort nicht klar im Kontext steht, gib das ehrlich zu. Erfinde keine Details.\n\n"
                f"## Methoden-Kontext:\n{method_context}"
            )
        }, {"role": "user", "content": question}]
    )
    return resp.choices[0].message.content.strip()


async def call_llm_coach_response(user_feedback, tool_id):
    resp = await client.chat.completions.create(
        model="gpt-4o-mini", temperature=0.5, max_tokens=300,
        messages=[{
            "role": "system",
            "content": (
                "Du bist ein empathischer Lerncoach (Diethelm-Bot) in der StudyFlow-App. "
                "Ein Student hat gerade eine Lernmethode ausprobiert und gibt dir Feedback. "
                "Antworte auf Deutsch, kurz (3-5 Sätze), warm und konkret. "
                "Gehe auf das spezifische Erlebnis ein. Gib einen konkreten nächsten Schritt. "
                "Vermeide leere Phrasen."
            )
        }, {
            "role": "user",
            "content": f"Tool: {tool_id}\nFeedback des Studenten: \"{user_feedback}\""
        }]
    )
    return resp.choices[0].message.content.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Test-Daten
# ─────────────────────────────────────────────────────────────────────────────

SENTIMENT_CASES_SYNTHETIC = [
    ("Das hat super funktioniert, ich war sehr fokussiert!", "positive"),
    ("Hat ganz okay geklappt, aber ich war manchmal abgelenkt.", "partial_positive"),
    ("War so mittel, nicht besonders gut aber auch nicht schlecht.", "neutral"),
    ("Ich fand es eher schwierig, hat nicht so gut gepasst für mich.", "partial_negative"),
    ("Das war komplett nutzlos für mich, ich konnte gar nichts damit anfangen.", "negative"),
    ("Hab die 30 Minuten kaum durchgehalten aber immerhin versucht.", "partial_negative"),
    ("Ehrlich gesagt hat mir die Methode heute sehr geholfen.", "positive"),
    ("Keine Ahnung, irgendwie weder noch.", "neutral"),
]

# Echte Feedbacks aus dem StudyFlow-Piloten (Feb 2026, 74 Nutzer)
# Format: (text, erwartetes_sentiment)
# Besonderheiten: umgangssprachlich, kurz, ambivalent, Feature-Requests
SENTIMENT_CASES_REAL = [
    # Klare Positivfälle
    (
        "Ich habe mich nicht unterbrochen, da ich ständig die Uhr vor mir hatte "
        "und wirklich versucht habe durchzuhalten. Geholfen hat mir dabei, dass "
        "eben alles was ich brauche vor mir habe und mein Handy aus ist.",
        "positive",
    ),
    (
        "Ich habe die Email-Erinnerung bekommen als ich im Bett gelegen und Reels "
        "auf Instagram angeschaut habe. Die Nachricht hat mich nicht nur erinnert, "
        "sondern auch motiviert aufzustehen. Ich bin tatsächlich damit fertig "
        "geworden nach wochenlangen aufschieben :)",
        "positive",
    ),
    (
        "Das bewusste fassen von Entschlüssen fühlt sich gut an, fast so, als hätte "
        "man das Vorhaben bereits erledigt. Es ist motivierend, bewusst die "
        "Entscheidung zu treffen.",
        "positive",
    ),
    (
        "Tiefer Atem war gut, fühle mich ruhiger und wacher zugleich. "
        "Es hat eine stabilisierende Wirkung, meinen Körper zu spüren.",
        "positive",
    ),
    (
        "Das hat mir sehr geholfen! Ich bin tagsüber entspannter, weil ich weiß, "
        "was zu tun ist und dann auch fertig mit Lernen bin, wenn ich es geschafft habe",
        "positive",
    ),
    # Partial positive
    (
        "Mit der Planungs-Methode habe ich eine strukturierte Übersicht erhalten. "
        "Allerdings hat mir der Wochenplan nicht so sehr geholfen, da ich jede "
        "Woche genau dasselbe lernen muss.",
        "partial_positive",
    ),
    (
        "Das Tool hilft aufjedenfall sich zu entspannen. Denke es könnte Abends "
        "vor dem Schlafen sinnvoll sein. Inwiefern ich meine Emotionen besser "
        "regulieren kann, ist noch nicht abschätzbar.",
        "partial_positive",
        # Achtung: Wichtigkeit NUR 2 aber Text positiv – Diskrepanz!
    ),
    (
        "ich wusste nicht, dass die Uhr stoppt, wenn ich die App wechsle. "
        "Nächstes Mal nehme ich das Handy um den Timer laufen zu lassen. "
        "Es hat super geklappt, bin gut vorangekommen.",
        "partial_positive",
        # Bug-Report + Erfolg gemischt
    ),
    (
        "Ich finde es gut, sich bereits im Voraus in die Prüfungssituation "
        "hineinzuversetzen. Allerdings macht es für mich trotzdem einen Unterschied, "
        "wenn in der richtigen Prüfung auch noch die Prüfer da sind.",
        "partial_positive",
    ),
    # Echter Grenzfall: ambivalent
    (
        "leichter Druck\naber auch Erleichterung, es im Blick zu haben",
        "partial_positive",
        # Zwei Seiten in Kurzform – echter Grenzfall aus Praxis
    ),
    # Neutral
    (
        "Es ist ein sehr warmer Tag und ich musste was drinken",
        "neutral",
        # Physischer Grund, kein Urteil über Methode
    ),
    (
        "Musti alles erklären",
        "neutral",
        # Zu kurz für klares Sentiment
    ),
    (
        "Ich habe noch keine Erfahrungen",
        "neutral",
        # Tool ohne echte Nutzung abgeschlossen
    ),
    (
        "Es war schwer einzuschätzen, wie lange ich für was brauche. "
        "Es wäre gut, wenn man eintragen könnte was man machen soll "
        "und die App mir einen Plan erstellt.",
        "neutral",
        # Feature-Request, kein klares Methodenurteil
    ),
    (
        "Ich konnte mich lange Konzentrieren, allerdings habe ich das Gefühl, "
        "in der Zeit nicht immer produktiv zu sein. Nach den ersten 30 Minuten "
        "fühle ich mich energielos.",
        "neutral",
        # Konzentration ja, Produktivität nein – ambivalent
    ),
    # Partial negative
    (
        "Meine Gedanken sind abgeschweift, da ich meine aktuelle Aufgabe als "
        "langweilig empfand. Außerdem habe ich nachher noch etwas zu erledigen "
        "und musste daran denken.",
        "partial_negative",
    ),
    (
        "Ich hab ein Problem mit Tagträumen. Besonders beim lernen bemerke ich es, "
        "wenn ich etwas nicht direkt verstehe. Mein Kopf driftet direkt ab, "
        "und wenn es nur für 5-10 Sekunden ist",
        "partial_negative",
        # Tiefe Selbstreflexion, echte Lernschwierigkeit
    ),
    (
        "ungutes Gefühl, Stress, etwas wirklich anzugehen, Berg vor Augen?",
        "partial_negative",
        # Sehr kurz, emotionaler Widerstand, Fragezeichen am Ende
    ),
    (
        "Unsicher, da noch nie zuvor so richtig angewandt. "
        "Bisschen überfordernd etwas zu planen was in ein paar Wochen ist",
        "partial_negative",
    ),
    (
        "Es sollte irgendein Belohnungssystem geben, dass mich motiviert zu lernen. "
        "Gamification Elemente wie Level oder Punkte würden mir sehr helfen.",
        "partial_negative",
        # App-Kritik / Wunsch nach mehr → implizit unzufrieden mit Status quo
    ),
]


METHOD_30MIN = """
### 30 Min Experiment
**Beschreibung:** 30 Minuten ohne Selbstunterbrechung am Platz bleiben – Fokus trainieren.
**Anwendung:**
1. Lege eine Aufgabe bereit. 2. Schalte Störquellen aus. 3. Starte 30-Min-Timer.
4. Bleib sitzen und unterbrich dich nicht. 5. Notiere: Minute der ersten Unterbrechung.
"""

METHOD_CHUNKING = """
### Chunking
**Beschreibung:** Einzelinfos zu Einheiten bündeln, um schneller abzurufen.
**Anwendung:**
1. Am Ende jeder Lernphase: 5-10 Prüfungsfragen erstellen.
2. Fragen in zufälliger Reihenfolge beantworten.
3. Lücken markieren und gezielt nacharbeiten.
"""

QUESTION_CASES = [
    ("Wie lange soll ich beim 30-Minuten-Experiment sitzen?", METHOD_30MIN, 3, False),
    ("Was mache ich wenn ich aufstehen muss auf die Toilette?", METHOD_30MIN, 2, True),
    ("Wie viele Chunks soll ich pro Lernphase erstellen?", METHOD_CHUNKING, 2, False),
    ("Welche Musik ist am besten beim Lernen?", METHOD_CHUNKING, 1, True),
    ("Was bedeutet Chunking genau?", METHOD_CHUNKING, 3, False),
]

# Ground Truth: echte Coaching-Antworten von Prof. Dr. Diethelm Wahl
COACH_RESPONSE_CASES = [
    (
        "thirty-minute-experiment",
        "Ich habe mich nicht unterbrochen, da ich ständig die Uhr vor mir hatte "
        "und wirklich versucht habe durchzuhalten. Mein Handy war aus.",
        "du hast die große, leider unter Studierenden seltene Fähigkeit, längere Zeit "
        "konzentriert zu lernen oder zu arbeiten. Sei stolz auf diese Kompetenz, denn sie "
        "hilft dir, in kurzer Zeit tüchtig voranzukommen.",
        3,
    ),
    (
        "commit-decision",
        "Das bewusste fassen von Entschlüssen fühlt sich gut an, fast so, als hätte "
        "man das Vorhaben bereits erledigt.",
        "toll, dass du direkt damit begonnen hast, konkrete Entschlüsse zu fassen. "
        "Nach der Rubikon-Theorie ist dieser Schritt essentiell um ins Handeln zu kommen.",
        3,
    ),
    (
        "plans",
        "Mit der Planungs-Methode habe ich eine strukturierte Übersicht erhalten. "
        "Allerdings hat mir der Wochenplan nicht so sehr geholfen.",
        "Dass dir der Wochenplan nicht geholfen hat ist anhand deiner Erklärung "
        "verständlich. Passe die Methode gerne so an, wie sie auf deine Bedürfnisse passt.",
        3,
    ),
    (
        "commit-decision",
        "ungutes Gefühl, Stress, etwas wirklich anzugehen, Berg vor Augen?",
        "Das ist ganz normal wenn man sich Sachen stellt, die man ungerne tut. "
        "Nimm dir erstmal eine kleinere Sache vor und gehe diese mit dem "
        "30-Minuten-Experiment an.",
        3,
    ),
    (
        "stabilize-core-emotion",
        "Das Tool hilft aufjedenfall sich zu entspannen. Inwiefern ich meine "
        "Emotionen besser regulieren kann, ist noch nicht abschätzbar.",
        "du hast gut erkannt, dass man damit in einen tiefen Ruhezustand kommt. "
        "Tagsüber ist es oft besser mit der 3-Minuten-Variante zu arbeiten.",
        3,
    ),
    (
        "thirty-minute-experiment",
        "Ich hab ein Problem mit Tagträumen. Mein Kopf driftet direkt ab, "
        "wenn ich etwas nicht direkt verstehe.",
        "Wenn deine Gedanken abdriften, musst du unterscheiden was die Ursache ist. "
        "Verstehst du etwas nicht und willst das Problem lösen, dann gehst du tiefer "
        "in die Sache hinein – das ist positiv.",
        3,
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("text,expected", SENTIMENT_CASES_SYNTHETIC)
async def test_sentiment_synthetic(text, expected):
    """Sentinel: synthetische Baseline-Fälle müssen weiterhin funktionieren."""
    predicted = await call_llm_sentiment(text)
    result    = await judge_sentiment(text, predicted, expected)
    print(f"\n[SYN] '{text[:60]}' → {predicted} (erwartet: {expected}) | {result}")
    assert result["correct"], f"Sentiment falsch: {result['reason']}"


@pytest.mark.asyncio
@pytest.mark.parametrize("text,expected", SENTIMENT_CASES_REAL)
async def test_sentiment_real_users(text, expected):
    """
    Ground Truth aus echten Nutzerfeedbacks des StudyFlow-Piloten (Feb 2026).
    Realistischer als Synthetic: umgangssprachlich, kurz, ambivalent,
    Bug-Reports, Feature-Requests, Diskrepanz zwischen Text und Wichtigkeit-Score.
    """
    predicted = await call_llm_sentiment(text)
    result    = await judge_sentiment(text, predicted, expected)
    print(f"\n[REAL] '{text[:70]}' → {predicted} (erwartet: {expected}) | {result}")
    assert result["correct"], f"Sentiment falsch: {result['reason']}"


@pytest.mark.asyncio
@pytest.mark.parametrize("question,context,min_score,expect_uncertainty", QUESTION_CASES)
async def test_answer_quality(question, context, min_score, expect_uncertainty):
    """LLM-Antworten sind sachlich, hilfreich und halluzinieren nicht."""
    answer = await call_llm_answer(question, context)
    result = await judge_answer_quality(question, context, answer)
    print(f"\n[ANSWER] Q: '{question}' | Score: {result.get('score')}/4 | {result.get('reason','')[:80]}")
    assert result["score"] >= min_score, f"Score zu niedrig ({result['score']}/4): {result['reason']}"
    assert result["not_hallucinating"], f"Halluziniert: {result['reason']}"
    if expect_uncertainty:
        assert result["admits_uncertainty"], f"Hätte Unsicherheit zugeben sollen: {result['reason']}"


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_id,user_feedback,reference,min_score", COACH_RESPONSE_CASES)
async def test_coach_response_vs_reference(tool_id, user_feedback, reference, min_score):
    """
    Vergleicht Bot-Antworten mit echten Coaching-Nachrichten von Prof. Dr. Diethelm Wahl.
    Der Bot muss nicht identisch antworten, aber ähnlich empathisch, konkret und
    nicht-generisch sein. Referenz = Ground Truth aus dem Piloten.
    """
    bot_response = await call_llm_coach_response(user_feedback, tool_id)
    result       = await judge_coach_response(user_feedback, tool_id, bot_response, reference)
    print(
        f"\n[COACH] {tool_id}\n"
        f"  Bot: '{bot_response[:100]}'\n"
        f"  Score: {result.get('score')}/4 | {result.get('reason','')[:80]}"
    )
    assert result["score"] >= min_score, f"Coach-Antwort zu schwach: {result['reason']}"
    assert result["not_generic"], f"Antwort zu generisch: {result['reason']}"
    assert result["empathetic"], f"Nicht empathisch genug: {result['reason']}"


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def print_summary():
    total = (
        len(SENTIMENT_CASES_SYNTHETIC)
        + len(SENTIMENT_CASES_REAL)
        + len(QUESTION_CASES)
        + len(COACH_RESPONSE_CASES)
    )
    yield
    print(f"\n\n═══════════════════════════════════════════════")
    print(f"  LLM-as-a-Judge Tests abgeschlossen")
    print(f"  Gesamt: {total} Test-Cases")
    print(f"  ├─ Sentiment synthetisch:       {len(SENTIMENT_CASES_SYNTHETIC)}")
    print(f"  ├─ Sentiment echte User:        {len(SENTIMENT_CASES_REAL)}")
    print(f"  ├─ Fragen-Antworten:            {len(QUESTION_CASES)}")
    print(f"  └─ Coach vs. Diethelm-Referenz: {len(COACH_RESPONSE_CASES)}")
    print(f"═══════════════════════════════════════════════\n")
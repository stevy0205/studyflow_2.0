"""
Unit Tests – statische Logik (kein LLM, kein Server nötig)
Ausführen: pytest tests/test_unit.py -v
"""

import re
import sys
import json
import pytest
from pathlib import Path

# Projektpfad damit Imports funktionieren
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools_registry import ToolsRegistry, AREA_ORDER


# ─────────────────────────────────────────────────────────────────────────────
# Helpers – dieselbe Intent-Logik wie in api.py (extrahiert zum Testen)
# ─────────────────────────────────────────────────────────────────────────────

QUESTION_BLOCKLIST = {
    "noch eine frage", "andere methode", "nächste methode ➡️",
    "wiederholen 🔁", "beenden ✅", "nächste methode"
}


def detect_intent(message: str) -> dict:
    text = message.strip().lower()

    is_choose = (
        bool(re.search(r'\b(wähle?|erkläre?|option|methode)\s*[12]\b|\b[12]\s*(wählen|wähle|erkläre?)\b', text))
        or text.strip() in ["1", "2", "1.", "2."]
    )
    choose_idx = 1 if re.search(r'\b2\b', text) else 0

    is_next   = (any(kw in text for kw in ["nächste methode", "nächste ➡️", "neue methode", "andere methode", "➡️"])
                 or text.strip() == "nächste methode") and not is_choose
    is_repeat = any(kw in text for kw in ["wiederholen", "wiederhol", "nochmal", "🔁"])
    is_start  = any(kw in text for kw in ["starten", "start", "🚀", "los", "beginnen", "ok", "okay", "machen", "probier"]) \
                and not is_choose and not is_next
    is_end    = any(kw in text for kw in ["beenden", "fertig", "tschüss", "bye", "aufhören", "stop", "ende", "schluss", "✅"])

    question_kws = ["wie", "was", "warum", "wann", "erkläre", "erklär", "hilf", "kannst", "?", "wieso", "wozu", "welche"]
    is_question  = (any(kw in text for kw in question_kws)
                    and not is_choose and not is_next and not is_start and not is_repeat
                    and text.strip() not in QUESTION_BLOCKLIST
                    and len(text.strip()) > 10)

    return {
        "is_choose": is_choose,
        "choose_idx": choose_idx,
        "is_next": is_next,
        "is_repeat": is_repeat,
        "is_start": is_start,
        "is_end": is_end,
        "is_question": is_question,
    }


def calc_scores(answers: list) -> tuple[dict, list]:
    """Score-Berechnung aus api.py nachgebaut."""
    AREAS = ["prokrastination", "unterbrechungen", "leistung", "emotion"]
    area_scores = {area: sum(answers[i*6:(i+1)*6]) for i, area in enumerate(AREAS)}
    top_areas   = sorted(area_scores, key=lambda a: area_scores[a])[:2]
    return area_scores, top_areas


# ─────────────────────────────────────────────────────────────────────────────
# 1. Intent-Erkennung
# ─────────────────────────────────────────────────────────────────────────────

class TestIntentChoose:
    def test_plain_1(self):
        assert detect_intent("1")["is_choose"] is True

    def test_plain_2(self):
        assert detect_intent("2")["is_choose"] is True

    def test_methode_1(self):
        r = detect_intent("Methode 1")
        assert r["is_choose"] is True
        assert r["choose_idx"] == 0

    def test_methode_2(self):
        r = detect_intent("Methode 2")
        assert r["is_choose"] is True
        assert r["choose_idx"] == 1

    def test_wähle_1(self):
        assert detect_intent("wähle 1")["is_choose"] is True

    def test_erkläre_methode_1(self):
        r = detect_intent("Erkläre Methode 1")
        assert r["is_choose"] is True
        assert r["choose_idx"] == 0

    def test_erkläre_methode_2(self):
        r = detect_intent("Erkläre Methode 2")
        assert r["is_choose"] is True
        assert r["choose_idx"] == 1


class TestIntentStart:
    def test_starten(self):
        assert detect_intent("starten")["is_start"] is True

    def test_starten_emoji(self):
        assert detect_intent("Starten 🚀")["is_start"] is True

    def test_los(self):
        assert detect_intent("Los geht's!")["is_start"] is True

    def test_ok(self):
        assert detect_intent("ok")["is_start"] is True

    def test_start_does_not_trigger_choose(self):
        r = detect_intent("starten")
        assert r["is_choose"] is False

    def test_methode_1_does_not_trigger_start(self):
        # "ok" könnte in "Methode 1 ok" stecken – choose soll dominieren
        r = detect_intent("Methode 1")
        assert r["is_start"] is False  # is_choose dominiert nicht is_start, aber choose_idx richtig


class TestIntentEnd:
    def test_beenden(self):
        assert detect_intent("beenden")["is_end"] is True

    def test_beenden_emoji(self):
        assert detect_intent("Beenden ✅")["is_end"] is True

    def test_tschüss(self):
        assert detect_intent("tschüss")["is_end"] is True

    def test_danke_nicht_end(self):
        # "danke" ist kein end_kw mehr
        assert detect_intent("danke")["is_end"] is False


class TestIntentNext:
    def test_nächste_methode(self):
        assert detect_intent("Nächste Methode")["is_next"] is True

    def test_nächste_methode_emoji(self):
        assert detect_intent("Nächste Methode ➡️")["is_next"] is True

    def test_andere_methode(self):
        assert detect_intent("Andere Methode")["is_next"] is True

    def test_neue_methode(self):
        assert detect_intent("neue methode")["is_next"] is True


class TestIntentRepeat:
    def test_wiederholen(self):
        assert detect_intent("Wiederholen")["is_repeat"] is True

    def test_wiederholen_emoji(self):
        assert detect_intent("Wiederholen 🔁")["is_repeat"] is True

    def test_nochmal(self):
        assert detect_intent("nochmal bitte")["is_repeat"] is True


class TestIntentQuestion:
    def test_echte_frage(self):
        assert detect_intent("Wie funktioniert das genau?")["is_question"] is True

    def test_was_bedeutet(self):
        assert detect_intent("Was bedeutet Chunking?")["is_question"] is True

    def test_kurzer_text_kein_question(self):
        # Zu kurz (< 10 Zeichen)
        assert detect_intent("Wie?")["is_question"] is False

    def test_blocklist_noch_eine_frage(self):
        assert detect_intent("noch eine frage")["is_question"] is False

    def test_wiederholen_kein_question(self):
        assert detect_intent("Wie war das nochmal?")["is_question"] is False  # is_repeat True blockiert


# ─────────────────────────────────────────────────────────────────────────────
# 2. Score-Berechnung
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreCalculation:
    def test_24_answers_required(self):
        answers = [2] * 24
        scores, top = calc_scores(answers)
        assert len(scores) == 4
        assert len(top) == 2

    def test_alle_null_gleicher_score(self):
        answers = [0] * 24
        scores, top = calc_scores(answers)
        assert all(v == 0 for v in scores.values())

    def test_prokrastination_höchster_score_nicht_in_top2(self):
        # Prokrastination = hoher Score → NICHT in top2 (top2 = niedrigster Score)
        answers = [3]*6 + [0]*6 + [0]*6 + [0]*6
        scores, top = calc_scores(answers)
        assert "prokrastination" not in top

    def test_leistung_niedrigster_score_in_top2(self):
        answers = [3]*6 + [3]*6 + [0]*6 + [3]*6
        scores, top = calc_scores(answers)
        assert "leistung" in top

    def test_top2_hat_zwei_bereiche(self):
        answers = [1, 2, 3, 0, 1, 2,   # prokrastination = 9
                   0, 0, 0, 0, 0, 0,   # unterbrechungen = 0  ← top
                   1, 1, 1, 1, 1, 1,   # leistung = 6
                   0, 0, 0, 0, 0, 1]   # emotion = 1  ← top
        scores, top = calc_scores(answers)
        assert len(top) == 2
        assert "unterbrechungen" in top
        assert "emotion" in top

    def test_max_score_18_pro_bereich(self):
        answers = [3] * 24
        scores, _ = calc_scores(answers)
        assert all(v == 18 for v in scores.values())


# ─────────────────────────────────────────────────────────────────────────────
# 3. ToolsRegistry
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def registry():
    # Braucht data/tools.json im Projektverzeichnis
    path = Path(__file__).parent.parent / "data" / "tools.json"
    if not path.exists():
        pytest.skip("tools.json nicht gefunden – bitte data/tools.json bereitstellen")
    return ToolsRegistry(path)


class TestRegistry:
    def test_alle_tools_laden(self, registry):
        tools = registry.all_tools()
        assert len(tools) > 0

    def test_keine_deprecated(self, registry):
        for t in registry.all_tools():
            assert not t.get("_deprecated"), f"{t.get('name')} ist deprecated aber erscheint"

    def test_prokrastination_reihenfolge(self, registry):
        tools = registry.by_category("prokrastination")
        names = [t["name"] for t in tools]
        expected_order = AREA_ORDER["prokrastination"]
        # Alle erwarteten Methoden in richtiger Reihenfolge
        present = [n for n in expected_order if n in names]
        indices = [names.index(n) for n in present]
        assert indices == sorted(indices), f"Falsche Reihenfolge: {names}"

    def test_unterbrechungen_reihenfolge(self, registry):
        tools = registry.by_category("unterbrechungen")
        names = [t["name"] for t in tools]
        expected = [n for n in AREA_ORDER["unterbrechungen"] if n in names]
        indices  = [names.index(n) for n in expected]
        assert indices == sorted(indices)

    def test_next_method_überspringt_used(self, registry):
        tools = registry.by_category("prokrastination")
        if len(tools) < 2:
            pytest.skip("Zu wenige Prokrastinations-Methoden")
        first  = tools[0]
        second = tools[1]
        next_m = registry.next_method(first, used_names=[first["name"]])
        assert next_m is not None
        assert next_m["name"] == second["name"]

    def test_next_method_alle_used_gibt_none(self, registry):
        tools    = registry.by_category("prokrastination")
        all_names = [t["name"] for t in tools]
        result   = registry.next_method(tools[0], used_names=all_names)
        assert result is None

    def test_top_for_area_gibt_erste_methode(self, registry):
        tools = registry.top_for_area("prokrastination")
        assert len(tools) > 0
        assert tools[0]["name"] == AREA_ORDER["prokrastination"][0]

    def test_alle_tools_haben_name(self, registry):
        for t in registry.all_tools():
            assert "name" in t, f"Tool ohne Name: {t}"

    def test_alle_tools_haben_kategorie(self, registry):
        for t in registry.all_tools():
            assert t.get("kategorie") in ["prokrastination", "unterbrechungen", "leistung", "emotion"], \
                f"{t.get('name')} hat ungültige Kategorie: {t.get('kategorie')}"

    def test_format_for_llm_enthält_name(self, registry):
        tool = registry.all_tools()[0]
        text = registry.format_for_llm(tool)
        assert tool["name"] in text


# ─────────────────────────────────────────────────────────────────────────────
# 4. Feedback-Keyword-Klassifikation (statisch)
# ─────────────────────────────────────────────────────────────────────────────

def classify_feedback_static(text: str) -> str:
    text = text.lower()
    pos_kws      = ["super", "🌟", "toll", "klasse", "perfekt", "sehr gut", "top", "prima", "wunderbar"]
    part_pos_kws = ["teilweise gut", "👍", "teilweise", "ganz gut", "größtenteils"]
    neutral_kws  = ["neutral", "😐", "so lala", "mittel", "weder noch"]
    part_neg_kws = ["eher nicht", "👎", "nicht so gut", "nicht ganz", "kaum"]
    neg_kws      = ["hat nicht gepasst", "❌", "schlecht", "gar nicht", "überhaupt nicht", "frustrierend"]

    if any(kw in text for kw in neg_kws):      return "negative"
    if any(kw in text for kw in part_neg_kws): return "partial_negative"
    if any(kw in text for kw in neutral_kws):  return "neutral"
    if any(kw in text for kw in pos_kws):      return "positive"
    if any(kw in text for kw in part_pos_kws): return "partial_positive"
    return "unknown"  # → LLM-Fallback


class TestFeedbackClassification:
    def test_super_emoji(self):
        assert classify_feedback_static("Super! 🌟") == "positive"

    def test_toll(self):
        assert classify_feedback_static("Das war toll!") == "positive"

    def test_teilweise_gut_emoji(self):
        assert classify_feedback_static("Teilweise gut 👍") == "partial_positive"

    def test_neutral_emoji(self):
        assert classify_feedback_static("Neutral 😐") == "neutral"

    def test_eher_nicht_emoji(self):
        assert classify_feedback_static("Eher nicht 👎") == "partial_negative"

    def test_hat_nicht_gepasst(self):
        assert classify_feedback_static("Hat nicht gepasst ❌") == "negative"

    def test_schlecht(self):
        assert classify_feedback_static("War schlecht") == "negative"

    def test_freier_text_unbekannt(self):
        # Freier Text ohne Keywords → LLM-Fallback
        assert classify_feedback_static("Es war irgendwie okay aber nicht wirklich") == "unknown"

    def test_negativ_schlägt_teilneg(self):
        # "gar nicht" (neg) soll gewinnen
        assert classify_feedback_static("war gar nicht gut") == "negative"

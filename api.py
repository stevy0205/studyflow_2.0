"""
StudyFlow – FastAPI Backend
Startbefehl: uvicorn api:app --reload
"""

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv() 
from typing import Optional
from graph import graph
from database import init_db, verify_login, save_result, get_latest_result

# ── App Setup ──────────────────────────────────────────────────────────────────
app = FastAPI(title="StudyFlow Coach")

BASE = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE / "frontend" / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE / "frontend" / "templates"))

# DB beim Start initialisieren
@app.on_event("startup")
def startup():
    init_db()


# ── Models ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class QuestionnaireRequest(BaseModel):
    answers: list
    thread_id: Optional[str] = None
    is_logged_in: bool = False
    username: Optional[str] = None
    user_name: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    thread_id: str
    session_phase: str = "method_selection"
    selected_methods: list = []
    chosen_method: Optional[dict] = None
    used_method_names: list = []   # alle bereits genutzten Methoden-Namen


# ── HTML Seiten ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/questionnaire", response_class=HTMLResponse)
async def questionnaire_page(request: Request):
    return templates.TemplateResponse("questionnaire.html", {"request": request})

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


# ── API: Auth ──────────────────────────────────────────────────────────────────

@app.post("/api/login")
async def login(req: LoginRequest):
    user = verify_login(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Ungültige Zugangsdaten.")

    thread_id = str(uuid.uuid4())

    # Letztes Ergebnis laden falls vorhanden
    saved = get_latest_result(user["username"])

    return {
        "thread_id":        thread_id,
        "username":         user["username"],
        "name":             user["name"],
        "is_logged_in":     True,
        "has_saved_result": saved is not None,
        # Gespeicherte Ergebnisse direkt mitschicken → Frontend kann Fragebogen überspringen
        "saved_result":     saved,
    }


@app.post("/api/guest")
async def guest_start():
    return {
        "thread_id":        str(uuid.uuid4()),
        "is_logged_in":     False,
        "has_saved_result": False,
    }


# ── API: Fragebogen ────────────────────────────────────────────────────────────

@app.post("/api/questionnaire")
async def submit_questionnaire(req: QuestionnaireRequest):
    if len(req.answers) != 24:
        raise HTTPException(status_code=400, detail="Genau 24 Antworten erwartet.")

    thread_id = req.thread_id or str(uuid.uuid4())

    # ── Score-Berechnung direkt (kein LLM, kein Graph) ─────────────────────────
    AREAS = ["prokrastination", "unterbrechungen", "leistung", "emotion"]
    area_scores = {}
    for i, area in enumerate(AREAS):
        area_scores[area] = sum(req.answers[i * 6 : (i + 1) * 6])

    # Top 2 Bereiche = niedrigster Score = größter Entwicklungsbedarf
    top_areas = sorted(area_scores, key=lambda a: area_scores[a])[:2]

    # Methoden direkt aus Registry holen
    from tools_registry import ToolsRegistry
    registry = ToolsRegistry.get()
    selected_methods = []
    for area in top_areas:
        tools = registry.top_for_area(area)
        if tools:
            selected_methods.append(tools[0])

    # ── Intro-Text zusammenbauen ───────────────────────────────────────────────
    area_labels = {
        "prokrastination": "Prokrastination",
        "unterbrechungen": "Unterbrechungen",
        "leistung":        "Leistung",
        "emotion":         "Emotion",
    }

    intro = (
        f"Hey! Ich habe deine Antworten ausgewertet. 🎉\n\n"
        f"Deine Top-Bereiche mit dem größten Entwicklungspotenzial:\n"
        f"1. **{area_labels.get(top_areas[0], top_areas[0])}** (Score: {area_scores[top_areas[0]]}/18)\n"
        f"2. **{area_labels.get(top_areas[1], top_areas[1])}** (Score: {area_scores[top_areas[1]]}/18)\n\n"
        f"Hier sind deine **2 empfohlenen Methoden**:\n\n"
    )
    for i, m in enumerate(selected_methods, 1):
        intro += f"**{i}. {m['name']}** ({m.get('dauer','?')})\n{m.get('kurzbeschreibung','')}\n\n"
    intro += "Tippe **1** oder **2** zum Auswählen, oder stelle eine Frage! 💬"

    # ── Ergebnis in DB speichern (nur eingeloggte User) ────────────────────────
    if req.is_logged_in and req.username:
        save_result(
            username         = req.username,
            area_scores      = area_scores,
            top_areas        = top_areas,
            selected_methods = selected_methods,
            answers          = req.answers,
        )

    return {
        "thread_id":        thread_id,
        "top_areas":        top_areas,
        "area_scores":      area_scores,
        "selected_methods": selected_methods,  # vollständige Objekte
        "intro_message": intro,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_method_detail(method: dict, entschluesse_text: str) -> str:
    """Baut den vollständigen Methoden-Erklärungstext auf."""
    schritte     = method.get("anwendung") or method.get("schritte") or []
    steps_text   = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(schritte))
    erklaerung   = method.get("llm_explanation") or method.get("ziel") or ""
    paraphrase   = method.get("original_paraphrase", "")
    dauer        = method.get("dauer", "")
    dauer_text   = f" · ⏱️ {dauer}" if dauer else ""
    beschreibung = paraphrase or method.get("kurzbeschreibung", "")

    entschluss = method.get("entschluss", {})
    if entschluss and entschluss.get("vorlagen"):
        vorlagen_text = "\n".join(f"• {v}" for v in entschluss["vorlagen"])
        entschluss_block = (
            f"\n\n**📝 {entschluss.get('frage', 'Formuliere deinen Entschluss:')}**\n"
            f"{vorlagen_text}\n_{entschluss.get('hinweis', '')}_"
        )
    else:
        entschluss_block = f"\n\n**📝 Entschlüsse-Vorlagen:**\n{entschluesse_text}"

    return (
        f"✅ **{method['name']}**{dauer_text}\n\n"
        f"{beschreibung}\n\n"
        + (f"💡 _{erklaerung}_\n\n" if erklaerung else "")
        + f"**Anwendung:**\n{steps_text}"
        f"{entschluss_block}\n\n"
        "Hast du noch Fragen, oder tippe **starten** um loszulegen!"
    )


async def _llm_sentiment(text: str) -> str:
    """Klassifiziert Feedback per LLM wenn Keywords nicht matchen."""
    import os
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=10,
        messages=[{
            "role": "system",
            "content": (
                "Du klassifizierst Feedback zu einer Lernmethode. "
                "Antworte NUR mit einem Wort: positive, partial_positive, neutral, partial_negative oder negative."
            )
        }, {
            "role": "user",
            "content": text
        }]
    )
    result = resp.choices[0].message.content.strip().lower()
    valid = {"positive", "partial_positive", "neutral", "partial_negative", "negative"}
    return result if result in valid else "neutral"


async def _llm_answer_question(question: str, method: dict, registry) -> str:
    """Beantwortet eine Frage zur Methode mithilfe der Registry."""
    import os
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    method_context = registry.format_for_llm(method) if method else ""
    # Alle Methoden der gleichen Kategorie als Kontext
    kategorie = method.get("kategorie", "") if method else ""
    related = registry.by_category(kategorie)[:5] if kategorie else []
    related_context = "\n\n---\n\n".join(registry.format_for_llm(m) for m in related if m.get("name") != method.get("name"))

    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.3,
        max_tokens=400,
        messages=[{
            "role": "system",
            "content": (
                "Du bist ein freundlicher Lerncoach. Beantworte die Frage des Studenten "
                "auf Basis der folgenden Methoden-Informationen. Antworte auf Deutsch, maximal 3–4 Sätze.\n\n"
                "WICHTIG: Wenn die Antwort nicht klar aus den Methoden-Informationen hervorgeht, "
                "gib das ehrlich zu – z.B. 'Dazu habe ich leider keine genauen Infos in den Unterlagen.' "
                "Erfinde keine Details. Verweise dann auf die allgemeine Beschreibung der Methode.\n\n"
                f"## Aktuelle Methode:\n{method_context}\n\n"
                f"## Verwandte Methoden:\n{related_context}"
            )
        }, {
            "role": "user",
            "content": question
        }]
    )
    return resp.choices[0].message.content.strip()


# ── API: Chat ──────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    import re
    from tools_registry import ToolsRegistry, ENTSCHLUESSE_VORLAGEN

    registry          = ToolsRegistry.get()
    text              = req.message.strip().lower()
    entschluesse_text = "\n".join(f"• {v}" for v in ENTSCHLUESSE_VORLAGEN)

    phase            = req.session_phase
    selected_methods = req.selected_methods or []
    chosen_method    = req.chosen_method
    used_names       = list(req.used_method_names or [])

    # ── Intent-Erkennung ───────────────────────────────────────────────────────
    # UI-Button-Texte die NUR für is_question blockiert werden
    QUESTION_BLOCKLIST = {"noch eine frage", "andere methode", "nächste methode ➡️",
                          "wiederholen 🔁", "beenden ✅", "nächste methode"}

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

    # Frage: echter Inhalt, kein reiner UI-Button-Text, mindestens 10 Zeichen
    question_kws = ["wie", "was", "warum", "wann", "erkläre", "erklär", "hilf", "kannst", "?", "wieso", "wozu", "welche"]
    is_question  = (any(kw in text for kw in question_kws)
                    and not is_choose and not is_next and not is_start and not is_repeat
                    and text.strip() not in QUESTION_BLOCKLIST
                    and len(text.strip()) > 10)

    # "Noch eine Frage" Button → zeige Eingabeaufforderung ohne LLM
    if text.strip() == "noch eine frage":
        return {
            "reply": "💬 Klar! Stelle deine Frage einfach direkt – ich beantworte sie gerne.",
            "thread_id": req.thread_id,
            "new_phase": phase,
            "chosen_method": chosen_method,
            "used_method_names": used_names,
            "qr_hint": "asking",
        }

    # ── Beenden ────────────────────────────────────────────────────────────────
    if is_end:
        return {"reply": "👋 Super, dass du heute dabei warst! Bis zum nächsten Mal! 🎉",
                "thread_id": req.thread_id, "new_phase": "done", "used_method_names": used_names}

    # ── Frage → LLM ───────────────────────────────────────────────────────────
    if is_question and phase in ("method_detail", "session_active") and chosen_method:
        answer = await _llm_answer_question(req.message, chosen_method, registry)
        qr_after = "detail" if phase == "method_detail" else "session"
        return {
            "reply": f"💬 {answer}",
            "thread_id": req.thread_id,
            "new_phase": phase,
            "chosen_method": chosen_method,
            "used_method_names": used_names,
            "qr_hint": qr_after,
        }

    # ── Methode wählen → Detail ────────────────────────────────────────────────
    if is_choose and phase == "method_selection":
        method = selected_methods[choose_idx] if choose_idx < len(selected_methods) else (selected_methods[0] if selected_methods else None)
        if not method:
            return {"reply": "Keine Methode verfügbar.", "thread_id": req.thread_id, "new_phase": phase, "used_method_names": used_names}
        return {
            "reply": _build_method_detail(method, entschluesse_text),
            "thread_id": req.thread_id,
            "new_phase": "method_detail",
            "chosen_method": method,
            "used_method_names": used_names,
            "qr_hint": "detail",
        }

    # ── Andere Methode (aus method_detail) ────────────────────────────────────
    if is_next and phase == "method_detail":
        current = chosen_method or {}
        next_m  = registry.next_method(current, used_names=used_names) if current else None
        if not next_m and selected_methods:
            # Fallback: erste noch-nicht-verwendete aus selected_methods
            next_m = next((m for m in selected_methods if m["name"] not in used_names), None)
        if not next_m:
            return {
                "reply": "🎉 Du hast alle vorgeschlagenen Methoden gesehen! Tippe **starten** bei einer Methode oder **beenden**.",
                "thread_id": req.thread_id, "new_phase": "method_selection",
                "used_method_names": used_names, "qr_hint": "selection",
            }
        return {
            "reply": _build_method_detail(next_m, entschluesse_text),
            "thread_id": req.thread_id, "new_phase": "method_detail",
            "chosen_method": next_m, "used_method_names": used_names, "qr_hint": "detail",
        }

    # ── Starten ────────────────────────────────────────────────────────────────
    if is_start and phase == "method_detail" and chosen_method:
        method     = chosen_method
        schritte   = method.get("anwendung") or method.get("schritte") or ["Lege los!"]
        dauer      = method.get("dauer", "")
        dauer_text = f"⏱️ Plane dir **{dauer}** ein.\n\n" if dauer else ""
        entschluss = method.get("entschluss", {})
        if entschluss and entschluss.get("bestaetigung"):
            entschluss_block = f"\n\n_{entschluss['bestaetigung']}_"
        else:
            entschluss_block = f"\n\n**📝 Dein Entschluss:**\n{entschluesse_text}"

        # Zur used_names hinzufügen
        if method["name"] not in used_names:
            used_names.append(method["name"])

        reply = (
            f"🚀 **Los geht's mit {method['name']}!**\n\n"
            f"**Erster Schritt:** {schritte[0]}\n\n"
            f"{dauer_text}{entschluss_block}\n\n"
            "Wenn du fertig bist: Wie hat es geklappt? 👇"
        )
        return {
            "reply": reply,
            "thread_id": req.thread_id,
            "new_phase": "session_active",
            "chosen_method": method,
            "used_method_names": used_names,
            "qr_hint": "feedback",
        }

    # ── Session aktiv ──────────────────────────────────────────────────────────
    if phase == "session_active":
        method = chosen_method or {}
        name   = method.get("name", "die Methode")

        # Nächste Methode: exkl. bereits verwendeter
        next_m = registry.next_method(method, used_names=used_names) if method else None

        # ── Nächste Methode direkt zeigen ─────────────────────────────────────
        if is_next:
            if not next_m:
                return {
                    "reply": "🎉 Du hast alle Methoden in diesem Bereich ausprobiert! Klasse Arbeit.\n\nMöchtest du **beenden** oder eine Methode **wiederholen**?",
                    "thread_id": req.thread_id,
                    "new_phase": "session_active",
                    "chosen_method": method,
                    "used_method_names": used_names,
                    "qr_hint": "all_done",
                }
            return {
                "reply": _build_method_detail(next_m, entschluesse_text),
                "thread_id": req.thread_id,
                "new_phase": "method_detail",
                "chosen_method": next_m,
                "used_method_names": used_names,
                "qr_hint": "detail",
            }

        # ── Wiederholen ───────────────────────────────────────────────────────
        if is_repeat:
            return {
                "reply": _build_method_detail(method, entschluesse_text),
                "thread_id": req.thread_id,
                "new_phase": "method_detail",
                "chosen_method": method,
                "used_method_names": used_names,
                "qr_hint": "detail",
            }

        # ── Frage in Session ──────────────────────────────────────────────────
        if is_question:
            answer = await _llm_answer_question(req.message, method, registry)
            return {
                "reply": f"💬 {answer}",
                "thread_id": req.thread_id,
                "new_phase": "session_active",
                "chosen_method": method,
                "used_method_names": used_names,
                "qr_hint": "session",
            }

        # ── Feedback klassifizieren ────────────────────────────────────────────
        # Erst Keywords, dann LLM
        pos_kws      = ["super", "🌟", "toll", "klasse", "perfekt", "sehr gut", "top", "prima", "wunderbar"]
        part_pos_kws = ["teilweise gut", "👍", "teilweise", "ganz gut", "größtenteils"]
        neutral_kws  = ["neutral", "😐", "so lala", "mittel", "weder noch"]
        part_neg_kws = ["eher nicht", "👎", "nicht so gut", "nicht ganz", "kaum"]
        neg_kws      = ["hat nicht gepasst", "❌", "schlecht", "gar nicht", "überhaupt nicht", "frustrierend"]

        if any(kw in text for kw in neg_kws):
            category = "negative"
        elif any(kw in text for kw in part_neg_kws):
            category = "partial_negative"
        elif any(kw in text for kw in neutral_kws):
            category = "neutral"
        elif any(kw in text for kw in pos_kws):
            category = "positive"
        elif any(kw in text for kw in part_pos_kws):
            category = "partial_positive"
        else:
            # LLM-Fallback für freie Texte
            category = await _llm_sentiment(req.message)

        next_hint = (f"\n\nAls nächste Methode würde ich **{next_m['name']}** vorschlagen: "
                     f"{next_m.get('kurzbeschreibung','')}") if next_m else ""

        if category == "negative":
            reply = (f"🙏 Danke für deine Ehrlichkeit! Schade, dass **{name}** nicht gepasst hat.\n\n"
                     f"Das ist wichtiges Feedback – wir probieren etwas anderes.{next_hint}\n\n"
                     "Möchtest du die **nächste Methode** ausprobieren oder **beenden**?")
            qr_hint = "negative"
        elif category == "partial_negative":
            reply = (f"💬 **{name}** hat nicht ganz gepasst – das ist wertvoll zu wissen.{next_hint}\n\n"
                     "Möchtest du die **nächste Methode** starten oder **beenden**?")
            qr_hint = "negative"
        elif category == "neutral":
            reply = (f"🙂 Danke für dein Feedback zu **{name}**!\n\n"
                     f"Neutral ist okay – manchmal braucht eine Methode Wiederholungen.{next_hint}\n\n"
                     "Möchtest du **wiederholen**, die **nächste Methode** starten oder **beenden**?")
            qr_hint = "after_feedback"
        elif category == "partial_positive":
            reply = (f"👍 **{name}** hat teilweise geklappt – Wiederholungen helfen!{next_hint}\n\n"
                     "Möchtest du **wiederholen**, die **nächste Methode** starten oder **beenden**?")
            qr_hint = "after_feedback"
        else:  # positive
            reply = (f"🎉 Toll, dass **{name}** so gut funktioniert hat!\n\n"
                     f"Wiederhole sie am besten regelmäßig.{next_hint}\n\n"
                     "Möchtest du **wiederholen**, die **nächste Methode** starten oder **beenden**?")
            qr_hint = "after_feedback"

        return {
            "reply": reply,
            "thread_id": req.thread_id,
            "new_phase": "session_active",
            "chosen_method": method,
            "used_method_names": used_names,
            "qr_hint": qr_hint,
        }

    # ── Fallback ───────────────────────────────────────────────────────────────
    if selected_methods:
        m1  = selected_methods[0]
        m2  = selected_methods[1] if len(selected_methods) > 1 else None
        txt = f"**1. {m1['name']}** ({m1.get('dauer','')})\n{m1.get('kurzbeschreibung','')}"
        if m2:
            txt += f"\n\n**2. {m2['name']}** ({m2.get('dauer','')})\n{m2.get('kurzbeschreibung','')}"
        txt += "\n\nTippe **1** oder **2** zum Auswählen!"
        return {"reply": txt, "thread_id": req.thread_id, "new_phase": "method_selection",
                "used_method_names": used_names, "qr_hint": "selection"}

    return {"reply": "Ich bin bereit! Wie kann ich dir helfen? 😊",
            "thread_id": req.thread_id, "new_phase": phase, "used_method_names": used_names}


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/methods")
async def get_all_methods():
    """Gibt alle Methoden aus tools.json zurück."""
    from tools_registry import ToolsRegistry
    registry = ToolsRegistry.get()
    return {"methods": registry.all_tools()}
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
    # Frontend sendet den aktuellen Session-State mit
    session_phase: str = "method_selection"  # "method_selection" | "method_detail" | "session_active"
    selected_methods: list = []
    chosen_method: Optional[dict] = None


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


# ── API: Chat ──────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    config = {"configurable": {"thread_id": req.thread_id}}
    text = req.message.strip().lower()

    from langchain_core.messages import HumanMessage
    from tools_registry import ToolsRegistry, ENTSCHLUESSE_VORLAGEN

    registry = ToolsRegistry.get()
    entschluesse_text = "\n".join(f"• {v}" for v in ENTSCHLUESSE_VORLAGEN)

    # ── Keywords ───────────────────────────────────────────────────────────────
    # Methode wählen: "1", "2", "1 wählen", "wähle 1", "methode 1", "erkläre 1" etc.
    import re
    is_choose = bool(re.search(r'\b(wähle?|erkläre?|option|methode)\s*[12]\b|\b[12]\s*(wählen|wähle|erkläre?)\b', text)) \
                or text.strip() in ["1", "2", "1.", "2."]

    # Index: enthält "2" → methode 2, sonst methode 1
    choose_idx = 1 if re.search(r'\b2\b', text) else 0

    next_kws   = ["nächste methode", "nächste", "neue methode", "andere methode", "➡️"]
    is_next    = any(kw in text for kw in next_kws) and not is_choose

    repeat_kws = ["wiederholen", "wiederhol", "nochmal", "🔁"]
    is_repeat  = any(kw in text for kw in repeat_kws)

    start_kws  = ["starten", "start", "los", "beginnen", "ok", "okay", "machen", "probier"]
    is_start   = any(kw in text for kw in start_kws) and not is_choose and not is_next

    end_kws    = ["beenden", "fertig", "tschüss", "bye", "aufhören", "stop", "ende", "schluss"]
    is_end     = any(kw in text for kw in end_kws)

    # State kommt vom Frontend
    phase            = req.session_phase
    selected_methods = req.selected_methods or []
    chosen_method    = req.chosen_method

    # ── Beenden ────────────────────────────────────────────────────────────────
    if is_end:
        return {
            "reply": "👋 Super, dass du heute dabei warst! Bis zum nächsten Mal! 🎉",
            "thread_id": req.thread_id,
            "new_phase": "done",
        }

    # ── Methode wählen → Detail anzeigen ───────────────────────────────────────
    if is_choose and phase == "method_selection":
        method = selected_methods[choose_idx] if choose_idx < len(selected_methods) else (
            selected_methods[0] if selected_methods else None)
        if not method:
            return {"reply": "Keine Methode verfügbar.", "thread_id": req.thread_id, "new_phase": phase}

        schritte    = method.get("anwendung") or method.get("schritte") or []
        steps_text  = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(schritte))
        erklaerung  = method.get("llm_explanation") or method.get("ziel") or ""
        paraphrase  = method.get("original_paraphrase", "")
        dauer       = method.get("dauer", "")
        dauer_text  = f" · ⏱️ {dauer}" if dauer else ""

        # Hauptbeschreibung: Paraphrase bevorzugen (ausführlich), sonst kurzbeschreibung
        if paraphrase:
            beschreibung = paraphrase
        else:
            beschreibung = method.get("kurzbeschreibung", "")

        # Methoden-eigener Entschluss
        entschluss = method.get("entschluss", {})
        if entschluss and entschluss.get("vorlagen"):
            vorlagen_text = "\n".join(f"• {v}" for v in entschluss["vorlagen"])
            entschluss_block = (
                f"\n\n**📝 {entschluss.get('frage', 'Formuliere deinen Entschluss:')}**\n"
                f"{vorlagen_text}\n"
                f"_{entschluss.get('hinweis', '')}_"
            )
        else:
            entschluss_block = f"\n\n**📝 Entschlüsse-Vorlagen:**\n{entschluesse_text}"

        reply = (
            f"✅ **{method['name']}**{dauer_text}\n\n"
            f"{beschreibung}\n\n"
            + (f"💡 _{erklaerung}_\n\n" if erklaerung else "")
            + f"**Anwendung:**\n{steps_text}"
            f"{entschluss_block}\n\n"
            "Hast du noch Fragen, oder tippe **starten** um loszulegen!"
        )
        return {
            "reply": reply,
            "thread_id": req.thread_id,
            "new_phase": "method_detail",
            "chosen_method": method,
        }

    # ── Starten → Session aktiv ────────────────────────────────────────────────
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

        reply = (
            f"🚀 **Los geht's mit {method['name']}!**\n\n"
            f"**Erster Schritt:** {schritte[0]}\n\n"
            f"{dauer_text}"
            f"{entschluss_block}\n\n"
            "Sobald du fertig bist: Wie hat es geklappt? Schreibe mir einfach eine kurze Rückmeldung!"
        )
        return {
            "reply": reply,
            "thread_id": req.thread_id,
            "new_phase": "session_active",
            "chosen_method": method,
        }

    # ── Session aktiv: Feedback direkt verarbeiten (kein LLM) ─────────────────
    if phase == "session_active":
        method = chosen_method or {}
        name   = method.get("name", "die Methode")

        # Nächste Methode aus Registry
        next_m = registry.next_method(method) if method else None

        # ── "Nächste Methode" → direkt Detail der nächsten Methode anzeigen ──
        if is_next and next_m:
            schritte   = next_m.get("anwendung") or next_m.get("schritte") or []
            steps_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(schritte))
            erklaerung = next_m.get("llm_explanation") or next_m.get("ziel") or ""
            paraphrase = next_m.get("original_paraphrase", "")
            dauer      = next_m.get("dauer", "")
            dauer_text = f" · ⏱️ {dauer}" if dauer else ""
            beschreibung = paraphrase or next_m.get("kurzbeschreibung", "")

            entschluss = next_m.get("entschluss", {})
            if entschluss and entschluss.get("vorlagen"):
                vorlagen_text = "\n".join(f"• {v}" for v in entschluss["vorlagen"])
                entschluss_block = (
                    f"\n\n**📝 {entschluss.get('frage', 'Formuliere deinen Entschluss:')}**\n"
                    f"{vorlagen_text}\n_{entschluss.get('hinweis', '')}_"
                )
            else:
                entschluss_block = f"\n\n**📝 Entschlüsse-Vorlagen:**\n{entschluesse_text}"

            reply = (
                f"✅ **{next_m['name']}**{dauer_text}\n\n"
                f"{beschreibung}\n\n"
                + (f"💡 _{erklaerung}_\n\n" if erklaerung else "")
                + f"**Anwendung:**\n{steps_text}"
                f"{entschluss_block}\n\n"
                "Hast du noch Fragen, oder tippe **starten** um loszulegen!"
            )
            return {
                "reply": reply,
                "thread_id": req.thread_id,
                "new_phase": "method_detail",
                "chosen_method": next_m,
            }

        # ── "Wiederholen" → nochmal Detail der aktuellen Methode ─────────────
        if is_repeat and method:
            schritte   = method.get("anwendung") or method.get("schritte") or []
            steps_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(schritte))
            erklaerung = method.get("llm_explanation") or method.get("ziel") or ""
            dauer      = method.get("dauer", "")
            dauer_text = f" · ⏱️ {dauer}" if dauer else ""

            entschluss = method.get("entschluss", {})
            if entschluss and entschluss.get("vorlagen"):
                vorlagen_text = "\n".join(f"• {v}" for v in entschluss["vorlagen"])
                entschluss_block = (
                    f"\n\n**📝 {entschluss.get('frage', 'Formuliere deinen Entschluss:')}**\n"
                    f"{vorlagen_text}\n_{entschluss.get('hinweis', '')}_"
                )
            else:
                entschluss_block = f"\n\n**📝 Entschlüsse-Vorlagen:**\n{entschluesse_text}"

            reply = (
                f"🔁 **{name}** nochmal!{dauer_text}\n\n"
                f"💡 _{erklaerung}_\n\n"
                f"**Anwendung:**\n{steps_text}"
                f"{entschluss_block}\n\n"
                "Tippe **starten** wenn du bereit bist!"
            )
            return {
                "reply": reply,
                "thread_id": req.thread_id,
                "new_phase": "method_detail",
                "chosen_method": method,
            }

        next_hint = f"\n\nAls nächste Methode würde ich **{next_m['name']}** vorschlagen: {next_m.get('kurzbeschreibung','')}" if next_m else ""

        pos_kws      = ["super", "🌟", "toll", "klasse", "perfekt", "sehr gut", "top", "prima", "wunderbar"]
        part_pos_kws = ["teilweise gut", "👍", "gut", "ganz gut", "hat funktioniert", "größtenteils"]
        neutral_kws  = ["neutral", "😐", "so lala", "mittel", "weder noch", "geht so"]
        part_neg_kws = ["eher nicht", "👎", "nicht so gut", "schwierig", "nicht ganz", "kaum"]
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
            category = "neutral"

        if category == "negative":
            reply = (
                f"🙏 Danke für deine Ehrlichkeit! Schade, dass **{name}** nicht gepasst hat.\n\n"
                f"Das ist wichtiges Feedback – wir probieren eine andere Methode.{next_hint}\n\n"
                "Möchtest du die **nächste Methode** ausprobieren oder **beenden**?"
            )
        elif category == "partial_negative":
            reply = (
                f"💬 **{name}** hat diesmal nicht ganz gepasst – das ist wertvoll zu wissen.\n\n"
                f"Ich würde eine andere Methode empfehlen.{next_hint}\n\n"
                "Möchtest du die **nächste Methode** starten oder **beenden**?"
            )
        elif category == "neutral":
            reply = (
                f"🙂 Danke für dein Feedback zu **{name}**!\n\n"
                f"Neutral ist okay – manchmal braucht eine Methode Wiederholungen.{next_hint}\n\n"
                "Möchtest du **wiederholen**, die **nächste Methode** starten oder **beenden**?"
            )
        elif category == "partial_positive":
            reply = (
                f"👍 **{name}** hat teilweise geklappt – ein paar Wiederholungen helfen!{next_hint}\n\n"
                "Möchtest du **wiederholen**, die **nächste Methode** starten oder **beenden**?"
            )
        else:  # positive
            reply = (
                f"🎉 Toll, dass **{name}** so gut funktioniert hat!\n\n"
                f"Wiederhole sie am besten regelmäßig.{next_hint}\n\n"
                "Möchtest du **wiederholen**, die **nächste Methode** starten oder **beenden**?"
            )

        # Nach negativem Feedback → direkt neue Methode vorschlagen
        if category in ("negative", "partial_negative") and next_m:
            new_phase  = "method_selection"
            new_chosen = None
        else:
            new_phase  = "session_active"
            new_chosen = chosen_method

        return {
            "reply": reply,
            "thread_id": req.thread_id,
            "new_phase": new_phase,
            "chosen_method": new_chosen,
            "next_available_method": next_m,
        }

    # ── Fallback: unbekannte Phase → Methodenliste zeigen ─────────────────────
    if selected_methods:
        m1 = selected_methods[0]
        m2 = selected_methods[1] if len(selected_methods) > 1 else None
        txt = (f"**1. {m1['name']}** ({m1.get('dauer','')})\n{m1.get('kurzbeschreibung','')}")
        if m2:
            txt += f"\n\n**2. {m2['name']}** ({m2.get('dauer','')})\n{m2.get('kurzbeschreibung','')}"
        txt += "\n\nTippe **1** oder **2** zum Auswählen!"
        return {"reply": txt, "thread_id": req.thread_id, "new_phase": "method_selection"}

    return {
        "reply": "Ich bin bereit! Wie kann ich dir helfen? 😊",
        "thread_id": req.thread_id,
        "new_phase": phase,
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/methods")
async def get_all_methods():
    """Gibt alle Methoden aus tools.json zurück."""
    from tools_registry import ToolsRegistry
    registry = ToolsRegistry.get()
    return {"methods": registry.all_tools()}
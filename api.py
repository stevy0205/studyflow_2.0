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
from langchain_core.messages import AIMessage

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
        "selected_methods": [
            {
                "name":             m.get("name"),
                "kategorie":        m.get("kategorie"),
                "kurzbeschreibung": m.get("kurzbeschreibung"),
                "dauer":            m.get("dauer"),
            }
            for m in selected_methods
        ],
        "intro_message": intro,
    }


# ── API: Chat ──────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    config = {"configurable": {"thread_id": req.thread_id}}

    from langchain_core.messages import HumanMessage
    result = graph.invoke(
        {"messages": [HumanMessage(content=req.message)]},
        config=config,
    )

    ai_message = ""
    

    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage):
            ai_message = msg.content
            break

    return {"reply": ai_message, "thread_id": req.thread_id}


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/methods")
async def get_all_methods():
    """Gibt alle Methoden aus tools.json zurück."""
    from tools_registry import ToolsRegistry
    registry = ToolsRegistry.get()
    return {"methods": registry.all_tools()}
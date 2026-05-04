"""
database.py – SQLite Datenbank für StudyFlow
User werden optional über Environment Variables erzeugt.
"""

import sqlite3
import hashlib
import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "studyflow.db"


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# 🔐 Seed-User aus ENV laden
def get_seed_users():
    users = []

    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    admin_name = os.getenv("ADMIN_NAME", "Admin")

    if admin_email and admin_password:
        users.append({
            "email": admin_email,
            "password": admin_password,
            "name": admin_name,
        })

    # optional zweiter User
    user_email = os.getenv("SEED_USER_EMAIL")
    user_password = os.getenv("SEED_USER_PASSWORD")
    user_name = os.getenv("SEED_USER_NAME", "Test User")

    if user_email and user_password:
        users.append({
            "email": user_email,
            "password": user_password,
            "name": user_name,
        })

    return users


def init_db():
    """Erstellt Tabellen und optional Seed-User."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                email         TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS results (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                email            TEXT NOT NULL,
                area_scores      TEXT NOT NULL,
                top_areas        TEXT NOT NULL,
                selected_methods TEXT NOT NULL,
                answers          TEXT NOT NULL,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email) REFERENCES users(email)
            );
        """)

        # 🔐 Seed nur wenn ENV gesetzt ist
        for u in get_seed_users():
            conn.execute(
                "INSERT OR IGNORE INTO users (email, name, password_hash) VALUES (?,?,?)",
                (u["email"], u["name"], _hash(u["password"]))
            )

        conn.commit()


# ── Auth ─────────────────────────────────────────────────────────────

def verify_login(email: str, password: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT email, name FROM users WHERE email=? AND password_hash=?",
            (email.lower().strip(), _hash(password))
        ).fetchone()
    return dict(row) if row else None


def register_user(email: str, password: str, name: str) -> dict:
    email = email.lower().strip()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT email FROM users WHERE email=?", (email,)
        ).fetchone()
        if existing:
            raise ValueError("Diese E-Mail-Adresse ist bereits registriert.")

        conn.execute(
            "INSERT INTO users (email, name, password_hash) VALUES (?,?,?)",
            (email, name.strip(), _hash(password))
        )
        conn.commit()

    return {"email": email, "name": name.strip()}


# ── Results ───────────────────────────────────────────────────────────

def save_result(email: str, area_scores: dict, top_areas: list,
                selected_methods: list, answers: list):
    import json
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO results (email, area_scores, top_areas, selected_methods, answers)
               VALUES (?,?,?,?,?)""",
            (
                email,
                json.dumps(area_scores),
                json.dumps(top_areas),
                json.dumps(selected_methods),
                json.dumps(answers),
            )
        )
        conn.commit()


def get_latest_result(email: str) -> dict | None:
    import json
    with get_conn() as conn:
        row = conn.execute(
            """SELECT area_scores, top_areas, selected_methods, answers, created_at
               FROM results WHERE email=? ORDER BY created_at DESC LIMIT 1""",
            (email,)
        ).fetchone()

    if not row:
        return None

    return {
        "area_scores":      json.loads(row["area_scores"]),
        "top_areas":        json.loads(row["top_areas"]),
        "selected_methods": json.loads(row["selected_methods"]),
        "answers":          json.loads(row["answers"]),
        "created_at":       row["created_at"],
    }
import sqlite3
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parent / "reviews.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                uid TEXT PRIMARY KEY,
                reservation_code TEXT,
                checkout_date TEXT,
                eligible_after TEXT,
                reviewed_at TEXT,
                status TEXT DEFAULT 'pending',
                comment_used TEXT,
                error_message TEXT,
                review_url TEXT
            )
        """)
        # Migration : ajouter la colonne si elle n'existe pas encore
        try:
            conn.execute("ALTER TABLE reservations ADD COLUMN review_url TEXT")
        except Exception:
            pass


def upsert_reservation(uid: str, reservation_code: str, checkout_date: date, eligible_after: datetime):
    with get_conn() as conn:
        # Ne pas créer d'entrée si ce code de réservation a déjà été traité avec succès
        existing = conn.execute(
            "SELECT uid FROM reservations WHERE reservation_code = ? AND status = 'reviewed'",
            (reservation_code,)
        ).fetchone()
        if existing:
            return
        conn.execute("""
            INSERT INTO reservations (uid, reservation_code, checkout_date, eligible_after)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(uid) DO NOTHING
        """, (uid, reservation_code, checkout_date.isoformat(), eligible_after.isoformat()))


def get_eligible_reservations():
    now = datetime.now().isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM reservations
            WHERE status = 'pending'
            AND eligible_after <= ?
        """, (now,)).fetchall()
    return [dict(r) for r in rows]


def mark_reviewed(uid: str, comment: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE reservations
            SET status = 'reviewed', reviewed_at = ?, comment_used = ?
            WHERE uid = ?
        """, (datetime.now().isoformat(), comment, uid))


def store_review_url(uid: str, review_url: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE reservations SET review_url = ? WHERE uid = ?",
            (review_url, uid)
        )


def mark_failed(uid: str, error: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE reservations
            SET status = 'failed', error_message = ?
            WHERE uid = ?
        """, (error, uid))


def mark_skipped(uid: str, reason: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE reservations
            SET status = 'skipped', error_message = ?
            WHERE uid = ?
        """, (reason, uid))


def print_stats():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT status, COUNT(*) as n FROM reservations GROUP BY status
        """).fetchall()
    for row in rows:
        print(f"  {row['status']}: {row['n']}")

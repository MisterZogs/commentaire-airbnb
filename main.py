#!/usr/bin/env python3
"""
Agent d'avis Airbnb automatique
Soumet 5 étoiles + commentaire 48h après le départ de chaque locataire.

Usage:
    python main.py          # mode normal
    python main.py --dry    # simulation sans rien soumettre
    python main.py --stats  # affiche les statistiques de la base
    python main.py --reset-failed  # remet en 'pending' les avis en erreur
"""

import sys
import json
import random
import argparse
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

import db
import ical_reader
import reviewer


def send_alert(subject: str, body: str):
    """Envoie un email d'alerte si SMTP configuré dans .env."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    notify_email = os.getenv("NOTIFY_EMAIL")

    if not all([smtp_host, smtp_user, smtp_pass, notify_email]):
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"[Agent Airbnb] {subject}"
    msg["From"] = "noreply@lifaia.com"
    msg["To"] = notify_email

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, notify_email, msg.as_string())
        print(f"  Alerte email envoyée à {notify_email}")
    except Exception as e:
        print(f"  Impossible d'envoyer l'email d'alerte : {e}")

TEMPLATES_FILE = Path(__file__).parent / "templates.json"


def load_templates() -> list[str]:
    with open(TEMPLATES_FILE, encoding="utf-8") as f:
        return json.load(f)["templates"]


def pick_template(templates: list[str], used_recently: list[str]) -> str:
    """Choisit un template en évitant les derniers utilisés."""
    available = [t for t in templates if t not in used_recently[-3:]]
    if not available:
        available = templates
    return random.choice(available)


def get_recently_used_comments() -> list[str]:
    import sqlite3
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT comment_used FROM reservations WHERE comment_used IS NOT NULL ORDER BY reviewed_at DESC LIMIT 3"
            ).fetchall()
        return [r["comment_used"] for r in rows]
    except Exception:
        return []


def run(dry_run: bool = False):
    db.init_db()

    email = os.getenv("AIRBNB_EMAIL")
    password = os.getenv("AIRBNB_PASSWORD")
    ical_url = os.getenv("ICAL_URL")
    delay_hours = int(os.getenv("REVIEW_DELAY_HOURS", "48"))
    locale = os.getenv("AIRBNB_LOCALE", "fr")
    headless = os.getenv("HEADLESS", "false").lower() == "true"

    auth_file = Path(__file__).parent / "auth" / "airbnb_state.json"
    if not email or not ical_url:
        print("Erreur : AIRBNB_EMAIL et ICAL_URL sont requis dans .env")
        sys.exit(1)
    if not password and not auth_file.exists():
        print("Erreur : AIRBNB_PASSWORD requis dans .env (ou lancez d'abord : python3 main.py --login)")
        sys.exit(1)

    templates = load_templates()

    print(f"\n=== Agent Airbnb — {datetime.now().strftime('%d/%m/%Y %H:%M')} ===")
    print(f"Délai configuré : {delay_hours}h après le départ")

    # 1. Récupérer les réservations récentes depuis l'iCal
    print("\n[1/3] Lecture du calendrier iCal...")
    try:
        recent = ical_reader.get_recent_checkouts(ical_url, delay_hours=delay_hours)
    except Exception as e:
        print(f"Erreur iCal : {e}")
        sys.exit(1)

    print(f"  {len(recent)} réservation(s) dans la fenêtre de {delay_hours}h à 14 jours")

    # 2. Mettre à jour la base de données
    print("\n[2/3] Mise à jour de la base...")
    for res in recent:
        eligible_after = datetime.combine(res.checkout, datetime.min.time()) + timedelta(hours=delay_hours)
        db.upsert_reservation(res.uid, res.reservation_code, res.checkout, eligible_after)

    # 3. Traiter les avis éligibles
    print("\n[3/3] Soumission des avis...")
    eligible = db.get_eligible_reservations()

    if not eligible:
        print("  Aucun avis à soumettre pour l'instant.")
    else:
        print(f"  {len(eligible)} avis à soumettre.")

    recently_used = get_recently_used_comments()

    for res in eligible:
        code = res["reservation_code"]
        checkout = res["checkout_date"]
        print(f"\n  → Réservation {code} (départ le {checkout})")

        comment = pick_template(templates, recently_used)

        if dry_run:
            print(f"  [DRY RUN] Commentaire qui serait envoyé :")
            print(f"  « {comment[:80]}... »")
            continue

        success, found_url = reviewer.submit_review(
            reservation_code=code,
            comment=comment,
            email=email,
            password=password,
            locale=locale,
            headless=headless,
            review_url=res.get("review_url"),
        )

        # Stocker l'URL de review si trouvée (pour réutilisation si retry)
        if found_url:
            db.store_review_url(res["uid"], found_url)

        if success:
            db.mark_reviewed(res["uid"], comment)
            recently_used.append(comment)
            print(f"  ✓ Avis soumis.")
        else:
            error_msg = "Échec Playwright — voir screenshots/"
            db.mark_failed(res["uid"], error_msg)
            print(f"  ✗ Échec. Voir screenshots/{code}_error.png")
            send_alert(
                subject=f"Échec avis {code} — action requise",
                body=(
                    f"L'agent Airbnb n'a pas pu soumettre l'avis pour la réservation {code} "
                    f"(départ le {checkout}).\n\n"
                    f"Cause probable : session Airbnb expirée.\n\n"
                    f"Action : relancez la connexion depuis votre Mac :\n"
                    f"  python3 main.py --login\n"
                    f"puis recopiez les cookies sur le VPS :\n"
                    f"  scp -i ~/.ssh/id_ed25519_gringoNoPwd auth/airbnb_state.json "
                    f"gringo@178.104.70.16:~/airbnb-agent/auth/airbnb_state.json\n\n"
                    f"Vous avez 14 jours depuis le départ pour poster l'avis manuellement sur Airbnb."
                )
            )

    print("\n=== Terminé ===")
    db.print_stats()


def main():
    parser = argparse.ArgumentParser(description="Agent d'avis Airbnb automatique")
    parser.add_argument("--login", action="store_true", help="Connexion manuelle et sauvegarde des cookies")
    parser.add_argument("--dry", action="store_true", help="Simulation sans soumission")
    parser.add_argument("--stats", action="store_true", help="Affiche les statistiques")
    parser.add_argument("--reset-failed", action="store_true", help="Remet en pending les avis en échec")
    args = parser.parse_args()

    if args.login:
        locale = os.getenv("AIRBNB_LOCALE", "fr")
        reviewer.login_manual_and_save(locale=locale)
        return

    if args.stats:
        db.init_db()
        print("Statistiques :")
        db.print_stats()
        return

    if args.reset_failed:
        db.init_db()
        with db.get_conn() as conn:
            n = conn.execute("UPDATE reservations SET status='pending', error_message=NULL WHERE status='failed'").rowcount
        print(f"{n} réservation(s) remises en pending.")
        return

    run(dry_run=args.dry)


if __name__ == "__main__":
    main()

import requests
from datetime import date, timedelta
from dataclasses import dataclass
from icalendar import Calendar


@dataclass
class Reservation:
    uid: str
    reservation_code: str
    checkin: date
    checkout: date  # date réelle de départ (DTEND - 1 jour selon convention iCal)


def fetch_reservations(ical_url: str) -> list[Reservation]:
    resp = requests.get(ical_url, timeout=15)
    resp.raise_for_status()

    cal = Calendar.from_ical(resp.content)
    reservations = []

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        summary = str(component.get("SUMMARY", ""))
        # Ignorer les blocages manuels (non des vraies réservations)
        if "Not available" in summary or "Unavailable" in summary or "Indisponible" in summary:
            continue

        uid = str(component.get("UID", ""))
        dtstart = component.get("DTSTART")
        dtend = component.get("DTEND")

        if not uid or not dtstart or not dtend:
            continue

        # Convertir en date si c'est un datetime
        start = dtstart.dt if hasattr(dtstart.dt, "date") else dtstart.dt
        end = dtend.dt if hasattr(dtend.dt, "date") else dtend.dt
        if hasattr(start, "date"):
            start = start.date()
        if hasattr(end, "date"):
            end = end.date()

        # Sur Airbnb, DTEND = date réelle de départ (ex: check-in 28 juin, check-out 29 juin → DTEND=29 juin)
        checkout = end

        # Extraire le code de réservation depuis la DESCRIPTION
        # Format : "Reservation URL: https://www.airbnb.com/hosting/reservations/details/HMXXXXXXXX"
        description = str(component.get("DESCRIPTION", ""))
        reservation_code = None
        for line in description.replace("\\n", "\n").splitlines():
            if "reservations/details/" in line:
                reservation_code = line.strip().rstrip("/").split("/")[-1]
                break
        if not reservation_code:
            reservation_code = uid.split("@")[0] if "@" in uid else uid

        reservations.append(Reservation(
            uid=uid,
            reservation_code=reservation_code,
            checkin=start,
            checkout=checkout,
        ))

    return reservations


def get_recent_checkouts(ical_url: str, delay_hours: int = 48, window_days: int = 14) -> list[Reservation]:
    """Retourne les réservations dont le départ a eu lieu entre delay_hours et window_days*24h."""
    from datetime import datetime, timedelta as td

    all_reservations = fetch_reservations(ical_url)
    now = datetime.now().date()

    eligible = []
    for r in all_reservations:
        days_since_checkout = (now - r.checkout).days
        delay_days = delay_hours / 24
        # La réservation est eligible si le départ est passé depuis assez longtemps
        # mais pas plus de window_days (Airbnb donne 14j pour laisser un avis)
        if delay_days <= days_since_checkout <= window_days:
            eligible.append(r)

    return eligible

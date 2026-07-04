"""Script de debug pour inspecter le wizard de review Airbnb."""
import time
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

load_dotenv()
auth_file = Path("auth/airbnb_state.json")

REVIEW_URL = "https://www.airbnb.fr/hosting/reviews/1720248191740537743/edit"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(storage_state=str(auth_file))
    page = context.new_page()

    page.goto(REVIEW_URL, wait_until="domcontentloaded", timeout=20000)
    # Attendre que les boutons soient présents
    try:
        page.wait_for_selector("button", timeout=10000)
    except PWTimeout:
        print("Aucun bouton trouvé après 10s!")
    time.sleep(2)
    print(f"URL: {page.url}")

    # Lister les frames
    print(f"\n=== Frames ({len(page.frames)}) ===")
    for i, frame in enumerate(page.frames):
        print(f"  [{i}] url={frame.url!r}")

    # Iframes dans le DOM
    iframes = page.locator("iframe").count()
    print(f"\n=== Iframes dans DOM: {iframes} ===")

    page.screenshot(path="screenshots/debug_step0.png")

    # Cliquer Continuer si présent
    try:
        page.get_by_role("button", name="Continuer").click(timeout=5000)
        time.sleep(3)
        print("Continuer cliqué")
        page.screenshot(path="screenshots/debug_step1.png")
    except PWTimeout:
        print("Pas de bouton Continuer (déjà passé)")

    # Lister tous les boutons (Playwright traverse les frames)
    print("\n=== Boutons (Playwright, cross-frame) ===")
    for btn in page.locator("button").all():
        txt = btn.inner_text().strip()[:60]
        frame_url = btn.evaluate("el => window.location.href")
        print(f"  text={txt!r} (frame: {frame_url[-40:]})")

    # Chercher input[type='radio'] via Playwright
    print("\n=== Inputs radio ===")
    radios = page.locator("input[type='radio']")
    print(f"  {radios.count()} radio(s) trouvé(s)")
    for i in range(min(radios.count(), 5)):
        val = radios.nth(i).get_attribute("value")
        name = radios.nth(i).get_attribute("name")
        print(f"    value={val!r} name={name!r}")

    # Cliquer étoile via nth (5ème étoile = index 4)
    print("\n=== Test clic 5ème étoile par position ===")
    # Les étoiles sont probablement des boutons, trouver le 5ème
    star_candidates = page.locator("button").all()
    for btn in star_candidates:
        txt = btn.inner_text().strip()
        if txt in ["Suivant", "Retour", "Enregistrer et quitter",
                   "S'est occupé des poubelles", "Bien entretenu",
                   "Propre et bien rangé", "Autre", "Continuer"]:
            continue
        print(f"  Bouton inconnu (possible étoile): {txt!r}")

    # Essayer de re-cliquer les étoiles (même déjà remplies)
    # Les étoiles sont souvent des SVG sans aria-label explicite
    print("\n=== Tenter de cliquer le 5e star par nth SVG ===")
    svgs = page.locator("svg")
    print(f"  {svgs.count()} SVG(s) trouvé(s)")

    # Cliquer Suivant et observer le résultat
    print("\n=== Clic Suivant + attente 5s ===")
    try:
        btn = page.get_by_role("button", name="Suivant")
        box = btn.bounding_box()
        print(f"  bounding_box={box}")
        btn.click(timeout=5000)
        time.sleep(5)
        page.screenshot(path="screenshots/debug_after_suivant.png")
        print(f"  URL après: {page.url}")
        print(f"  Nb boutons après: {page.locator('button').count()}")
        for btn2 in page.locator("button").all():
            print(f"    {btn2.inner_text().strip()[:60]!r}")
    except Exception as e:
        print(f"  Erreur: {e}")

    browser.close()
    print("\nDone.")

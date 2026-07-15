"""
Automatisation Playwright pour soumettre les avis sur Airbnb.

Si Airbnb change son interface, ajuster les sélecteurs dans les fonctions
_fill_stars(), _fill_recommend() et _fill_comment().
"""

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, BrowserContext, TimeoutError as PWTimeout

AUTH_FILE = Path(__file__).parent / "auth" / "airbnb_state.json"
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"


def _save_context(context: BrowserContext):
    AUTH_FILE.parent.mkdir(exist_ok=True)
    context.storage_state(path=str(AUTH_FILE))


def login_manual_and_save(locale: str = "fr"):
    """
    Ouvre un navigateur visible pour que vous vous connectiez manuellement
    (code SMS, Google, Apple…). Sauvegarde les cookies une fois connecté.
    À lancer une seule fois avec : python main.py --login
    """
    tld = "com" if locale == "en" else locale
    base_url = f"https://www.airbnb.{tld}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print(f"\nOuverture d'Airbnb ({base_url})...")
        print("→ Connectez-vous normalement dans le navigateur (email, mot de passe, code SMS...)")
        print("→ Le script détecte automatiquement quand vous êtes connecté (attente max 3 min)\n")

        page.goto(f"{base_url}/hosting", wait_until="domcontentloaded", timeout=20000)

        # Attendre que l'URL contienne /hosting (= connecté sur le tableau de bord hôte)
        page.wait_for_url(f"**airbnb.{tld}/hosting**", timeout=180000)
        time.sleep(2)

        _save_context(context)
        browser.close()

    print(f"\nCookies sauvegardés dans {AUTH_FILE}")
    print("Vous n'aurez plus besoin de vous reconnecter sauf si votre session expire.\n")


def _login(page: Page, email: str, password: str, locale: str):
    base = f"https://www.airbnb.{locale}" if locale != "en" else "https://www.airbnb.com"
    page.goto(f"{base}/login", wait_until="networkidle", timeout=30000)
    time.sleep(2)

    # Accepter les cookies si la bannière apparaît
    try:
        page.click("button[data-testid='accept-btn']", timeout=4000)
    except PWTimeout:
        pass
    try:
        page.get_by_role("button", name="Accepter").click(timeout=4000)
    except PWTimeout:
        pass

    # Cliquer sur "Continuer avec l'e-mail"
    try:
        page.get_by_role("button", name="Continuer avec l'e-mail").click(timeout=6000)
    except PWTimeout:
        try:
            page.get_by_role("button", name="Continue with email").click(timeout=6000)
        except PWTimeout:
            pass

    page.fill("input[name='email']", email)
    page.get_by_role("button", name="Continuer").click(timeout=8000)
    time.sleep(1)

    page.fill("input[name='password']", password)
    page.get_by_role("button", name="Se connecter").click(timeout=8000)

    page.wait_for_url("**/airbnb.**", timeout=20000)
    time.sleep(3)


def _fill_stars(page: Page):
    """Sélectionne 5 étoiles pour tous les critères visibles."""
    # Méthode 1 : aria-label
    for label in ["5", "5 stars", "5 étoiles"]:
        for el in page.locator(f"[aria-label='{label}']").all():
            try:
                el.click(timeout=2000)
                time.sleep(0.2)
            except PWTimeout:
                pass

    # Méthode 2 : input radio value=5
    for radio in page.locator("input[type='radio'][value='5']").all():
        try:
            radio.check(force=True, timeout=2000)
        except PWTimeout:
            pass

    # Méthode 3 : groupe de 5 boutons SVG (design Airbnb post-2025)
    for group in page.locator("[role='group'], [role='radiogroup']").all():
        btns = group.locator("button").all()
        if len(btns) == 5:
            try:
                btns[4].click(timeout=2000)
                time.sleep(0.3)
            except Exception:
                pass

    # Méthode 4 : JavaScript (fallback ultime si React bloque les clics natifs)
    try:
        page.evaluate("""() => {
            document.querySelectorAll('[role="group"], [role="radiogroup"]').forEach(g => {
                const btns = [...g.querySelectorAll('button')];
                if (btns.length === 5) btns[4].click();
            });
            document.querySelectorAll('input[type="radio"][value="5"]').forEach(r => {
                r.click();
                r.dispatchEvent(new Event('change', {bubbles: true}));
            });
        }""")
        time.sleep(0.5)
    except Exception:
        pass


def _fill_recommend(page: Page):
    """Coche 'Oui' pour la recommandation du locataire."""
    for label in ["Oui", "Yes", "Recommander"]:
        try:
            page.get_by_role("button", name=label).click(timeout=3000)
            return
        except PWTimeout:
            pass
    # Fallback radio
    try:
        page.locator("input[type='radio'][value='true']").first.check(force=True, timeout=3000)
    except PWTimeout:
        pass
    try:
        page.locator("input[type='radio'][value='yes']").first.check(force=True, timeout=3000)
    except PWTimeout:
        pass


def _fill_comment(page: Page, comment: str):
    """Écrit le commentaire public dans le champ de texte."""
    selectors = [
        "textarea[name='publicReview']",
        "textarea[placeholder*='avis']",
        "textarea[placeholder*='review']",
        "textarea[aria-label*='public']",
        "textarea",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            el.wait_for(timeout=4000)
            el.click()
            el.fill(comment)
            return
        except PWTimeout:
            continue
    raise RuntimeError("Impossible de trouver le champ de commentaire.")


def _submit(page: Page):
    for label in ["Envoyer", "Submit", "Publier", "Soumettre"]:
        try:
            page.get_by_role("button", name=label).click(timeout=4000)
            return
        except PWTimeout:
            pass
    # Fallback : bouton submit du formulaire
    page.locator("button[type='submit']").last.click(timeout=5000)


def _screenshot(page: Page, name: str):
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path))
    print(f"  Screenshot sauvegardé : {path}")


def submit_review(
    reservation_code: str,
    comment: str,
    email: str,
    password: str,
    locale: str = "fr",
    headless: bool = False,
    review_url: str | None = None,
) -> tuple[bool, str | None]:
    """
    Ouvre Airbnb, navigue jusqu'à l'avis en attente pour ce code de réservation
    et soumet 5 étoiles + commentaire.
    Retourne (succès, review_url_trouvée_ou_None).
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)

        # Charger l'état d'authentification sauvegardé si disponible
        if AUTH_FILE.exists():
            context = browser.new_context(storage_state=str(AUTH_FILE))
        else:
            context = browser.new_context()

        page = context.new_page()
        page.set_default_timeout(20000)

        tld = "com" if locale == "en" else locale
        base_url = f"https://www.airbnb.{tld}"

        try:
            # Vérifier si on est connecté
            page.goto(f"{base_url}/hosting", wait_until="domcontentloaded", timeout=20000)
            if "/login" in page.url or "se-connecter" in page.url or "connexion" in page.url:
                if password:
                    print("  Connexion à Airbnb...")
                    _login(page, email, password, tld)
                    _save_context(context)
                else:
                    browser.close()
                    raise RuntimeError(
                        "Session expirée. Ajoutez AIRBNB_PASSWORD dans .env ou relancez : python main.py --login"
                    )

            found_review_page = False
            found_review_url = review_url  # URL connue d'un run précédent

            # Si on a déjà l'URL de review, aller directement dessus
            if review_url:
                # /progress/reviews/details/ = page de l'avis du voyageur sur le logement, pas le formulaire hôte
                if "/progress/reviews/details/" in review_url:
                    raise RuntimeError(
                        "URL stockée '/progress/reviews/details/' = avis du voyageur sur le logement. "
                        "Ce n'est pas le formulaire d'avis hôte. Avis peut-être déjà soumis."
                    )
                print(f"  URL review stockée : {review_url}")
                full_review_url = review_url if review_url.startswith("http") else f"{base_url}{review_url}"
                page.goto(full_review_url, wait_until="domcontentloaded", timeout=20000)
                time.sleep(2)
                _screenshot(page, f"{reservation_code}_details")
                if "Access Denied" not in page.content() and page.locator("button").count() > 0:
                    found_review_page = True
                else:
                    print("  URL stockée inaccessible, tentative via page détail...")
                    found_review_url = None

            if not found_review_page:
                # Aller sur la page de détail de la réservation
                details_url = f"{base_url}/hosting/reservations/details/{reservation_code}"
                print(f"  Navigation vers {details_url}")
                page.goto(details_url, wait_until="domcontentloaded", timeout=20000)
                time.sleep(2)
                _screenshot(page, f"{reservation_code}_details")

                # Détecter Access Denied (VPS bloqué par Cloudflare)
                if "Access Denied" in page.content() or page.locator("button").count() == 0:
                    raise RuntimeError(
                        "Page détail bloquée (Access Denied). "
                        "Relancer plus tard ou fournir review_url manuellement."
                    )

            # Chercher un lien d'avis direct sur la page (scroll inclus)
            page.mouse.wheel(0, 600)
            time.sleep(1)
            page.mouse.wheel(0, 600)
            time.sleep(1)
            _screenshot(page, f"{reservation_code}_details_scrolled")

            review_texts = [
                "Écrire un avis", "Laisser un avis", "Évaluer le voyageur",
                "Write a review", "Leave a review", "Rate guest",
            ]
            for sel in [
                f"a[href*='review'][href*='{reservation_code}']",
                "a[href*='/reviews/write']",
                "a[href*='review-guest']",
                "a[href*='write-a-review']",
            ] + [f"button:has-text('{t}')" for t in review_texts] \
              + [f"a:has-text('{t}')" for t in review_texts]:
                try:
                    el = page.locator(sel).first
                    el.wait_for(timeout=1500)
                    href = el.get_attribute("href") or ""
                    print(f"  Lien avis trouvé ({sel}) : {href}")
                    el.click(timeout=5000)
                    time.sleep(2)
                    found_review_page = True
                    break
                except PWTimeout:
                    continue

            if not found_review_page:
                # Ouvrir le menu "Autres actions" (bouton "..." de la page détail)
                print("  Tentative via menu 'Autres actions'...")
                menu_selectors = [
                    "button[aria-label='Autres actions']",
                    "button[aria-label='Other actions']",
                    "button[aria-label='More options']",
                    "button[aria-label='Plus d\\'options']",
                    "button[aria-label='...']",
                    "button[aria-label='Plus']",
                    "button:has-text('...')",
                ]
                for menu_sel in menu_selectors:
                    try:
                        page.locator(menu_sel).first.click(timeout=3000)
                        time.sleep(1.5)
                        _screenshot(page, f"{reservation_code}_menu")
                        print(f"  Menu ouvert via {menu_sel}")
                        break
                    except PWTimeout:
                        continue

                _screenshot(page, f"{reservation_code}_menu")

                # Chercher l'option avis dans le menu déroulant
                for t in review_texts + ["avis", "review"]:
                    for role in ["menuitem", "option", "link", "button"]:
                        try:
                            page.get_by_role(role, name=t).click(timeout=2000)
                            found_review_page = True
                            break
                        except PWTimeout:
                            pass
                    if found_review_page:
                        break

                # Fallback : naviguer directement vers le href du lien review trouvé
                if not found_review_page:
                    for a in page.locator("a[href*='review'], a[href*='avis']").all():
                        href = a.get_attribute("href") or ""
                        if not href:
                            continue
                        # /progress/reviews/details/ = page de l'avis du voyageur sur le logement
                        if "/progress/reviews/details/" in href:
                            print(f"  Lien ignoré (avis voyageur sur logement) : {href}")
                            continue
                        found_review_url = href  # stocker pour réutilisation future
                        print(f"  Navigation directe vers : {href}")
                        full_url = href if href.startswith("http") else f"{base_url}{href}"
                        page.goto(full_url, wait_until="domcontentloaded", timeout=20000)
                        time.sleep(2)
                        found_review_page = True
                        break

            if not found_review_page:
                raise RuntimeError(
                    "Bouton d'avis introuvable. Voir screenshots/_menu.png pour inspecter le menu."
                )

            _screenshot(page, f"{reservation_code}_before")

            def _click_next() -> bool:
                """Clique sur Suivant/Continuer/Next et retourne True si la page a changé."""
                url_before = page.url
                content_before = page.locator("main, [role='main'], body").first.inner_html()[:500]
                for name in ["Suivant", "Continuer", "Continue", "Next"]:
                    try:
                        page.get_by_role("button", name=name).click(timeout=3000)
                        time.sleep(5)  # SPA React : transition lente, 5s nécessaires
                        url_after = page.url
                        content_after = page.locator("main, [role='main'], body").first.inner_html()[:500]
                        if url_after != url_before or content_after != content_before:
                            return True
                        # Bouton cliqué mais page inchangée = boucle infinie
                        print(f"  Bouton '{name}' cliqué mais page inchangée — arrêt.")
                        return False
                    except PWTimeout:
                        pass
                return False

            def _is_intro_page() -> bool:
                """Détecte la page d'intro du wizard (pas d'étoiles, pas de textarea)."""
                has_stars = page.locator("[role='group'] button, [role='radiogroup'] button").count() > 0
                has_textarea = page.locator("textarea").count() > 0
                has_radio = page.locator("input[type='radio']").count() > 0
                return not has_stars and not has_textarea and not has_radio

            # Étape intro : cliquer "Continuer" pour démarrer le wizard
            if _is_intro_page():
                print("  Page intro — clic Continuer...")
                _click_next()

            intro_count = 0  # nombre de fois qu'on revient sur l'intro dans la boucle

            # Boucle sur les pages du wizard (étoiles, recommandation, commentaire)
            for step in range(30):
                _screenshot(page, f"{reservation_code}_step{step+1}")

                # Si on est revenu à la page d'intro, on clique Continuer une fois de plus
                # mais si ça arrive deux fois, c'est une boucle : les étoiles ne se sélectionnent pas
                if _is_intro_page():
                    intro_count += 1
                    if intro_count >= 2:
                        raise RuntimeError(
                            "Wizard cyclé vers page intro — _fill_stars() échoue à sélectionner les étoiles. "
                            "Session peut-être expirée, ou sélecteurs à mettre à jour."
                        )
                    print(f"  Étape {step+1} : retour intro (cycle {intro_count}) — re-clic Continuer")
                    _click_next()
                    continue

                # Si on atteint le champ commentaire, on sort de la boucle
                if page.locator("textarea").count() > 0:
                    print(f"  Étape {step+1} : champ commentaire trouvé")
                    break

                # Page de recommandation (Oui/Non)
                rec_found = False
                for label in ["Oui", "Yes", "Recommander"]:
                    try:
                        page.get_by_role("button", name=label).click(timeout=1500)
                        rec_found = True
                        print(f"  Étape {step+1} : recommandation '{label}' sélectionnée")
                        break
                    except PWTimeout:
                        pass
                if not rec_found:
                    try:
                        page.locator("input[type='radio'][value='true'], input[type='radio'][value='yes']").first.check(force=True, timeout=1500)
                        rec_found = True
                    except PWTimeout:
                        pass

                # Page d'étoiles (critère quelconque)
                _fill_stars(page)

                # Avancer à la page suivante
                if not _click_next():
                    print(f"  Étape {step+1} : impossible d'avancer")
                    break
                print(f"  Étape {step+1} : avancé")
            else:
                raise RuntimeError("Wizard trop long — arrêt après 30 étapes.")

            print("  Écriture du commentaire...")
            _fill_comment(page, comment)

            _screenshot(page, f"{reservation_code}_filled")

            # Avancer depuis la page commentaire vers la page recommandation
            print("  Avancement vers recommandation...")
            _click_next()

            # Page recommandation : sélectionner "Oui"
            print("  Recommandation finale : Oui")
            _fill_recommend(page)
            _click_next()  # avance vers "Message prive" (facultatif)

            # Page message prive — on laisse vide et on envoie
            _screenshot(page, f"{reservation_code}_before_submit")

            print("  Soumission finale (Envoyer)...")
            _submit(page)
            time.sleep(3)

            _screenshot(page, f"{reservation_code}_after")
            _save_context(context)

            print(f"  Avis soumis pour {reservation_code}.")
            return True, found_review_url

        except Exception as e:
            try:
                _screenshot(page, f"{reservation_code}_error")
            except Exception:
                pass
            print(f"  Erreur pour {reservation_code} : {e}")
            return False, found_review_url

        finally:
            browser.close()

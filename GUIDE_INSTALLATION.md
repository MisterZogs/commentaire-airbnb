# Guide d'installation — Agent Avis Airbnb Automatique

Ce script poste automatiquement un avis 5 étoiles + commentaire à chaque
locataire, 48h après son départ par défaut (réglable via `REVIEW_DELAY_HOURS`
dans `.env`, voir étape 4). Il tourne pour son propre compte : il n'y a pas
de service central, chacun héberge sa propre copie avec ses propres
identifiants Airbnb.

## Ce dont tu as besoin

- Un compte Airbnb hôte avec au moins une annonce
- Un serveur qui tourne 24/7 (un petit VPS suffit — Hetzner, OVH, DigitalOcean
  proposent des offres à quelques euros/mois), ou ton ordinateur si tu le
  laisses allumé
- Un peu de terminal / ligne de commande

## 1. Récupérer le code

```bash
git clone <URL_DU_REPO> airbnb-agent
cd airbnb-agent
```

## 2. Installer les dépendances

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium   # sur Linux/VPS uniquement
```

## 3. Récupérer ton URL iCal Airbnb

1. Va sur Airbnb > **Calendrier**
2. Sélectionne ton annonce > clique sur **"..."** (autres options)
3. **Exporter le calendrier** → copie l'URL `.ics` proposée

Cette URL contient un token secret propre à ton compte : ne la partage pas.

## 4. Configurer

```bash
cp .env.example .env
```

Édite `.env` et remplis au minimum :

```
AIRBNB_EMAIL=ton@email.com
AIRBNB_PASSWORD=ton_mot_de_passe
ICAL_URL=https://www.airbnb.fr/calendar/ical/....ics?s=....
```

Les autres champs (`REVIEW_DELAY_HOURS`, `AIRBNB_LOCALE`, `HEADLESS`) ont des
valeurs par défaut raisonnables. Les champs `SMTP_*` sont optionnels : ils
servent uniquement à recevoir un email si un avis échoue (ex: session
expirée). Sans SMTP configuré, le script fonctionne quand même, juste sans
alerte email.

## 5. Personnaliser les commentaires (optionnel)

Modifie `templates.json` — 10 commentaires par défaut, adapte-les à ton
style. Le script évite de réutiliser les 3 derniers pour paraître naturel.

## 6. Première connexion (obligatoire, à faire une fois)

```bash
python3 main.py --login
```

Ça ouvre un vrai navigateur (pas headless) pour te connecter à Airbnb à la
main. **Important** : la première fois, Airbnb demande souvent une
vérification (SMS, email...) — fais-la manuellement dans cette fenêtre.

Une fois connecté, les cookies sont sauvegardés dans `auth/airbnb_state.json`
et réutilisés automatiquement ensuite (pas besoin de refaire `--login` à
chaque lancement).

Si tu configures ça sur un VPS distant sans écran, fais cette étape depuis
ton ordinateur perso (en local), puis copie le fichier de cookies sur le VPS :

```bash
scp auth/airbnb_state.json user@ton-vps:~/airbnb-agent/auth/airbnb_state.json
```

## 7. Tester en simulation

```bash
python3 main.py --dry
```

Ça affiche ce qui serait envoyé sans rien soumettre réellement — vérifie que
les réservations récentes remontent bien et que les commentaires te
plaisent.

## 8. Lancer pour de vrai

```bash
python3 main.py
```

## 9. Automatiser (cron)

Sur le VPS :

```bash
mkdir -p logs
crontab -e
```

Ajoute une ligne (ici : tous les jours à 15h) :

```
0 15 * * * cd /chemin/vers/airbnb-agent && /chemin/vers/.venv/bin/python3 main.py >> logs/cron.log 2>&1
```

Adapte le chemin à ton installation. Sur un VPS, mets bien `HEADLESS=true`
dans `.env` (pas d'écran disponible).

## Commandes utiles

```bash
python3 main.py --stats         # état de la base (reviewed/pending/failed)
python3 main.py --reset-failed  # relance les avis en échec
python3 main.py --dry           # simulation, rien n'est soumis
```

## En cas de souci

- **Avis non trouvé / erreur Playwright** : regarde
  `screenshots/{CODE}_before.png` et `{CODE}_error.png` pour voir ce que le
  navigateur a vu. Airbnb change son interface de temps en temps ; si ça
  casse, il faut ajuster les sélecteurs dans `reviewer.py`.
- **Erreur de connexion** : supprime `auth/airbnb_state.json` et refais
  `python3 main.py --login`.
- **URL iCal expirée** : régénère-en une nouvelle depuis Airbnb (Calendrier
  > Exporter).
- **Rien ne se passe** : `python3 main.py --stats` pour voir l'état de la
  base, et `logs/cron.log` pour voir la sortie du dernier passage cron.

## Important — responsabilité

Ce script automatise une action (poster un avis) sur un compte Airbnb.
Les conditions d'utilisation d'Airbnb n'autorisent pas explicitement ce
type d'automatisation côté utilisateur — l'usage se fait sous ta propre
responsabilité et à tes risques (au pire, un compte peut être limité ou
suspendu par Airbnb). Chacun héberge et fait tourner sa propre copie avec
ses propres identifiants : personne d'autre n'a accès à ton compte Airbnb
ni à tes données.

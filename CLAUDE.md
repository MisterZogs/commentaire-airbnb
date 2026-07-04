# Agent Avis Airbnb Automatique

## Objectif
Soumettre automatiquement un avis 5 étoiles + commentaire à chaque locataire,
48h après son départ. L'utilisateur loue un appartement toute l'année (~100 réservations/an).

## Architecture

```
iCal Airbnb (URL gratuite)  →  ical_reader.py  →  db.py (SQLite)
                                                        ↓
                                                  main.py (orchestrateur)
                                                        ↓
                                                  reviewer.py (Playwright)
                                                        ↓
                                                Airbnb : 5 ★ + commentaire
```

## Fichiers clés

| Fichier | Rôle |
|---|---|
| `main.py` | Point d'entrée, orchestration |
| `ical_reader.py` | Lecture du calendrier iCal Airbnb |
| `db.py` | SQLite — suivi des réservations traitées |
| `reviewer.py` | Playwright — automatisation navigateur Airbnb |
| `templates.json` | 10 commentaires rotatifs (personnalisables) |
| `.env` | Credentials (non versionné) |
| `reviews.db` | Base SQLite auto-créée |
| `auth/airbnb_state.json` | Cookies Playwright (auto-créé après 1ère connexion) |
| `screenshots/` | Captures d'écran avant/après chaque soumission |

## Configuration initiale (à faire une fois)

```bash
# 1. Installer les dépendances
pip install -r requirements.txt
playwright install chromium

# 2. Créer le fichier de config
cp .env.example .env
# Remplir AIRBNB_EMAIL, AIRBNB_PASSWORD, ICAL_URL dans .env

# 3. Obtenir l'URL iCal
# Airbnb > Calendrier > cliquer "..." > Exporter le calendrier
# Copier l'URL .ics dans ICAL_URL du .env
```

## Utilisation

```bash
python main.py           # lancement normal
python main.py --dry     # simulation : voir ce qui serait envoyé sans rien soumettre
python main.py --stats   # voir l'état de la base (pending/reviewed/failed)
python main.py --reset-failed  # relancer les avis en échec
```

## Automatisation (cron)

Pour tourner toutes les 6h automatiquement :

```bash
# Ouvrir crontab
crontab -e

# Ajouter cette ligne (adapter le chemin)
0 */6 * * * cd /Users/gaetan/Documents/IA/commentaire-airbnb && python main.py >> logs/cron.log 2>&1
```

Créer le dossier logs : `mkdir -p logs`

## Comportement du script

1. **Lit l'iCal** pour trouver les réservations dont le départ est entre J-2 et J-14
2. **Stocke en base** chaque réservation avec sa date d'éligibilité (départ + 48h)
3. **Soumet les avis** pour les réservations éligibles non traitées
4. **Tourne l'avis** parmi 10 templates pour paraître naturel (évite les 3 derniers utilisés)
5. **Prend des screenshots** avant/après chaque soumission (dans `screenshots/`)
6. **Sauvegarde les cookies** Airbnb pour ne pas se reconnecter à chaque fois

## Statuts en base

- `pending` : réservation importée, pas encore éligible ou pas encore traitée
- `reviewed` : avis soumis avec succès
- `failed` : échec Playwright (voir `screenshots/{code}_error.png`)
- `skipped` : ignoré manuellement

## Dépannage

**L'avis n'est pas trouvé par Playwright :**
- L'URL `airbnb.fr/review-guest/{CODE}` peut changer si Airbnb modifie son interface
- Consulter `screenshots/{code}_before.png` pour voir ce que Playwright voit
- Ajuster les sélecteurs dans `reviewer.py` dans `_fill_stars()`, `_fill_recommend()`, `_fill_comment()`
- Lancer avec `HEADLESS=false` dans `.env` pour voir le navigateur en direct

**Erreur de connexion :**
- Supprimer `auth/airbnb_state.json` pour forcer une reconnexion
- Vérifier que le mot de passe dans `.env` est correct
- Airbnb peut demander une vérification 2FA lors de la première connexion (la faire manuellement avec `HEADLESS=false`)

**Erreur iCal :**
- L'URL iCal expire parfois, en regénérer une dans Airbnb

## Personnalisation des commentaires

Modifier `templates.json` pour adapter les textes. Le script évite de réutiliser
les 3 derniers commentaires utilisés pour varier les avis.

## Choix techniques

- **iCal** (pas Gmail) : plus simple, pas d'OAuth requis, donne les dates de départ
- **Playwright** (pas l'API officielle) : Airbnb n'a pas d'API publique pour les avis
- **SQLite** : pas de serveur requis, fichier local suffisant pour ~100 résa/an
- **Pas de génération IA** : templates fixes pour éviter de dépendre d'une clé API
  (peut être ajouté plus tard si souhaité)

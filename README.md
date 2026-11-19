# HALTUP — prototype

HALTUP transforme quelques informations simples (sport, objectif, niveau, matériel, lieu, durée) en **une séance de musculation claire et adaptée**, via un formulaire court et un chatbot en français.

Projet scolaire de start-up fictive. Prototype non déployé, non commercialisé, destiné aux adultes. HALTUP ne remplace ni un professionnel de santé ni un entraîneur qualifié.

## Lancer le projet

Prérequis : **Python 3.9 ou plus récent** (déjà présent sur macOS). Aucune installation de paquet n'est nécessaire.

```bash
python3 server.py
```

Puis ouvrir <http://127.0.0.1:8000>. Arrêt : `Ctrl+C`.

Tests automatisés du moteur :

```bash
python3 -m unittest discover -s tests -v
```

Tests de la dictée vocale dans le navigateur (reconnaissance simulée) : serveur lancé, ouvrir <http://127.0.0.1:8000/__tests__/voice.html> ; le titre de l'onglet affiche « OK n/n » ou « ÉCHEC ». Cette page n'est servie que si le serveur écoute en local.

## Ce qui fonctionne sans clé d'IA (mode démonstration)

Tout le parcours : accueil, formulaire, chat en texte libre (analyse par mots-clés), génération de séance, adaptations (« pas de banc », « réduis à 30 minutes », « plus facile », « match demain », « autres exercices »), garde-fous (âge, douleur, hors sujet, nutrition, charges maximales), sources et limites. S'y ajoutent les trois scénarios de démonstration et les boutons « Remplacer » / « Retirer » sur chaque exercice.

**Douleur ou blessure** : seule la zone est demandée (sans détail médical). Les exercices qui la sollicitent (champ `zones` du catalogue) et les sauts sont écartés, et le volume est réduit. Un bandeau rappelle que ce tri est approximatif et recommande l'avis d'un professionnel. Aucune séance n'est proposée si la zone est inconnue, s'il y a plus de deux zones, des signes d'alerte, ou trop peu d'exercices restants. Le badge **Mode démonstration** l'indique dans l'en-tête.

## Activer un modèle d'IA (facultatif)

1. Copier `.env.example` en `.env` (fichier ignoré par Git) et le remplir.
2. Pour Claude API : `AI_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=…`, puis installer le SDK officiel :
   ```bash
   python3 -m pip install -r requirements-ai.txt
   ```
3. Pour un autre service exposant `/chat/completions` : `AI_PROVIDER=openai_compatible`, `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`.
4. Relancer `python3 server.py` : le badge passe à **Mode IA**.

| Variable | Rôle | Défaut |
|---|---|---|
| `AI_PROVIDER` | `none`, `anthropic` ou `openai_compatible` | `none` |
| `ANTHROPIC_API_KEY` | Clé Claude API (console Claude), lue uniquement par le serveur | — |
| `AI_MODEL` | Modèle utilisé | `claude-opus-5-5` pour Anthropic |
| `AI_EFFORT` | Effort du modèle Claude (`low` conseillé pour un chat) | `low` |
| `AI_BASE_URL`, `AI_API_KEY` | Service compatible | — |
| `AI_TIMEOUT_SECONDS` | Délai maximal d'un appel | `30` |
| `HOST`, `PORT` | Adresse d'écoute | `127.0.0.1`, `8000` |

> Claude Code (l'outil utilisé pour programmer) et une clé Claude API (utilisée par l'application) sont deux choses distinctes : un abonnement Claude Code ne fournit pas de clé pour faire fonctionner HALTUP.

En mode IA, le modèle **interprète le message** et peut **proposer une sélection d'exercices**, mais uniquement parmi une liste d'exercices déjà filtrés (matériel, niveau, fatigue). Le serveur revalide tout (valeurs autorisées, identifiants, âge et douleur jamais confirmés par l'IA) ; séries, répétitions, repos et durée restent calculés par le moteur. En cas d'erreur, de refus ou de réponse invalide, HALTUP revient au moteur de règles et l'affiche. Ce mode **n'a pas été testé avec une vraie clé** dans cette version.

## Architecture

Choix : serveur Python **sans dépendance** (bibliothèque standard) + interface HTML/CSS/JS sans framework. Raison : se lance en une commande sur un Mac d'élève, rien à installer, code lisible et facile à modifier. Node.js n'était pas installé sur la machine de développement.

```
server.py                  Serveur HTTP (pages statiques + API JSON)
altup/
  constants.py             Marque, sports, objectifs, niveaux, lieux, matériel (source unique)
  directives.py            Directives de l'assistant et messages fixes (source unique)
  data/exercises.json      Catalogue d'exercices (60) + échauffement + retour au calme
  data/sports.json         Profils sportifs (10 sports + général)
  knowledge.py             Chargement et vérification des données
  profile.py               Profil : nettoyage des entrées, validation du formulaire
  parser.py                Analyse du texte libre (mode démo)
  generator.py             Construction de séance : matériel, niveau, fatigue, durée
  assistant.py             Orchestration d'un tour : sécurité → IA facultative → moteur
  ai.py                    Fournisseurs d'IA configurables + extraction JSON
  config.py                Variables d'environnement (.env facultatif)
public/                    Interface (index.html, styles.css, app.js)
tests/test_scenarios.py    Tests automatisés du moteur
docs/                      Documents de projet (start-up, chatbot, sources, validation, présentation)
```

API : `GET /api/config`, `POST /api/chat` (`{message, state}`), `POST /api/generate` (`{profile, state}`), `POST /api/adapt` (`{action: "replace"|"remove", exercise_id, state}`).
L'état de la conversation est gardé **dans l'onglet du navigateur** et renvoyé à chaque requête ; le serveur ne stocke rien.

## Confidentialité

**Dictée vocale** (bouton micro dans la Conversation) : reconnaissance vocale intégrée au navigateur (Web Speech API, `SpeechRecognition` ou `webkitSpeechRecognition`, langue `fr-FR`), sans dépendance, clé ni service ajouté. Un clic sur le micro démarre l'écoute (le navigateur peut demander l'autorisation du micro la première fois) ; les mots provisoires s'affichent dans un aperçu, puis « Arrêter » (ou le micro) place le texte final dans le champ, ajouté au texte déjà saisi ; « Annuler » ou Échap l'abandonne. Rien n'est jamais envoyé sans clic sur « Envoyer ». HALTUP n'utilise pas MediaRecorder, ne capte, ne téléverse ni ne conserve aucun audio. En revanche, selon le navigateur, l'audio peut être traité en ligne par son éditeur (Google pour Chrome, Microsoft pour Edge, Apple pour Safari) : c'est indiqué dans la ligne de confidentialité sous la conversation. Si le navigateur permet de vérifier qu'une transcription locale du français est disponible (API `SpeechRecognition.available`), elle est utilisée ; aucun modèle n'est téléchargé. Firefox ne propose pas cette fonction : un message invite alors à écrire au clavier.

Pas de compte, pas de base de données. La conversation disparaît à la fermeture de l'onglet. Aucune réponse du profil n'est enregistrée dans le navigateur : l'ancienne option « Mémoriser mes choix » a été retirée, et l'éventuelle trace qu'elle avait laissée (`altup.profil.v1`) est supprimée au chargement de la page. En mode IA, les messages du chat sont envoyés au fournisseur configuré (indiqué sous le chat) ; les messages repérés localement comme évoquant une douleur, une blessure ou une minorité ne sont pas transmis, et sont remplacés par une mention neutre dans l'historique envoyé lors des tours suivants. Le bouton « Supprimer la séance » (zone Conversation, désactivé tant qu'aucune séance n'est affichée) retire la séance affichée sans toucher au profil ni à la conversation.

## Documents

Voir [docs/](docs/) : fiche start-up, modèle économique hypothétique, stratégie du chatbot, instructions, sources et licences, scénarios de validation, plan Google Slides, script de démo, vision future, et l'audit au regard des consignes du Wagon (`docs/10-audit-wagon.md`).

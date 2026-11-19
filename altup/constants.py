"""Constantes centralisées d'HALTUP : marque, sports, objectifs, niveaux, matériel, lieux.

Ces listes sont aussi envoyées à l'interface via /api/config : modifier ce fichier
suffit pour changer les libellés du formulaire.
"""

BRAND = {
    "name": "HALTUP",
    "tagline": "Votre séance de musculation, adaptée à votre sport, votre objectif et votre matériel.",
    "pitch": (
        "HALTUP transforme quelques informations simples en une séance de musculation "
        "claire, adaptée à votre profil et facile à suivre."
    ),
    "disclaimer": (
        "HALTUP est un prototype pédagogique destiné aux adultes. Il ne remplace ni un "
        "professionnel de santé ni un entraîneur qualifié."
    ),
}

# Ordre d'affichage conservé. "autre" = sport non listé : séance générale.
SPORTS = [
    {"id": "football", "label": "Football"},
    {"id": "basketball", "label": "Basketball"},
    {"id": "rugby", "label": "Rugby"},
    {"id": "athletisme", "label": "Athlétisme"},
    {"id": "volleyball", "label": "Volleyball"},
    {"id": "handball", "label": "Handball"},
    {"id": "tennis", "label": "Tennis"},
    {"id": "natation", "label": "Natation"},
    {"id": "boxe", "label": "Boxe"},
    {"id": "cyclisme", "label": "Cyclisme"},
    {"id": "autre", "label": "Autre sport / sport non listé"},
]

ATHLETICS_FOCUS = [
    {"id": "general", "label": "Athlétisme général"},
    {"id": "sprint_sauts", "label": "Sprint / sauts"},
]

GOALS = [
    {"id": "force", "label": "Force"},
    {"id": "muscle", "label": "Prise de muscle"},
    {"id": "explosivite", "label": "Explosivité"},
    {"id": "endurance", "label": "Endurance musculaire"},
    {"id": "forme", "label": "Remise en forme générale"},
    {"id": "perte_poids", "label": "Accompagnement d'un objectif de perte de poids"},
]

LEVELS = [
    {"id": "debutant", "label": "Débutant", "rank": 1},
    {"id": "intermediaire", "label": "Intermédiaire", "rank": 2},
    {"id": "avance", "label": "Avancé", "rank": 3},
]

PLACES = [
    {"id": "maison", "label": "Maison"},
    {"id": "salle", "label": "Salle de sport"},
    {"id": "exterieur", "label": "Extérieur"},
    {"id": "autre", "label": "Autre lieu"},
]

# "aucun" et "poids_corps" signifient tous deux : uniquement le poids du corps.
EQUIPMENT = [
    {"id": "aucun", "label": "Aucun matériel"},
    {"id": "poids_corps", "label": "Poids du corps"},
    {"id": "halteres", "label": "Haltères"},
    {"id": "barre", "label": "Barre et poids"},
    {"id": "banc", "label": "Banc"},
    {"id": "machines", "label": "Machines"},
    {"id": "elastiques", "label": "Élastiques"},
    {"id": "kettlebell", "label": "Kettlebell"},
    {"id": "medecine_ball", "label": "Ballon médicinal"},
]

# Zones signalées en cas de gêne : uniquement une région du corps, jamais de détail médical.
# Elles servent à écarter les exercices qui la sollicitent (champ "zones" du catalogue).
PAIN_ZONES = [
    {"id": "epaule", "label": "Épaule"},
    {"id": "coude_poignet", "label": "Coude, poignet ou main"},
    {"id": "cou_haut_dos", "label": "Cou ou haut du dos"},
    {"id": "dos_bas", "label": "Bas du dos"},
    {"id": "hanche", "label": "Hanche ou aine"},
    {"id": "genou", "label": "Genou"},
    {"id": "cheville_pied", "label": "Cheville ou pied"},
    {"id": "inconnu", "label": "Je ne sais pas / je préfère ne pas préciser"},
]
PAIN_ZONE_IDS = {z["id"] for z in PAIN_ZONES}
MAX_PAIN_ZONES = 2  # au-delà, le tri par zone n'est plus assez fiable pour proposer une séance

# Scénarios de démonstration : ils remplissent le formulaire, l'utilisateur lance lui-même la génération.
DEMO_SCENARIOS = [
    {
        "id": "foot_explosivite_salle",
        "title": "Football — explosivité — salle",
        "summary": "Séance de puissance en complément des entraînements de football.",
        "profile": {"sport": "football", "goal": "explosivite", "level": "intermediaire", "duration": 45,
                    "place": "salle", "equipment": ["banc", "halteres", "kettlebell", "machines", "medecine_ball"],
                    "fatigue_recent": False, "fatigue_next": False, "fatigue_none": True,
                    "other_equipment": "", "other_equipment_none": True, "pain": False},
        "why": [
            "Objectif explosivité : un ou deux exercices de puissance, choisis selon le matériel, ouvrent la séance, quand vous êtes encore frais.",
            "Football : la séance privilégie les jambes en travail unilatéral, la chaîne arrière et le gainage.",
            "Complément d'entraînement : 45 minutes, 3 séries par exercice et repos complets pour garder la qualité du geste plutôt que la fatigue.",
        ],
        "caveat": "Le prototype ne connaît pas votre volume réel d'entraînement de football ni votre calendrier : l'orientation sportive reste indicative (confiance faible).",
    },
    {
        "id": "maison_sans_materiel",
        "title": "À la maison — sans matériel",
        "summary": "Séance complète au poids du corps, sans équipement.",
        "profile": {"sport": "autre", "goal": "forme", "level": "debutant", "duration": 30,
                    "place": "maison", "equipment": ["aucun"], "fatigue_recent": False, "fatigue_next": False,
                    "fatigue_none": True, "other_equipment": "", "other_equipment_none": True, "pain": False},
        "why": [
            "Aucun matériel : seuls des exercices au poids du corps sont retenus.",
            "Remise en forme, niveau débutant : 2 séries par exercice, difficulté modérée et variantes plus faciles proposées.",
            "30 minutes : le volume est calculé pour tenir dans ce temps, échauffement et retour au calme compris.",
        ],
        "caveat": "Pas de sport précisé : la séance reste générale et équilibrée.",
    },
    {
        "id": "rugby_match_demain",
        "title": "Rugby — match demain",
        "summary": "Séance courte et légère à la veille d'une rencontre.",
        "profile": {"sport": "rugby", "goal": "force", "level": "intermediaire", "duration": 30,
                    "place": "salle", "equipment": ["banc", "barre", "halteres", "machines"],
                    "fatigue_recent": False, "fatigue_next": True, "fatigue_none": False,
                    "other_equipment": "", "other_equipment_none": True, "pain": False},
        "why": [
            "Match prévu dans les prochaines 24–48 h : pas de sauts, pas de travail lourd à la barre, 2 séries seulement.",
            "Charges modérées avec une large marge (3 à 4 répétitions en réserve) pour arriver frais au match.",
            "Rugby : équilibre entre poussées, tirages et gainage.",
        ],
        "caveat": "La façon de gérer la veille d'un match dépend de chaque joueur et de son staff : si votre club prévoit autre chose, suivez ses consignes. Le repos complet reste aussi une option.",
    },
]

DURATIONS = [20, 30, 40, 45, 60, 75, 90]
MIN_DURATION = 15
MAX_DURATION = 120
DEFAULT_DURATION = 45

SPORT_IDS = {s["id"] for s in SPORTS}
GOAL_IDS = {g["id"] for g in GOALS}
LEVEL_RANK = {lv["id"]: lv["rank"] for lv in LEVELS}
PLACE_IDS = {p["id"] for p in PLACES}
EQUIPMENT_IDS = {e["id"] for e in EQUIPMENT}


def label(items, item_id, default="—"):
    for it in items:
        if it["id"] == item_id:
            return it["label"]
    return default


def public_config():
    """Données non sensibles nécessaires à l'interface."""
    return {
        "brand": BRAND,
        "sports": SPORTS,
        "athleticsFocus": ATHLETICS_FOCUS,
        "goals": GOALS,
        "levels": [{"id": lv["id"], "label": lv["label"]} for lv in LEVELS],
        "places": PLACES,
        "equipment": EQUIPMENT,
        "durations": DURATIONS,
        "painZones": PAIN_ZONES,
        "maxPainZones": MAX_PAIN_ZONES,
        "scenarios": DEMO_SCENARIOS,
        "minDuration": MIN_DURATION,
        "maxDuration": MAX_DURATION,
    }

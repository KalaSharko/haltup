"""Chargement et vérification de la base de connaissance (exercices + profils sportifs)."""
from __future__ import annotations

import json
import os

from .constants import EQUIPMENT_IDS, GOAL_IDS, PAIN_ZONE_IDS

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

PATTERNS = {
    "power_lower", "power_upper", "squat", "hinge", "lunge", "push_h", "pull_h",
    "push_v", "pull_v", "carry", "calf", "adductor", "shoulder", "core_anti_ext",
    "core_rot", "conditioning",
}

# Ordre d'exécution dans la séance : puissance d'abord (fraîcheur), gainage et cardio à la fin.
PATTERN_ORDER = [
    "power_lower", "power_upper", "squat", "hinge", "lunge", "push_h", "pull_h",
    "push_v", "pull_v", "carry", "adductor", "calf", "shoulder", "core_anti_ext",
    "core_rot", "conditioning",
]


def _load(name):
    with open(os.path.join(_DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def _validate_exercises(data):
    ids = set()
    for ex in data["exercises"]:
        assert ex["id"] not in ids, "identifiant en double : %s" % ex["id"]
        ids.add(ex["id"])
        assert ex["pattern"] in PATTERNS, ex["id"]
        assert ex["level"] in (1, 2, 3), ex["id"]
        assert isinstance(ex["equipment"], list) and ex["equipment"], ex["id"]
        for option in ex["equipment"]:
            for item in option:
                assert item in EQUIPMENT_IDS, (ex["id"], item)
        for g in ex["goals"]:
            assert g in GOAL_IDS, (ex["id"], g)
        assert ex.get("zones"), "zones manquantes : %s" % ex["id"]
    for item in data["exercises"] + data["warmup"] + data["cooldown"]:
        for z in item.get("zones", []):
            assert z in PAIN_ZONE_IDS and z != "inconnu", (item["id"], z)
    for ex in data["exercises"]:
        for ref in ("easier", "less_equipment"):
            if ex.get(ref):
                assert ex[ref] in ids, (ex["id"], ref, ex[ref])


CATALOG = _load("exercises.json")
_validate_exercises(CATALOG)
SPORTS_DATA = _load("sports.json")

EXERCISES = {ex["id"]: ex for ex in CATALOG["exercises"]}
WARMUP = {w["id"]: w for w in CATALOG["warmup"]}
COOLDOWN = {c["id"]: c for c in CATALOG["cooldown"]}
CATALOG_META = CATALOG["meta"]
SPORTS_META = SPORTS_DATA["meta"]


def sport_profile(sport_id: str, athletics_focus: str | None = None) -> dict:
    sports = SPORTS_DATA["sports"]
    if sport_id == "athletisme" and athletics_focus == "sprint_sauts":
        return sports["athletisme_sprint_sauts"]
    return sports.get(sport_id) or sports["autre"]


def available_equipment(equipment: list) -> set:
    """Le poids du corps est toujours disponible ; 'aucun' n'ajoute rien."""
    return {e for e in equipment if e not in ("aucun",)} | {"poids_corps"}


def is_feasible(ex: dict, available: set) -> bool:
    return any(all(item in available for item in option) for option in ex["equipment"])


def needed_equipment(ex: dict, available: set) -> list:
    """Option de matériel réellement utilisée avec le matériel disponible."""
    for option in ex["equipment"]:
        if all(item in available for item in option):
            return option
    return ex["equipment"][0]


def equipment_label_list(items: list) -> str:
    from .constants import EQUIPMENT, label
    if not items:
        return "Poids du corps"
    return " + ".join(label(EQUIPMENT, i) for i in items)


def sources_for(sport: dict) -> list:
    out = [{
        "title": "%s v%s" % (CATALOG_META["name"], CATALOG_META["version"]),
        "detail": CATALOG_META["source"],
        "license": CATALOG_META["license"],
        "date": CATALOG_META["written_on"],
        "status": CATALOG_META["review_status"],
    }, {
        "title": "%s v%s — %s" % (SPORTS_META["name"], SPORTS_META["version"], sport["name"]),
        "detail": SPORTS_META["method"],
        "license": SPORTS_META["license"],
        "date": SPORTS_META["written_on"],
        "status": "Niveau de confiance : %s. %s" % (sport["confidence"], sport["limits"]),
    }]
    for src in sport.get("sources", []):
        out.append(src)
    return out

"""Profil de séance : valeurs par défaut, nettoyage des données reçues et fusion.

Toute donnée venant du navigateur ou d'un modèle d'IA passe par `sanitize_patch`
avant d'être utilisée : les valeurs inconnues sont ignorées.
"""
from __future__ import annotations

from .constants import (
    EQUIPMENT_IDS, GOAL_IDS, LEVEL_RANK, MAX_DURATION, MIN_DURATION, PAIN_ZONE_IDS, PLACE_IDS, SPORT_IDS,
)


def empty_profile() -> dict:
    return {
        "sport": None, "athletics_focus": None, "other_sport": "", "goal": None,
        "level": None, "duration": None, "place": None, "equipment": [],
        "other_equipment": "", "other_equipment_none": False,
        "fatigue_recent": False, "fatigue_next": False, "fatigue_none": False,
        "pain": None, "pain_zones": [], "adult": None,
    }


def _short_text(value, limit):
    if not isinstance(value, str):
        return None
    return " ".join(value.split())[:limit]


def sanitize_patch(raw) -> dict:
    """Ne garde que les champs connus et les valeurs autorisées."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    if raw.get("sport") in SPORT_IDS:
        out["sport"] = raw["sport"]
    if raw.get("athletics_focus") in ("general", "sprint_sauts"):
        out["athletics_focus"] = raw["athletics_focus"]
    if "other_sport" in raw:
        txt = _short_text(raw["other_sport"], 40)
        if txt is not None:
            out["other_sport"] = txt
    if raw.get("goal") in GOAL_IDS:
        out["goal"] = raw["goal"]
    if raw.get("level") in LEVEL_RANK:
        out["level"] = raw["level"]
    if raw.get("duration") is not None:
        try:
            out["duration"] = max(1, min(MAX_DURATION, int(raw["duration"])))
        except (TypeError, ValueError):
            pass
    if raw.get("place") in PLACE_IDS:
        out["place"] = raw["place"]
    if isinstance(raw.get("equipment"), list):
        out["equipment"] = sorted({e for e in raw["equipment"] if e in EQUIPMENT_IDS})
    if "other_equipment" in raw:
        txt = _short_text(raw["other_equipment"], 80)
        if txt is not None:
            out["other_equipment"] = txt
    for key in ("fatigue_recent", "fatigue_next", "fatigue_none", "other_equipment_none"):
        if isinstance(raw.get(key), bool):
            out[key] = raw[key]
    for key in ("pain", "adult"):
        if key in raw and raw[key] in (True, False, None):
            out[key] = raw[key]
    if isinstance(raw.get("pain_zones"), list):
        out["pain_zones"] = sorted({z for z in raw["pain_zones"] if z in PAIN_ZONE_IDS})
    return out


def merge(profile: dict, patch: dict) -> dict:
    merged = dict(profile)
    merged.update(patch)
    if merged.get("sport") != "athletisme":
        merged["athletics_focus"] = None
    if merged.get("pain") is not True:
        merged["pain_zones"] = []
    return merged


def pain_status(profile: dict) -> str:
    """'none' (pas de douleur), 'need_zone', 'insufficient' ou 'zones' (séance prudente possible)."""
    if profile.get("pain") is not True:
        return "none"
    zones = profile.get("pain_zones") or []
    if not zones:
        return "need_zone"
    from .constants import MAX_PAIN_ZONES
    if "inconnu" in zones or len(zones) > MAX_PAIN_ZONES:
        return "insufficient"
    return "zones"


def sanitize_profile(raw) -> dict:
    return merge(empty_profile(), sanitize_patch(raw))


def level_rank(profile: dict) -> int:
    return LEVEL_RANK.get(profile.get("level") or "debutant", 1)


def validate_form_profile(profile: dict) -> list:
    """Erreurs explicites pour le formulaire (le chat, lui, tolère les manques)."""
    errors = []
    if not profile.get("sport"):
        errors.append("Choisissez un sport (ou « Autre sport »).")
    if not profile.get("goal"):
        errors.append("Choisissez un objectif principal.")
    if not profile.get("level"):
        errors.append("Indiquez votre niveau.")
    d = profile.get("duration")
    if not d:
        errors.append("Indiquez une durée disponible.")
    elif d < MIN_DURATION:
        errors.append("La durée minimale est de %d minutes." % MIN_DURATION)
    if not profile.get("place"):
        errors.append("Indiquez votre lieu d'entraînement.")
    if not profile.get("equipment"):
        errors.append("Cochez au moins une option de matériel (ou « Aucun matériel »).")
    if not (profile.get("other_equipment") or "").strip() and not profile.get("other_equipment_none"):
        errors.append("Autre matériel : précisez-le ou cochez « Aucun autre matériel ».")
    if not (profile.get("fatigue_recent") or profile.get("fatigue_next") or profile.get("fatigue_none")):
        errors.append("Charge sportive : cochez une situation ou « Aucun entraînement ni match à signaler ».")
    elif profile.get("fatigue_none") and (profile.get("fatigue_recent") or profile.get("fatigue_next")):
        errors.append("Charge sportive : « Aucun entraînement ni match » ne peut pas être coché avec une autre situation.")
    if profile.get("pain") is None:
        errors.append("Répondez à la question sur la douleur ou la blessure (oui / non).")
    if profile.get("adult") is not True:
        errors.append("HALTUP est réservé aux adultes : confirmez avoir 18 ans ou plus.")
    return errors

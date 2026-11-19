"""Orchestration d'un tour de conversation.

Ordre de priorité : (1) règles de sécurité locales, (2) IA facultative pour comprendre le message,
(3) moteur de règles pour construire ou adapter la séance. L'état de la conversation est conservé
par le navigateur (temporaire) et renvoyé à chaque requête ; il est entièrement revalidé ici.
"""
from __future__ import annotations

import json
import re

from . import ai
from .constants import (
    EQUIPMENT, GOALS, LEVELS, MIN_DURATION, PAIN_ZONES, PLACES, SPORTS, DEFAULT_DURATION, label,
)
from .directives import AI_OUTPUT_CONTRACT, GLOSSARY, MESSAGES, system_prompt
from .generator import build_session, candidate_exercises, find_replacement
from .knowledge import EXERCISES
from .parser import looks_on_topic, normalize, parse_message
from .profile import (
    empty_profile, merge, pain_status, sanitize_patch, sanitize_profile, validate_form_profile,
)

LEVEL_ORDER = ["debutant", "intermediaire", "avance"]
GATE_REPLIES = [
    {"label": "J'ai 18 ans ou plus, aucune douleur", "message": "J'ai 18 ans ou plus et aucune douleur ni blessure."},
    {"label": "J'ai une douleur ou une blessure", "message": "J'ai une douleur ou une blessure."},
    {"label": "J'ai moins de 18 ans", "message": "Je suis mineur."},
]
AGE_REPLIES = [
    {"label": "J'ai 18 ans ou plus", "message": "J'ai 18 ans ou plus."},
    {"label": "J'ai moins de 18 ans", "message": "Je suis mineur."},
]
ZONE_REPLIES = [{"label": z["label"], "message": ("Zone : %s." % z["label"]) if z["id"] != "inconnu"
                 else "Je préfère ne pas préciser la zone."} for z in PAIN_ZONES]
FOLLOW_UP_REPLIES = [
    {"label": "Je n'ai pas de banc", "message": "Je n'ai pas de banc.", "requires": "banc"},
    {"label": "Réduire à 30 min", "message": "Réduis la séance à 30 minutes."},
    {"label": "Variante plus facile", "message": "Je débute, donne-moi une variante plus facile."},
    {"label": "Match demain", "message": "J'ai un match ou un entraînement demain."},
    {"label": "Autres exercices", "message": "Propose-moi d'autres exercices."},
]


# ---------------------------------------------------------------- état

def sanitize_state(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    spec = raw.get("spec") if isinstance(raw.get("spec"), dict) else None
    if spec:
        ids = [i for i in spec.get("ids", []) if isinstance(i, str) and i in EXERCISES][:8]
        seed = spec.get("seed") if isinstance(spec.get("seed"), int) else 1
        spec = {"ids": ids, "seed": seed} if ids else None
    history = []
    for h in (raw.get("history") or [])[-8:]:
        if isinstance(h, dict) and h.get("role") in ("user", "assistant") and isinstance(h.get("text"), str):
            history.append({"role": h["role"], "text": h["text"][:500]})
    asked = [a for a in (raw.get("asked") or []) if a in ("profile", "gates")]
    assumed = [a for a in (raw.get("assumed") or []) if isinstance(a, str)][:8]
    seed = raw.get("seed") if isinstance(raw.get("seed"), int) and 0 < raw.get("seed") < 10 ** 6 else 1
    return {"profile": sanitize_profile(raw.get("profile")), "spec": spec, "history": history,
            "asked": asked, "assumed": assumed, "seed": seed}


def new_state() -> dict:
    return {"profile": empty_profile(), "spec": None, "history": [], "asked": [], "assumed": [], "seed": 1}


def _text(t):
    return {"kind": "text", "text": t}


def _reply(state, messages, quick=None, notice=None):
    for m in messages:
        if m["kind"] == "text":
            state["history"].append({"role": "assistant", "text": m["text"][:500]})
    state["history"] = state["history"][-8:]
    out = {"messages": messages, "state": state, "quickReplies": quick or []}
    if notice:
        out["notice"] = notice
    return out


def _follow_ups(profile):
    eq = profile.get("equipment") or []
    return [{"label": q["label"], "message": q["message"]} for q in FOLLOW_UP_REPLIES
            if not q.get("requires") or q["requires"] in eq]


# ---------------------------------------------------------------- hypothèses et manques

def _missing(profile):
    miss = []
    if not profile.get("sport"):
        miss.append("votre sport (ou « aucun sport en particulier »)")
    if not profile.get("goal"):
        miss.append("votre objectif (force, prise de muscle, explosivité, endurance musculaire, remise en forme, perte de poids)")
    if not profile.get("level"):
        miss.append("votre niveau (débutant, intermédiaire, avancé)")
    if not profile.get("duration"):
        miss.append("le temps disponible")
    if not profile.get("equipment") and not profile.get("place"):
        miss.append("votre lieu et votre matériel")
    return miss


def _apply_assumptions(profile, state):
    """Hypothèses raisonnables, annoncées à l'utilisateur, quand une info non critique manque."""
    notes = []
    p = dict(profile)
    if not p.get("sport"):
        p["sport"] = "autre"
        notes.append("Sport non précisé : séance de préparation générale.")
    if not p.get("goal"):
        p["goal"] = "forme"
        notes.append("Objectif non précisé : remise en forme générale.")
    if not p.get("level"):
        p["level"] = "debutant"
        notes.append("Niveau non précisé : niveau débutant retenu par prudence.")
    if not p.get("duration"):
        p["duration"] = DEFAULT_DURATION
        notes.append("Durée non précisée : %d minutes." % DEFAULT_DURATION)
    if not p.get("equipment"):
        if p.get("place") == "salle":
            p["equipment"] = ["banc", "halteres", "machines"]
            notes.append("Matériel non précisé : en salle, je suppose des haltères, un banc et des machines.")
        else:
            p["equipment"] = ["aucun"]
            notes.append("Matériel non précisé : séance au poids du corps uniquement.")
    if p.get("other_equipment"):
        notes.append("Le matériel « %s » est noté mais n'est pas utilisé dans la sélection automatique." % p["other_equipment"])
    if p["duration"] < MIN_DURATION:
        notes.append(MESSAGES["too_short"] % p["duration"])
        p["duration"] = MIN_DURATION
    state["assumed"] = notes
    return p, notes


# ---------------------------------------------------------------- IA facultative

def _ai_understand(message, state, local_profile):
    """Demande au modèle un JSON (réponse, informations du profil, sélection). Tout est revalidé."""
    candidates = candidate_exercises(_apply_assumptions(local_profile, dict(state))[0])
    payload = {
        "ALLOWED_VALUES": {
            "sport": [s["id"] for s in SPORTS], "athletics_focus": ["general", "sprint_sauts"],
            "goal": [g["id"] for g in GOALS], "level": [lv["id"] for lv in LEVELS],
            "place": [p["id"] for p in PLACES], "equipment": [e["id"] for e in EQUIPMENT],
            "duration": "entier en minutes (15 à 120)", "fatigue_recent / fatigue_next / pain / adult": "booléens",
        },
        "CURRENT_PROFILE": {k: v for k, v in local_profile.items() if k not in ("pain", "pain_zones")},
        "HAS_SESSION": bool(state.get("spec")),
        "CANDIDATES": candidates,
        "RECENT_CONVERSATION": state["history"][-6:],
        "USER_MESSAGE": message,
    }
    data = ai.complete_json(system_prompt() + "\n\n" + AI_OUTPUT_CONTRACT,
                            json.dumps(payload, ensure_ascii=False))
    reply = data.get("reply") if isinstance(data.get("reply"), str) else ""
    reply = reply.strip()[:700]
    patch = sanitize_patch(data.get("profile_patch") or {})
    patch.pop("pain_zones", None)  # la zone ne vient que de l'utilisateur
    # L'IA peut rendre le profil plus prudent, jamais moins : âge et douleur viennent de l'utilisateur.
    if patch.get("adult") is True:
        patch.pop("adult")
    if patch.get("pain") is False:
        patch.pop("pain")
    allowed = {c["id"] for c in candidates}
    ids = []
    for i in data.get("exercise_ids") or []:
        if isinstance(i, str) and i in allowed and i not in ids:
            ids.append(i)
    if not 3 <= len(ids) <= 7:
        ids = []
    return reply, patch, ids


# ---------------------------------------------------------------- tour de conversation

def _equipment_update(current, add, remove):
    eq = set(current or [])
    if "aucun" in add and len(add) == 1:
        eq = {"aucun"}
    else:
        eq |= {a for a in add if a != "aucun"}
    eq -= set(remove)
    if len(eq) > 1:
        eq.discard("aucun")
    if not eq and (current or remove):
        eq = {"aucun"}
    return sorted(eq)


REDACTED = "[message non conservé : il évoquait une gêne, une blessure ou l'âge]"


def _redact_last_user_message(state):
    """Les messages liés à la santé ou à l'âge restent locaux : ils ne figurent pas dans l'historique
    éventuellement transmis à un modèle d'IA lors des tours suivants."""
    for h in reversed(state["history"]):
        if h["role"] == "user":
            h["text"] = REDACTED
            return


def _glossary_answer(normalized):
    for key, text in GLOSSARY.items():
        if key in normalized:
            return text
    return None


def handle_message(message: str, raw_state) -> dict:
    state = sanitize_state(raw_state)
    message = (message or "").strip()[:1000]
    if not message:
        return _reply(state, [_text("Votre message est vide : décrivez votre séance ou posez une question.")])
    state["history"].append({"role": "user", "text": message[:500]})
    parsed = parse_message(message)
    intents = parsed["intents"]
    t = parsed["normalized"]
    old = dict(state["profile"])

    if "restart" in intents and not parsed["patch"]:
        fresh = new_state()
        return _reply(fresh, [_text(MESSAGES["restart"])])

    # 1. Sécurité locale : traitée avant tout appel externe.
    if intents & {"minor", "pain", "red_flag"} or (old.get("pain") is True and not old.get("pain_zones")):
        _redact_last_user_message(state)
    if "minor" in intents:
        state["profile"]["adult"] = False
        state["spec"] = None
        return _reply(state, [_text(MESSAGES["minor"])])
    awaiting_zone = old.get("pain") is True and not old.get("pain_zones")
    local_pain = False  # message lié à une gêne : traité localement, jamais envoyé à l'IA
    if "red_flag" in intents and ("pain" in intents or awaiting_zone or old.get("pain") is True):
        state["profile"]["pain"] = True
        state["profile"]["pain_zones"] = ["inconnu"]
        state["spec"] = None
        return _reply(state, [_text(MESSAGES["pain_red_flag"])])
    pain_patch = {}
    if "pain" in intents or (awaiting_zone and (parsed["zones"] or "zone_unknown" in intents)):
        local_pain = True
        pain_patch["pain"] = True
        if parsed["zones"]:
            pain_patch["pain_zones"] = sorted(set(old.get("pain_zones") or []) - {"inconnu"} | set(parsed["zones"]))
        elif "zone_unknown" in intents:
            pain_patch["pain_zones"] = ["inconnu"]
        else:
            pain_patch["pain_zones"] = list(old.get("pain_zones") or [])
    if "extreme" in intents:
        return _reply(state, [_text(MESSAGES["extreme"])], _follow_ups(state["profile"]) if state["spec"] else None)

    patch = dict(parsed["patch"])
    patch.update(pain_patch)
    eq_changed = bool(parsed["add_equipment"] or parsed["remove_equipment"])
    if eq_changed:
        patch["equipment"] = _equipment_update(old.get("equipment"), parsed["add_equipment"], parsed["remove_equipment"])

    # 2. IA facultative (jamais pour un message qui évoque une gêne).
    ai_reply, ai_ids, notice = "", [], None
    mode = ai.status()
    if mode["mode"] == "ai" and not local_pain:
        try:
            ai_reply, ai_patch, ai_ids = _ai_understand(message, state, merge(old, patch))
            for k, v in ai_patch.items():
                patch.setdefault(k, v)
                if k == "equipment":
                    patch[k] = v
            if ai_patch.get("pain") is True:
                # L'IA a repéré une gêne que les règles locales n'ont pas vue : on demande la zone.
                patch["pain"] = True
                patch["pain_zones"] = []
                ai_reply, ai_ids = "", []
        except ai.AIError as exc:
            notice = "%s (%s)" % (MESSAGES["ai_fallback"], exc)

    pre = []
    if "nutrition" in intents:
        pre.append(_text(MESSAGES["nutrition"]))
    if "shorter" in intents and "duration" not in patch:
        base = old.get("duration") or DEFAULT_DURATION
        patch["duration"] = max(MIN_DURATION, base - 10)

    nothing_new = not patch and not (intents & {"easier", "harder", "fatigue", "shorter"}) and not re.search(
        r"(autres? exercices|autre variante|change(r)? (les|d') ?exercices|nouvelle version|autre seance)", t)

    if nothing_new:
        if pre:
            return _reply(state, pre, _follow_ups(state["profile"]) if state["spec"] else None, notice)
        if ai_reply:
            return _reply(state, [_text(ai_reply)], _follow_ups(state["profile"]) if state["spec"] else None, notice)
        gl = _glossary_answer(t) if "question" in intents else None
        if gl:
            return _reply(state, [_text(gl)], None, notice)
        if not looks_on_topic(t):
            return _reply(state, [_text(MESSAGES["off_topic"])], None, notice)
        if state["spec"]:
            return _reply(state, [_text("Que souhaitez-vous adapter ? Par exemple la durée, le matériel, la difficulté, ou signaler un match à venir.")],
                          _follow_ups(state["profile"]), notice)

    profile = merge(old, patch)
    state["profile"] = profile

    # 3. Garde-fous : âge et douleur doivent être confirmés par l'utilisateur.
    if profile.get("adult") is False:
        state["spec"] = None
        return _reply(state, [_text(MESSAGES["minor"])])
    ps = pain_status(profile)
    if ps == "need_zone":
        state["spec"] = None
        return _reply(state, [_text(MESSAGES["pain_zone_question"])], ZONE_REPLIES)
    if ps == "insufficient":
        state["spec"] = None
        return _reply(state, [_text(MESSAGES["pain_insufficient"])])

    missing = _missing(profile)
    gates_open = profile.get("adult") is not True or profile.get("pain") is None
    if (missing and "profile" not in state["asked"] and not state["spec"]) or gates_open:
        parts = []
        recap = _recap(profile)
        if patch and recap:
            parts.append("Noté : %s." % recap)
        if ai_reply and not gates_open:
            parts.append(ai_reply)
        if missing and "profile" not in state["asked"] and not state["spec"]:
            state["asked"].append("profile")
            parts.append("Pour construire une séance adaptée, pouvez-vous préciser " + _join(missing) + " ?")
        quick = None
        if gates_open and profile.get("pain") is not None:
            # La question douleur est réglée : il ne manque que l'âge.
            parts.append(MESSAGES["age_only"])
            quick = AGE_REPLIES
        elif gates_open:
            if "gates" not in state["asked"]:
                state["asked"].append("gates")
                parts.append(MESSAGES["gate_question"])
            else:
                parts.append(MESSAGES["gate_reminder"])
            quick = GATE_REPLIES
        return _reply(state, pre + [_text(" ".join(parts))], quick, notice)

    # 4. Adapter la séance existante ou en construire une nouvelle.
    return _build_or_adapt(state, old, profile, patch, intents, t, pre, ai_reply, ai_ids, notice)


def _recap(p):
    bits = []
    if p.get("sport"):
        bits.append(p.get("other_sport") if p["sport"] == "autre" and p.get("other_sport") else label(SPORTS, p["sport"]))
    if p.get("goal"):
        bits.append(label(GOALS, p["goal"]))
    if p.get("level"):
        bits.append(label(LEVELS, p["level"]))
    if p.get("duration"):
        bits.append("%d min" % p["duration"])
    if p.get("place"):
        bits.append(label(PLACES, p["place"]))
    if p.get("equipment"):
        bits.append(", ".join(label(EQUIPMENT, e) for e in p["equipment"]))
    if p.get("fatigue_next"):
        bits.append("effort sportif prévu bientôt")
    if p.get("fatigue_recent"):
        bits.append("effort sportif récent")
    return " · ".join(bits)


def _join(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " et " + items[-1]


def _build_or_adapt(state, old, profile, patch, intents, t, pre, ai_reply, ai_ids, notice):
    effective, assumptions = _apply_assumptions(profile, state)
    spec = state.get("spec")
    seed = state.get("seed", 1)
    easier = False
    extra = []
    variant = bool(re.search(r"(autres? exercices|autre variante|change(r)? (les|d') ?exercices|nouvelle version|autre seance)", t))

    if "harder" in intents and "level" not in patch:
        idx = LEVEL_ORDER.index(effective["level"])
        if idx < 2:
            effective["level"] = profile["level"] = LEVEL_ORDER[idx + 1]
            extra.append("Niveau relevé à « %s »." % label(LEVELS, effective["level"]))
            spec = None
    if "easier" in intents:
        idx = LEVEL_ORDER.index(effective["level"])
        lowered = ("level" in patch and old.get("level")
                   and LEVEL_ORDER.index(patch["level"]) < LEVEL_ORDER.index(old["level"]))
        if lowered:
            pass  # la baisse de niveau suffit : les exercices trop difficiles seront remplacés
        elif idx > 0:
            effective["level"] = profile["level"] = LEVEL_ORDER[idx - 1]
        else:
            easier = True  # déjà débutant : variantes plus faciles et une série de moins

    rebuild_keys = {"sport", "goal", "athletics_focus", "other_sport"}
    changed = {k for k in patch if old.get(k) != patch.get(k)}
    added_equipment = "equipment" in changed and set(patch["equipment"]) - set(old.get("equipment") or []) - {"aucun"}
    longer = "duration" in changed and (patch["duration"] - (old.get("duration") or 0)) > 10
    level_up = "level" in changed and old.get("level") and LEVEL_ORDER.index(patch["level"]) > LEVEL_ORDER.index(old["level"])
    full = (not spec) or variant or bool(changed & rebuild_keys) or bool(added_equipment) or longer or level_up

    if variant and spec:
        seed += 1
        state["seed"] = seed
    if full:
        forced = ai_ids or None
        session = build_session(effective, seed=seed, forced_ids=forced, easier=easier, assumptions=assumptions,
                                extra_notes=extra)
        session["changes"] = extra  # nouvelle séance : pas de « retiré » sur des exercices jamais montrés
        intro = ai_reply or _intro(effective, adapting=bool(spec), variant=variant and bool(spec))
    else:
        session = build_session(effective, seed=seed, forced_ids=spec["ids"], easier=easier, assumptions=assumptions,
                                extra_notes=extra)
        intro = ai_reply or _adapt_intro(changed, intents, effective, session)
    state["profile"] = profile
    session["generated_by"] = "ai" if (full and ai_ids) else "rules"
    return _deliver(state, session, pre, intro, effective, notice)


def _deliver(state, session, pre, intro, effective, notice=None):
    """Affiche la séance, sauf si le tri par zone n'a pas laissé assez d'exercices."""
    if session.get("insufficient"):
        state["spec"] = None
        return _reply(state, pre + [_text(MESSAGES["pain_too_few"])], None, notice)
    state["spec"] = session["spec"]
    if session.get("caution"):
        intro = MESSAGES["pain_session_intro"]
    return _reply(state, pre + [_text(intro), {"kind": "session", "session": session}], _follow_ups(effective), notice)


def _intro(p, adapting=False, variant=False):
    if variant:
        return "Voici une variante de votre séance avec d'autres exercices, en gardant le même profil."
    if adapting:
        return "Votre profil a changé : j'ai reconstruit la séance."
    return "Voici votre séance %s (%s, %d min). Les hypothèses éventuelles sont indiquées en bas de la carte." % (
        label(GOALS, p["goal"]).lower(), label(LEVELS, p["level"]).lower(), p["duration"])


def _adapt_intro(changed, intents, p, session):
    bits = []
    if "equipment" in changed:
        bits.append("matériel mis à jour")
    if "duration" in changed:
        bits.append("durée ramenée à %d min" % p["duration"])
    if "easier" in intents:
        bits.append("variantes plus faciles")
    if changed & {"fatigue_next", "fatigue_recent"} or "fatigue" in intents:
        bits.append("charge sportive prise en compte")
    head = "J'ai adapté uniquement les parties concernées (%s)." % ", ".join(bits) if bits else "Séance mise à jour."
    if not session["changes"]:
        head += " Les exercices restent les mêmes ; seuls le volume et la durée ont été recalculés."
    return head


def handle_generate(raw_profile, raw_state) -> dict:
    """Génération depuis le formulaire : validation stricte avec messages explicites."""
    state = sanitize_state(raw_state)
    old = state["profile"]
    profile = sanitize_profile(raw_profile)
    errors = validate_form_profile(profile)
    if profile.get("adult") is False:
        state["profile"] = profile
        return _reply(state, [_text(MESSAGES["minor"])])
    ps = pain_status(profile)
    if ps == "need_zone":
        errors.append("Vous avez indiqué une gêne : choisissez la zone concernée, ou « Je ne sais pas / je préfère ne pas préciser ».")
    if errors:
        return {"errors": errors, "state": state}
    state["profile"] = profile
    state["asked"] = ["profile", "gates"]
    if ps == "insufficient":
        state["spec"] = None
        return _reply(state, [_text(MESSAGES["pain_insufficient"])])
    effective, assumptions = _apply_assumptions(profile, state)
    if state["spec"] and old.get("goal") == profile["goal"] and old.get("sport") == profile["sport"]:
        state["seed"] += 1
    session = build_session(effective, seed=state["seed"], assumptions=assumptions)
    session["changes"] = []  # nouvelle séance : rien n'a « changé » pour l'utilisateur
    session["generated_by"] = "rules"
    state["history"].append({"role": "user", "text": "[Formulaire de profil envoyé]"})
    return _deliver(state, session, [], _intro(effective), effective)


def handle_adapt(action, exercise_id, raw_state) -> dict:
    """Actions de la carte : remplacer ou retirer un exercice, en gardant le reste de la séance."""
    state = sanitize_state(raw_state)
    spec = state.get("spec")
    profile = state["profile"]
    if not spec or exercise_id not in spec["ids"] or action not in ("replace", "remove"):
        return _reply(state, [_text("Cette séance n'est plus disponible : générez une nouvelle séance.")])
    if profile.get("adult") is not True or pain_status(profile) in ("need_zone", "insufficient"):
        return _reply(state, [_text(MESSAGES["gate_reminder"])])
    effective, assumptions = _apply_assumptions(profile, state)
    old_ex = EXERCISES[exercise_id]
    ids = list(spec["ids"])
    if action == "remove":
        if len(ids) <= 2:
            return _reply(state, [_text("La séance ne compte plus que deux exercices : je les garde pour qu'elle reste cohérente. "
                                        "Vous pouvez remplacer un exercice ou raccourcir la séance.")], _follow_ups(effective))
        ids.remove(exercise_id)
        note = "« %s » retiré à votre demande ; la durée a été recalculée." % old_ex["name"]
        intro = "C'est fait : « %s » est retiré et le reste de la séance ne change pas." % old_ex["name"]
    else:
        alt, same_family = find_replacement(effective, spec["seed"], ids, exercise_id)
        if not alt:
            return _reply(state, [_text("Je n'ai pas trouvé d'autre exercice compatible avec votre matériel, votre niveau "
                                        "et vos contraintes pour remplacer « %s ». Vous pouvez le retirer ou ajouter du "
                                        "matériel dans votre profil." % old_ex["name"])], _follow_ups(effective))
        ids[ids.index(exercise_id)] = alt["id"]
        reason = ("même famille de mouvement, l'objectif de la séance est conservé" if same_family
                  else "mouvement proche, aucune autre variante n'étant disponible dans la même famille")
        note = "« %s » remplacé par « %s » (%s)." % (old_ex["name"], alt["name"], reason)
        intro = "Voici la séance avec « %s » à la place de « %s ». Le reste est inchangé." % (alt["name"], old_ex["name"])
    session = build_session(effective, seed=spec["seed"], forced_ids=ids, assumptions=assumptions, extra_notes=[note])
    session["generated_by"] = "rules"
    return _deliver(state, session, [], intro, effective)

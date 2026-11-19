"""Construction d'une séance à partir du profil, avec garde-fous de matériel, niveau et durée.

Ce moteur à règles est toujours utilisé, avec ou sans IA : le modèle d'IA peut proposer
une sélection d'exercices, mais celle-ci est revalidée ici (matériel, niveau, fatigue, durée).
"""
from __future__ import annotations

import hashlib

from .constants import GOALS, LEVELS, PLACES, SPORTS, label
from .knowledge import (
    COOLDOWN, EXERCISES, PATTERN_ORDER, WARMUP, available_equipment, equipment_label_list,
    is_feasible, needed_equipment, sources_for, sport_profile,
)
from .profile import level_rank

GOAL_RULES = {
    "force": {
        "patterns": ["squat", "push_h", "hinge", "pull_h", "push_v", "pull_v", "lunge", "core_anti_ext"],
        "sets": {1: 3, 2: 4, 3: 4}, "reps": {1: "6 à 8", 2: "5 à 6", 3: "4 à 6"},
        "rest": {1: 120, 2: 120, 3: 150}, "work": 30, "max_ex": 5,
        "effort": "Gardez 2 à 3 répétitions en réserve : la dernière répétition doit rester techniquement propre. Pas d'échec musculaire.",
    },
    "muscle": {
        "patterns": ["squat", "push_h", "pull_h", "hinge", "push_v", "pull_v", "lunge", "core_anti_ext"],
        "sets": {1: 3, 2: 3, 3: 4}, "reps": {1: "10 à 12", 2: "8 à 12", 3: "8 à 12"},
        "rest": {1: 75, 2: 90, 3: 90}, "work": 40, "max_ex": 6,
        "effort": "Terminez chaque série avec 1 à 3 répétitions encore possibles, mouvement contrôlé à la descente.",
    },
    "explosivite": {
        "patterns": ["power_lower", "squat", "hinge", "power_upper", "lunge", "core_rot", "push_h", "pull_h"],
        "sets": {1: 3, 2: 3, 3: 4}, "reps": {1: "6 à 8", 2: "5 à 6", 3: "4 à 6"},
        "rest": {1: 90, 2: 120, 3: 150}, "work": 30, "max_ex": 5,
        "effort": "Sur les exercices de puissance, chaque répétition doit être rapide et précise : arrêtez la série dès que la vitesse ou la réception se dégradent.",
    },
    "endurance": {
        "patterns": ["squat", "push_h", "pull_h", "lunge", "hinge", "core_anti_ext", "push_v", "core_rot"],
        "sets": {1: 2, 2: 3, 3: 3}, "reps": {1: "15", 2: "15 à 20", 3: "15 à 20"},
        "rest": {1: 45, 2: 45, 3: 45}, "work": 50, "max_ex": 6,
        "effort": "Rythme régulier et contrôlé ; gardez une marge, la technique ne doit pas se dégrader en fin de série.",
    },
    "forme": {
        "patterns": ["squat", "push_h", "hinge", "pull_h", "lunge", "core_anti_ext", "push_v", "core_rot"],
        "sets": {1: 2, 2: 3, 3: 3}, "reps": {1: "10 à 12", 2: "10 à 12", 3: "10 à 12"},
        "rest": {1: 60, 2: 60, 3: 60}, "work": 40, "max_ex": 6,
        "effort": "Difficulté modérée : vous devez pouvoir parler en fin de série et garder 2 à 3 répétitions en réserve.",
    },
    "perte_poids": {
        "patterns": ["squat", "push_h", "pull_h", "lunge", "hinge", "conditioning", "core_anti_ext", "core_rot"],
        "sets": {1: 2, 2: 3, 3: 3}, "reps": {1: "12", 2: "12 à 15", 3: "12 à 15"},
        "rest": {1: 45, 2: 45, 3: 40}, "work": 45, "max_ex": 6,
        "effort": "Intensité modérée et régulière ; l'objectif est de bouger avec une bonne technique, pas de s'épuiser.",
    },
}

POWER = {"power_lower", "power_upper"}
ACCESSORY = {"calf", "shoulder", "adductor"}
CORE = {"core_anti_ext", "core_rot"}
TRANSITION_SEC = 60
MAX_EXERCISES = 8


def _jitter(seed: int, ex_id: str) -> float:
    h = hashlib.sha256(("%s:%s" % (seed, ex_id)).encode()).hexdigest()
    return int(h[:6], 16) / 0xFFFFFF


class Context:
    def __init__(self, profile: dict, seed: int, easier: bool = False):
        self.profile = profile
        self.seed = seed
        self.rank = level_rank(profile)
        self.goal = profile.get("goal") or "forme"
        self.rule = GOAL_RULES[self.goal]
        self.available = available_equipment(profile.get("equipment") or [])
        self.sport = sport_profile(profile.get("sport") or "autre", profile.get("athletics_focus"))
        self.fatigue = bool(profile.get("fatigue_next") or profile.get("fatigue_recent"))
        self.fatigue_next = bool(profile.get("fatigue_next"))
        # Gêne signalée : on écarte les exercices qui sollicitent la zone (tri prudent, pas un diagnostic).
        self.pain_zones = set(profile.get("pain_zones") or []) if profile.get("pain") is True else set()
        self.caution = bool(self.pain_zones)
        self.easier = easier
        self.duration = int(profile.get("duration") or 45)

    def zone_ok(self, item: dict) -> bool:
        return not (self.pain_zones & set(item.get("zones", [])))

    def allowed(self, ex: dict) -> bool:
        if not is_feasible(ex, self.available):
            return False
        if ex["level"] > self.rank:
            return False
        if not self.zone_ok(ex):
            return False
        if (self.fatigue or self.caution) and (ex["pattern"] in POWER or ex.get("impact")):
            return False
        if self.fatigue_next and "barre" in needed_equipment(ex, self.available):
            return False  # veille de match : pas de travail lourd à la barre
        return True

    def choose(self, pattern: str, exclude: set):
        best, best_score = None, None
        for ex in EXERCISES.values():
            if ex["pattern"] != pattern or ex["id"] in exclude or not self.allowed(ex):
                continue
            uses_equipment = bool(needed_equipment(ex, self.available))
            score = 0.0
            if self.goal in ex["goals"]:
                score += 2
            if uses_equipment:
                score += 1.5 if self.goal in ("force", "muscle") else 0.6
            score -= 0.6 * (self.rank - ex["level"])
            score += 0.4 * _jitter(self.seed, ex["id"])
            if best_score is None or score > best_score:
                best, best_score = ex, score
        return best


def _priority_patterns(ctx: Context) -> list:
    goal_p = list(ctx.rule["patterns"])
    sport_p = list(ctx.sport.get("priority_patterns", []))
    out = []
    for i in range(max(len(goal_p), len(sport_p))):
        for seq in (goal_p, sport_p):
            if i < len(seq) and seq[i] not in out:
                out.append(seq[i])
    if ctx.fatigue or ctx.caution:
        out = [p for p in out if p not in POWER]
    return out


def _prescription(ex: dict, ctx: Context) -> dict:
    rule, rank, p = ctx.rule, ctx.rank, ex["pattern"]
    side = " par côté" if ex.get("unilateral") else ""
    if p in POWER:
        sets, reps, rest, work = 3, "3 à 5" + side, 90, 12
    elif ex.get("timed"):
        secs = {1: "20 à 30 s", 2: "30 à 40 s", 3: "30 à 45 s"}[rank]
        if p == "carry":
            secs = "30 à 40 s de marche"
        elif p == "conditioning":
            secs = "30 s"
        sets = 2 if rank == 1 else 3
        reps, rest, work = secs + side, 45, 35
    elif p in CORE:
        sets, reps, rest, work = (2 if rank == 1 else 3), "6 à 8" + (side or " par côté"), 45, 35
    elif p in ACCESSORY:
        sets, reps, rest, work = 2, "12 à 15" + side, 45, 35
    else:
        sets, reps, rest, work = rule["sets"][rank], rule["reps"][rank] + side, rule["rest"][rank], rule["work"]
    if ctx.fatigue:
        sets = max(2, sets - 1)
    if ctx.easier or ctx.caution:
        sets = max(2, sets - 1)
    if ctx.fatigue_next:
        # Veille de match : volume minimal et charges modérées.
        sets = 2
        if p not in CORE and p not in ACCESSORY and not ex.get("timed"):
            reps, rest = "8 à 10" + side, min(rest, 90)
    if ex.get("unilateral"):
        work = work * 2
    # Gêne signalée ou veille de match : le temps libre ne sert pas à ajouter du volume.
    max_sets = sets if (ctx.caution or ctx.fatigue_next) else sets + 1
    return {"sets": sets, "reps": reps, "rest": rest, "work": work, "min_sets": 2 if sets >= 2 else 1,
            "max_sets": max_sets}


def _exercise_seconds(item: dict) -> int:
    s = item["sets"]
    return s * item["work"] + max(0, s - 1) * item["rest"] + TRANSITION_SEC


def _warmup(ctx: Context, items: list) -> list:
    has_power = any(EXERCISES[i["id"]]["pattern"] in POWER for i in items)
    if ctx.duration <= 20:  # séance courte : échauffement essentiel uniquement
        ids = ["wu_cardio", "wu_hanches"] + (["wu_saut_progressif"] if has_power else [])
        return [WARMUP[i] for i in ids if ctx.zone_ok(WARMUP[i])]
    ids = ["wu_cardio", "wu_hanches", "wu_epaules"]
    if ctx.duration > 25:
        ids.append("wu_squat")
    if ctx.duration > 40:
        ids.append("wu_fente_rotation")
    if has_power:
        ids.append("wu_saut_progressif")
    first = min((EXERCISES[i["id"]] for i in items), key=lambda e: PATTERN_ORDER.index(e["pattern"]), default=None)
    if first and needed_equipment(first, ctx.available) and ctx.goal in ("force", "muscle", "explosivite"):
        ids.append("wu_serie_approche")
    return [WARMUP[i] for i in ids if ctx.zone_ok(WARMUP[i])]


def _cooldown(ctx: Context, items: list) -> list:
    ids = ["cd_marche", "cd_cuisses"]
    upper = any(EXERCISES[i["id"]]["pattern"] in ("push_h", "push_v", "pull_h", "pull_v", "power_upper") for i in items)
    if ctx.duration > 25:
        ids.append("cd_haut" if upper else "cd_fessiers")
    if ctx.duration > 45:
        ids.append("cd_mollets")
    return [COOLDOWN[i] for i in ids if ctx.zone_ok(COOLDOWN[i])]


def _minutes(entries: list) -> float:
    return sum(e["minutes"] for e in entries)


def _fit(items: list, importance: list, ctx: Context, reserve: list = None) -> list:
    """Ajuste séries et nombre d'exercices pour respecter la durée disponible."""
    notes = []
    min_count = 2 if ctx.duration <= 20 else 3

    def total():
        wu = min(_minutes(_warmup(ctx, items)), 10)
        cd = min(_minutes(_cooldown(ctx, items)), 6)
        return wu + cd + sum(_exercise_seconds(i) for i in items) / 60.0

    by_importance = lambda: sorted(items, key=lambda i: importance.index(i["id"]) if i["id"] in importance else 99)
    guard = 0
    while total() > ctx.duration and guard < 60:
        guard += 1
        ordered = list(reversed(by_importance()))
        reducible = [i for i in ordered if i["sets"] > max(i["min_sets"], i["base_sets"] - 1)]
        if reducible:
            reducible[0]["sets"] -= 1
            continue
        # Séance courte : on raccourcit d'abord les repos (sauf force et puissance) avant de retirer des exercices.
        short_rest = [i for i in ordered if ctx.duration < 35 and ctx.goal != "force" and i["rest"] > 60
                      and EXERCISES[i["id"]]["pattern"] not in POWER]
        if short_rest:
            for i in short_rest:
                i["rest"] = max(60, i["rest"] - 30)
            continue
        if len(items) > min_count:
            dropped = ordered[0]
            items.remove(dropped)
            notes.append("« %s » retiré pour tenir dans %d min." % (EXERCISES[dropped["id"]]["name"], ctx.duration))
            continue
        reducible = [i for i in ordered if i["sets"] > i["min_sets"]]
        if reducible:
            reducible[0]["sets"] -= 1
            continue
        floor = 90 if ctx.goal == "force" else 45
        restable = [i for i in ordered if i["rest"] > floor]
        if restable:
            for i in restable:
                i["rest"] = max(floor, i["rest"] - 15)
            continue
        break
    guard = 0
    reserve = list(reserve or [])
    while total() < ctx.duration - 8 and guard < 30:
        guard += 1
        growable = [i for i in by_importance() if i["sets"] < i["max_sets"]]
        if not growable and reserve and len(items) < MAX_EXERCISES and not (ctx.caution or ctx.fatigue_next):
            # Beaucoup de temps libre : on ajoute un exercice de réserve s'il tient dans la durée.
            extra = reserve.pop(0)
            items.append(extra)
            importance.append(extra["id"])
            if total() > ctx.duration:
                items.remove(extra)
                importance.remove(extra["id"])
            continue
        if not growable:
            break
        growable[0]["sets"] += 1
        if total() > ctx.duration:
            growable[0]["sets"] -= 1
            break
    return notes


def _rest_label(sec: int) -> str:
    if sec >= 60 and sec % 60 == 0:
        return "%d min" % (sec // 60)
    if sec > 60:
        return "%d min %02d" % (sec // 60, sec % 60)
    return "%d s" % sec


def _resolve_forced(forced_ids: list, ctx: Context, changes: list):
    """Garde les exercices encore valides et remplace uniquement ceux qui ne le sont plus."""
    chosen, used = [], set()
    for ex_id in forced_ids:
        ex = EXERCISES.get(ex_id)
        if not ex or ex_id in used:
            continue
        if (ctx.fatigue or ctx.caution) and (ex["pattern"] in POWER or ex.get("impact")):
            reason = "gêne signalée" if ctx.caution else "fatigue sportive"
            changes.append("« %s » retiré : pas de sauts ni d'exercice de puissance (%s)." % (ex["name"], reason))
            continue
        candidate = ex
        swap_reason = None
        if not is_feasible(ex, ctx.available):
            swap_reason = "matériel"
        elif ex["level"] > ctx.rank:
            swap_reason = "niveau"
        elif not ctx.allowed(ex) and not (ex["pattern"] in POWER or ex.get("impact")):
            swap_reason = "matériel"  # zone signalée ou veille de match : même famille, exercice compatible
        elif ctx.easier and ex.get("easier"):
            swap_reason = "variante plus facile"
        if swap_reason:
            candidate = None
            refs = [EXERCISES.get(r) for r in (ex.get("easier"), ex.get("less_equipment")) if r]
            if swap_reason == "matériel":
                # Matériel manquant : meilleur exercice de la même famille avec le matériel restant.
                candidate = ctx.choose(ex["pattern"], used)
            for alt in refs:
                if candidate is None and alt["id"] not in used and ctx.allowed(alt):
                    candidate = alt
            if candidate is None and swap_reason == "niveau":
                candidate = ctx.choose(ex["pattern"], used)
            if candidate is None and swap_reason == "variante plus facile":
                candidate = ex
            if candidate is None:
                why = ("il sollicite la zone signalée" if not ctx.zone_ok(ex)
                       else "aucune alternative compatible avec votre matériel et vos contraintes")
                changes.append("« %s » retiré : %s." % (ex["name"], why))
                continue
            if candidate["id"] != ex["id"]:
                changes.append("« %s » → « %s »." % (ex["name"], candidate["name"]))
        chosen.append(candidate)
        used.add(candidate["id"])
    return chosen


def build_session(profile: dict, seed: int = 1, forced_ids: list = None, easier: bool = False,
                  assumptions: list = None, extra_notes: list = None) -> dict:
    ctx = Context(profile, seed, easier=easier)
    changes = list(extra_notes or [])

    if forced_ids:
        chosen = _resolve_forced(forced_ids, ctx, changes)
        # Un exercice retiré sans remplaçant direct est compensé par une famille de mouvement non couverte.
        missing = len([i for i in forced_ids if i in EXERCISES]) - len(chosen)
        if missing > 0:
            used = {e["id"] for e in chosen}
            covered = {e["pattern"] for e in chosen}
            for pattern in _priority_patterns(ctx):
                if missing <= 0:
                    break
                if pattern in covered:
                    continue
                ex = ctx.choose(pattern, used)
                if ex:
                    chosen.append(ex)
                    used.add(ex["id"])
                    covered.add(pattern)
                    changes.append("« %s » ajouté pour compléter la séance." % ex["name"])
                    missing -= 1
        importance = [e["id"] for e in chosen]
    reserve_ex = []
    if not forced_ids:
        chosen, used = [], set()
        limit = ctx.rule["max_ex"] + (1 if ctx.sport.get("priority_patterns") else 0)
        patterns = _priority_patterns(ctx)
        # Réserve : familles restantes, plus des accessoires utiles, pour les séances longues.
        for pattern in patterns + [p for p in ("calf", "shoulder", "core_rot", "core_anti_ext", "carry") if p not in patterns]:
            ex = ctx.choose(pattern, used)
            if not ex:
                continue
            (chosen if len(chosen) < limit else reserve_ex).append(ex)
            used.add(ex["id"])
        importance = [e["id"] for e in chosen]

    def to_item(ex):
        pres = _prescription(ex, ctx)
        return {"id": ex["id"], "sets": pres["sets"], "base_sets": pres["sets"], "reps": pres["reps"],
                "rest": pres["rest"], "work": pres["work"], "min_sets": pres["min_sets"], "max_sets": pres["max_sets"]}

    items = [to_item(ex) for ex in chosen]
    changes += _fit(items, importance, ctx, [to_item(ex) for ex in reserve_ex])
    items.sort(key=lambda i: PATTERN_ORDER.index(EXERCISES[i["id"]]["pattern"]))
    return _render(ctx, items, importance, changes, assumptions or [])


GOAL_PHRASES = {
    "force": "développer votre force",
    "muscle": "favoriser la prise de muscle",
    "explosivite": "travailler votre explosivité",
    "endurance": "améliorer votre endurance musculaire",
    "forme": "reprendre une activité physique équilibrée",
    "perte_poids": "bouger régulièrement, en accompagnement de votre objectif de perte de poids",
}


def zone_labels(zones) -> str:
    from .constants import PAIN_ZONES
    names = [label(PAIN_ZONES, z).lower() for z in sorted(zones)]
    return " et ".join(names)


def _no_equipment_variant(ex: dict, need: list, ctx: Context):
    """Variante sans le matériel requis, compatible avec les zones et le niveau."""
    if not need:
        return None
    alt = EXERCISES.get(ex.get("less_equipment") or "")
    bodyweight = {"poids_corps"}
    if not (alt and is_feasible(alt, bodyweight) and alt["level"] <= ctx.rank and ctx.zone_ok(alt)
            and not ((ctx.fatigue or ctx.caution) and (alt["pattern"] in POWER or alt.get("impact")))):
        bw = Context(dict(ctx.profile, equipment=["aucun"]), ctx.seed)
        alt = bw.choose(ex["pattern"], {ex["id"]})
    if not alt:
        return {"name": None, "cue": "Pas de variante sans matériel dans le catalogue : remplacez l'exercice ou retirez-le."}
    return {"name": alt["name"], "cue": alt["cue"]}


def _render(ctx: Context, items: list, importance: list, changes: list, assumptions: list) -> dict:
    p = ctx.profile
    warm = _warmup(ctx, items)
    cool = _cooldown(ctx, items)
    warm_min = min(_minutes(warm), 10)
    cool_min = min(_minutes(cool), 6)
    exercises = []
    used_barre = has_impact = has_power = False
    for it in items:
        ex = EXERCISES[it["id"]]
        need = needed_equipment(ex, ctx.available)
        used_barre = used_barre or "barre" in need
        has_impact = has_impact or bool(ex.get("impact"))
        has_power = has_power or ex["pattern"] in POWER
        easier = EXERCISES.get(ex.get("easier") or "")
        if easier and not ctx.allowed(easier):
            easier = None
        exercises.append({
            "id": ex["id"], "name": ex["name"], "original_name": ex["original_name"],
            "sets": it["sets"], "reps": it["reps"], "is_timed": bool(ex.get("timed")),
            "rest_sec": it["rest"], "rest_label": _rest_label(it["rest"]),
            "equipment": equipment_label_list(need), "needs_equipment": bool(need),
            "muscles": ex["muscles"], "cue": ex["cue"], "errors": ex["errors"],
            "easier": {"name": easier["name"], "cue": easier["cue"]} if easier else
                      {"name": "Même exercice simplifié", "cue": "Réduisez l'amplitude, la charge ou le nombre de répétitions."},
            "without_equipment": _no_equipment_variant(ex, need, ctx),
            "minutes": round(_exercise_seconds(it) / 60.0, 1),
        })
    main_min = sum(_exercise_seconds(i) for i in items) / 60.0
    total = int(round(warm_min + main_min + cool_min))

    sport_label = label(SPORTS, p.get("sport") or "autre")
    if p.get("sport") == "autre":
        sport_label = ("%s (sport non listé)" % p["other_sport"]) if p.get("other_sport") else "Préparation générale"
    if p.get("sport") == "athletisme" and p.get("athletics_focus") == "sprint_sauts":
        sport_label = "Athlétisme — sprint / sauts"

    # --- Textes de liaison : la séance se lit comme un ensemble, pas comme une liste de fragments.
    level_name = label(LEVELS, p.get("level") or "debutant").lower()
    intro = ("Cette séance d'environ %d minutes vise à %s, pour un niveau %s. Elle s'enchaîne en trois temps : "
             "un échauffement progressif, un corps de séance de %d exercices, puis un retour au calme."
             % (total, GOAL_PHRASES[ctx.goal], level_name, len(exercises)))
    if ctx.sport.get("priority_patterns"):
        q = ctx.sport["qualities"]
        intro += (" Pour le profil « %s », les exercices tiennent compte de qualités souvent utiles dans ce sport, "
                  "comme « %s » ou « %s » ; cette orientation reste indicative." % (ctx.sport["name"], q[0], q[1]))
    else:
        intro += " Sans profil sportif spécifique, la séance reste générale et équilibrée."
    if ctx.fatigue_next:
        intro += (" Comme un match ou un entraînement approche, elle reste volontairement légère : pas de sauts, "
                  "pas de travail lourd à la barre, deux séries par exercice et des charges modérées.")
    elif p.get("fatigue_recent"):
        intro += " Comme vous sortez d'un effort sportif récent, le volume est réduit et les sauts sont retirés."

    warm_intro = ("Commencez par environ %d minutes d'échauffement pour élever progressivement la température "
                  "du corps et préparer les articulations aux mouvements qui suivent." % int(round(warm_min)))
    order = ("les exercices de puissance viennent en premier, quand vous êtes encore frais, puis les mouvements "
             "de force et enfin le gainage" if has_power else
             "les mouvements qui sollicitent le plus de muscles viennent en premier, le gainage et les exercices "
             "plus ciblés à la fin")
    main_intro = ("Passez ensuite au corps de séance, dans l'ordre proposé : %s. Réalisez toutes les séries d'un "
                  "exercice en respectant le repos indiqué, puis passez au suivant." % order)
    cool_intro = ("Terminez par quelques minutes au calme pour faire redescendre le rythme cardiaque, avec des "
                  "étirements doux, sans forcer.")

    if ctx.fatigue_next:
        effort = "Intensité modérée : gardez 3 à 4 répétitions en réserve et terminez la séance en vous sentant frais."
    elif ctx.caution:
        effort = "Intensité légère à modérée : mouvements lents et contrôlés, arrêtez l'exercice dès qu'une gêne apparaît."
    else:
        effort = ctx.rule["effort"]

    safety = ["Arrêtez un exercice s'il provoque une douleur inhabituelle, vive ou articulaire.",
              "Choisissez des charges qui vous permettent de garder une technique propre sur toutes les répétitions."]
    if ctx.rank == 1:
        safety.append("Si vous débutez, faire vérifier votre technique par un professionnel qualifié est une bonne idée.")
    if has_impact:
        safety.append("Pour les sauts, recherchez des réceptions souples et silencieuses, genoux dans l'axe des pieds, et stoppez la série si la réception se dégrade.")
    if used_barre:
        safety.append("À la barre, utilisez un rack avec sécurités réglées ou un partenaire de parade.")
    if ctx.goal == "perte_poids":
        safety.append("La musculation peut accompagner un objectif de perte de poids, sans garantie de résultat ni perte de graisse ciblée sur une zone ; pour l'alimentation, adressez-vous à un professionnel de santé.")
    if p.get("fatigue_recent") and not ctx.fatigue_next:
        safety.append("Si vous vous sentez encore fatigué, une séance plus légère ou du repos est préférable.")

    caution = None
    if ctx.caution:
        caution = {
            "title": "Gêne signalée : %s" % zone_labels(ctx.pain_zones),
            "text": ("HALTUP a écarté les exercices qui sollicitent principalement cette zone, ainsi que les sauts, "
                     "et a réduit le volume. Ce tri reste approximatif : il ne remplace pas un avis et ne garantit pas "
                     "l'absence de risque. Avant de reprendre ou de modifier votre entraînement, demandez conseil à un "
                     "professionnel de santé ou à un entraîneur qualifié, et arrêtez tout exercice qui réveille la gêne."),
        }

    note_dur = None
    if total > ctx.duration:
        note_dur = "Même simplifiée, cette séance demande environ %d min : prévoyez un peu plus de temps ou retirez un exercice." % total
    elif total < ctx.duration - 8:
        note_dur = "Séance estimée à %d min : le temps restant peut servir à récupérer plus longtemps entre les séries." % total

    return {
        "summary": {
            "sport": sport_label,
            "goal": label(GOALS, ctx.goal),
            "level": label(LEVELS, p.get("level") or "debutant"),
            "place": label(PLACES, p.get("place"), "Lieu non précisé"),
            "equipment": equipment_label_list(sorted(ctx.available - {"poids_corps"})),
            "duration_requested": ctx.duration,
            "duration_estimated": total,
            "duration_note": note_dur,
        },
        "intro": intro,
        "caution": caution,
        "insufficient": bool(ctx.caution and len(exercises) < 3),
        "warmup": {"minutes": int(round(warm_min)), "intro": warm_intro,
                   "items": [{"name": w["name"], "detail": w["detail"]} for w in warm],
                   "tip": "Augmentez progressivement l'amplitude et le rythme, sans vous fatiguer."},
        "main": {"minutes": int(round(main_min)), "intro": main_intro, "effort": effort, "exercises": exercises,
                 "timing_rule": "La durée est estimée à partir du temps d'effort, des repos entre les séries et d'environ une minute de transition par exercice."},
        "cooldown": {"minutes": int(round(cool_min)), "intro": cool_intro,
                     "items": [{"name": c["name"], "detail": c["detail"]} for c in cool]},
        "safety": safety,
        "assumptions": assumptions,
        "changes": changes,
        "sport_note": {"name": ctx.sport["name"], "specifics": ctx.sport["specifics"],
                       "confidence": ctx.sport["confidence"], "limits": ctx.sport["limits"]},
        "sources": sources_for(ctx.sport),
        "spec": {"ids": importance and [i["id"] for i in sorted(items, key=lambda i: importance.index(i["id"]) if i["id"] in importance else 99)] or [],
                 "seed": ctx.seed},
    }


RELATED_PATTERNS = {
    "squat": ["lunge"], "lunge": ["squat"], "hinge": ["lunge"], "push_h": ["push_v"], "push_v": ["push_h"],
    "pull_h": ["pull_v", "shoulder"], "pull_v": ["pull_h"], "core_anti_ext": ["core_rot"], "core_rot": ["core_anti_ext"],
    "power_lower": ["power_upper"], "power_upper": ["power_lower"], "shoulder": ["pull_h"], "adductor": ["lunge"],
    "carry": ["core_anti_ext"], "conditioning": ["core_anti_ext"], "calf": ["lunge"],
}


def find_replacement(profile: dict, seed: int, current_ids: list, ex_id: str, tried: list = None):
    """Exercice de remplacement : même famille de mouvement d'abord (garde la logique de la séance),
    puis une famille proche, toujours avec le matériel déjà indiqué."""
    ctx = Context(profile, seed)
    ex = EXERCISES[ex_id]
    exclude = set(current_ids) | set(tried or [])
    for pattern in [ex["pattern"]] + RELATED_PATTERNS.get(ex["pattern"], []):
        alt = ctx.choose(pattern, exclude)
        if alt:
            return alt, pattern == ex["pattern"]
    return None, False


def candidate_exercises(profile: dict) -> list:
    """Exercices autorisés pour ce profil (proposés au modèle d'IA, qui ne peut choisir que parmi eux)."""
    ctx = Context(profile, 1)
    return [{"id": ex["id"], "name": ex["name"], "pattern": ex["pattern"], "level": ex["level"]}
            for ex in EXERCISES.values() if ctx.allowed(ex)]

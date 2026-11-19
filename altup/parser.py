"""Analyse du texte libre en français (mode démonstration, sans IA).

Repère par mots-clés les informations du profil et les demandes d'adaptation.
Volontairement simple et prévisible : ce n'est pas une compréhension complète du langage.
"""
from __future__ import annotations

import re
import unicodedata


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("’", "'")
    return " ".join(text.split())


def _has(text, *patterns):
    return any(re.search(p, text) for p in patterns)


SPORT_PATTERNS = [
    ("football", [r"\bfoot(ball)?\b", r"\bsoccer\b", r"\bfutsal\b"]),
    ("basketball", [r"\bbasket(ball)?\b"]),
    ("rugby", [r"\brugby\b"]),
    ("athletisme", [r"\bathle(tisme)?\b", r"\bsprint", r"\bsprinteur", r"\bsaut en (longueur|hauteur)\b", r"\btriple saut\b"]),
    ("volleyball", [r"\bvolley(ball)?\b"]),
    ("handball", [r"\bhand(ball)?\b"]),
    ("tennis", [r"\btennis\b(?! de table)"]),
    ("natation", [r"\bnatation\b", r"\bnage[rs]?\b", r"\bnageu(r|se)\b", r"\bpiscine\b"]),
    ("boxe", [r"\bboxe\b", r"\bboxeu(r|se)\b", r"\bboxing\b"]),
    ("cyclisme", [r"\bcyclisme\b", r"\bvelo\b", r"\bvtt\b", r"\bcycliste\b"]),
]

OTHER_SPORTS = [
    "escalade", "judo", "karate", "ski", "course a pied", "running", "trail", "golf", "danse",
    "badminton", "tennis de table", "ping-pong", "crossfit", "aviron", "surf", "equitation",
    "lutte", "mma", "taekwondo", "hockey", "baseball", "padel", "gymnastique", "triathlon",
]

GOAL_PATTERNS = [
    ("perte_poids", [r"perte de poids", r"perdre (du|des|quelques)? ?(poids|kilos|kg)", r"\bmaigrir\b", r"\bmincir\b", r"\bseche\b"]),
    ("explosivite", [r"explosi", r"\bdetente\b", r"\bpuissance\b", r"\bvitesse\b", r"\bsauter plus haut\b"]),
    ("muscle", [r"prise de (muscle|masse)", r"prendre du muscle", r"\b(objectif|but) ?:? ?muscle\b", r",\s*muscle\b", r"\bmuscler\b", r"\bhypertroph", r"\bmasse musculaire\b", r"\bgrossir\b"]),
    ("endurance", [r"endurance", r"\btenir plus longtemps\b"]),
    ("force", [r"\bforce\b", r"\bplus fort\b", r"\bdevenir fort\b"]),
    ("forme", [r"remise en forme", r"\bforme generale\b", r"\bme remettre\b", r"\bentretien\b", r"\bsante generale\b", r"\bgarder la forme\b"]),
]

LEVEL_PATTERNS = [
    ("debutant", [r"\bdebut(e|ant|ante|er)?\b", r"\bnovice\b", r"\bjamais fait\b", r"\bje commence\b", r"\breprise\b", r"\breprends?\b"]),
    ("intermediaire", [r"\bintermediaire\b", r"\bregulierement\b", r"\bquelques (mois|annees)\b"]),
    ("avance", [r"\bavance\b", r"\bconfirme\b", r"\bexperimente\b", r"\bdepuis des annees\b"]),
]

PLACE_PATTERNS = [
    ("maison", [r"\bmaison\b", r"\bdomicile\b", r"\bchez moi\b", r"\bappartement\b", r"\bappart\b"]),
    ("salle", [r"\bsalle\b", r"\bgym\b", r"\bfitness\b", r"\bclub de sport\b"]),
    ("exterieur", [r"\bdehors\b", r"\bexterieur\b", r"\bparc\b", r"\bplein air\b"]),
]

EQUIPMENT_PATTERNS = [
    ("halteres", r"halteres?"),
    ("barre", r"barres?(?! de traction)(?! fixe)"),
    ("banc", r"bancs?"),
    ("machines", r"machines?"),
    ("elastiques", r"(elastiques?|bandes? elastiques?)"),
    ("kettlebell", r"(kettlebells?|kettle)"),
    ("medecine_ball", r"(ballon medicinal|ballons medicinaux|medecine ?ball|med ?ball|medicine ?ball)"),
]

NEGATION_PREFIX = r"(pas de|pas d'|sans|plus de|aucun|aucune|n'ai pas de|n'ai plus de|je n'ai pas de)\s+(\w+\s+){0,2}?"


def _detect_duration(t: str):
    m = re.search(r"\b(\d)\s*h\s*(\d{1,2})?\b", t)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2) or 0)
    m = re.search(r"\b(\d{1,3})\s*(min|mn|minutes?)\b", t)
    if m:
        return int(m.group(1))
    if re.search(r"\b(une|1) heure et demie\b", t):
        return 90
    if re.search(r"\bdemi[- ]heure\b", t):
        return 30
    if re.search(r"\b(une|1) heure\b", t):
        return 60
    m = re.search(r"\b(reduis|reduire|raccourcis|passe|fais)\b\D{0,20}?\b(\d{2,3})\b(?!\s*ans)", t)
    if m and 10 <= int(m.group(2)) <= 120:
        return int(m.group(2))
    return None


def parse_message(message: str) -> dict:
    """Retourne {'patch': {...}, 'remove_equipment': [...], 'add_equipment': [...], 'intents': set()}."""
    t = normalize(message)
    patch = {}
    intents = set()
    add_eq, remove_eq = [], []

    # Âge
    m = re.search(r"(?:^|j'ai|\bai|\bage de|\bagee? de|\bage|[,.;])\s*(\d{1,2})\s*ans\b(?!\s*(de|d'))", t)
    if m:
        patch["adult"] = int(m.group(1)) >= 18
        if int(m.group(1)) < 18:
            intents.add("minor")
    if _has(t, r"\bmineure?\b", r"\bcollegien", r"\blyceen"):
        patch["adult"] = False
        intents.add("minor")
    if _has(t, r"\bmajeure?\b", r"18 ans ou plus", r"plus de 18 ans", r"\bje suis adulte\b"):
        patch["adult"] = True

    # Douleur / blessure (la négation est testée d'abord)
    no_pain = _has(t, r"\b(pas|aucune?|sans|ni)\s+(de\s+|d')?(douleur|blessure|bobo|probleme)", r"\bpas blesse", r"\bje ne suis pas blesse")
    pain = _has(t, r"\bdouleurs?\b", r"\bj'ai mal\b", r"\bmal (au|a la|aux|a l')\b", r"\bblesse", r"\bblessure",
                r"\btendinite", r"\bentorse", r"\bfracture", r"\bhernie", r"\bcontre-indication", r"\boper(e|ation)\b",
                r"\bdechirure", r"\bsciatique", r"\blumbago", r"\bkine\b.*\b(reeduc|soign)")
    if no_pain:
        patch["pain"] = False
    elif pain:
        patch["pain"] = True
        intents.add("pain")
    if not no_pain and re.search(RED_FLAGS, t):
        intents.add("red_flag")
    zones = detect_zones(t)
    if re.search(r"(ne sais pas|ne sait pas|prefere ne pas|plusieurs zones|partout|un peu partout|pas preciser)", t):
        intents.add("zone_unknown")

    # Sport
    for sport_id, pats in SPORT_PATTERNS:
        if _has(t, *pats):
            patch["sport"] = sport_id
            break
    if "sport" not in patch:
        for other in OTHER_SPORTS:
            if re.search(r"\b" + re.escape(other) + r"\b", t):
                patch["sport"] = "autre"
                patch["other_sport"] = other.capitalize()
                break
    if patch.get("sport") == "athletisme" or _has(t, r"\bsprint", r"\bsauts?\b.*\bathle"):
        if _has(t, r"\bsprint", r"\bsaut", r"\bhaies\b"):
            patch["athletics_focus"] = "sprint_sauts"

    # Objectif
    for goal_id, pats in GOAL_PATTERNS:
        if _has(t, *pats):
            patch["goal"] = goal_id
            break

    # Niveau
    if _has(t, r"\bplus facile\b", r"\btrop (dur|difficile)\b", r"\bvariante facile\b", r"\bplus simple\b", r"\bmoins dur"):
        intents.add("easier")
    if _has(t, r"\bplus (dur|difficile|intense)\b", r"\btrop facile\b"):
        intents.add("harder")
    for level_id, pats in LEVEL_PATTERNS:
        if _has(t, *pats):
            patch["level"] = level_id
            break

    # Durée
    d = _detect_duration(t)
    if d:
        patch["duration"] = d
    if _has(t, r"\bplus court", r"\braccourci", r"\breduis", r"\bmoins long", r"\bmanque de temps"):
        intents.add("shorter")

    # Lieu
    for place_id, pats in PLACE_PATTERNS:
        if _has(t, *pats):
            patch["place"] = place_id
            break

    # Matériel
    if _has(t, r"\b(sans|aucun|pas de|zero) (materiel|equipement)\b", r"\bpoids du corps\b", r"\bje n'ai rien\b"):
        add_eq.append("aucun")
    for eq_id, pat in EQUIPMENT_PATTERNS:
        if re.search(NEGATION_PREFIX + r"\b" + pat + r"\b", t):
            remove_eq.append(eq_id)
        elif re.search(r"\b" + pat + r"\b", t):
            add_eq.append(eq_id)

    # Charge sportive récente / à venir
    future = r"(demain|ce soir|apres-demain|dans (24|48) ?h|bientot|ce week-end|samedi|dimanche)"
    past = r"(hier|ce matin|cet apres-midi|aujourd'hui|avant-hier)"
    event = r"(match|entrainement|entraine|competition|course|tournoi|seance de \w+)"
    if re.search(event + r".{0,25}" + future, t) or re.search(future + r".{0,25}" + event, t):
        patch["fatigue_next"] = True
        intents.add("fatigue")
    if re.search(event + r".{0,25}" + past, t) or re.search(past + r".{0,25}" + event, t):
        patch["fatigue_recent"] = True
        intents.add("fatigue")
    if _has(t, r"\bpas de match\b", r"\bpas d'entrainement\b", r"\brepos (demain|ce week-end)\b"):
        patch["fatigue_next"] = False
        patch["fatigue_recent"] = False

    # Sujets à cadrer
    if _has(t, r"\bregime\b", r"\bcalories?\b", r"\bproteines?\b", r"\bcomplements?\b", r"\bnutrition\b",
            r"\bmanger\b", r"\bjeune intermittent\b", r"\bmacro"):
        intents.add("nutrition")
    if _has(t, r"\b1 ?rm\b", r"\bmax(imum)? (au|en) ", r"\bcharge maximale\b", r"\bjusqu'a l'echec\b",
            r"\bsteroide", r"\banabolis", r"\bdopage\b", r"\bperdre \d+ ?(kg|kilos) en\b"):
        intents.add("extreme")
    if _has(t, r"\b(recommence|recommencer|nouvelle seance|autre seance|reset)\b"):
        intents.add("restart")
    if re.search(r"\b(c'est quoi|qu'est-ce que|que veut dire|definition|signifie)\b", t):
        intents.add("question")

    return {"patch": patch, "add_equipment": add_eq, "remove_equipment": remove_eq,
            "intents": intents, "zones": zones, "normalized": t}


# Signes qui justifient un avis professionnel avant toute séance (aucune séance n'est alors proposée).
RED_FLAGS = (
    r"(gonfl|enfl|hematome|craquement|engourdi|fourmill|perte de force|poitrine|thorac|malaise|evanoui|"
    r"essouffl|vertige|fievre|ne (peux|peut) (plus |pas )*(marcher|poser|bouger|plier)|"
    r"douleur (tres |trop )?(intense|vive|insupportable)|chute|accident|fracture|opere|operation|entorse|"
    r"dechirure|luxation|sciatique|hernie)"
)

ZONE_PATTERNS = [
    ("epaule", r"\bepaules?\b"),
    ("coude_poignet", r"\b(coudes?|poignets?|mains?|doigts?|avant-bras)\b"),
    ("cou_haut_dos", r"\b(cou|nuque|cervicales?|haut du dos|trapezes?)\b"),
    ("dos_bas", r"\b(bas du dos|lombaires?|lumbago|reins)\b"),
    ("hanche", r"\b(hanches?|aine|adducteurs?)\b"),
    ("genou", r"\b(genoux?|genou|rotules?|menisques?)\b"),
    ("cheville_pied", r"\b(chevilles?|pieds?|talons?|achille|voute plantaire)\b"),
]


def detect_zones(t: str) -> list:
    """Région du corps mentionnée (aucun diagnostic, aucune interprétation médicale)."""
    zones = [z for z, pat in ZONE_PATTERNS if re.search(pat, t)]
    # « mal au dos » sans précision : on retient le bas du dos, la zone la plus souvent concernée.
    if re.search(r"\bdos\b", t) and "cou_haut_dos" not in zones and "dos_bas" not in zones:
        zones.append("dos_bas")
    return sorted(set(zones))


FITNESS_WORDS = (
    r"\b(seance|muscu|musculation|exercice|entrainement|entrainer|sport|serie|repetition|repos|"
    r"echauffement|etirement|gainage|squat|pompe|abdo|jambes?|bras|dos|epaules?|cuisses?|fessiers?|"
    r"programme|h?altup|salut|bonjour|bonsoir|hello|merci|ok|d'accord|oui|non|coach|forme|physique)\b"
)


def looks_on_topic(normalized: str) -> bool:
    return bool(re.search(FITNESS_WORDS, normalized))

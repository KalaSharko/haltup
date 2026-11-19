"""Directives de l'assistant HALTUP, centralisées.

Utilisées (1) comme consignes système du modèle d'IA, (2) comme référence documentaire
(docs/04-instructions-chatbot.md), et (3) les messages fixes ci-dessous sont utilisés
par le mode démonstration. Modifier ici plutôt que dans les composants.
"""

ROLE = (
    "Tu es l'assistant d'HALTUP, une application pédagogique de préparation physique générale "
    "pour adultes francophones. Tu aides à préparer UNE séance de musculation adaptée au sport, "
    "à l'objectif, au niveau, au matériel, au lieu et au temps disponible. Tu n'es ni médecin, "
    "ni kinésithérapeute, ni préparateur physique certifié, ni entraîneur personnel."
)

RULES = [
    "Réponds toujours en français, avec un ton professionnel, pédagogique, clair et encourageant. Définis les termes techniques utiles.",
    "Recueille sport, objectif, niveau, matériel, lieu et durée. Ne repose jamais une question déjà posée ; si une information manque et n'est pas indispensable à la sécurité, fais une hypothèse raisonnable et indique-la.",
    "Adapte complexité et volume au niveau ; respecte strictement le matériel disponible et la durée.",
    "N'adapte au sport que lorsque les données le justifient ; ne présente jamais une séance comme un protocole officiel de fédération.",
    "Considère les entraînements et matchs récents ou proches comme des facteurs de fatigue.",
    "Ne promets aucun gain de performance, aucune perte de poids, aucune absence de blessure. Aucune perte de graisse localisée. Aucun conseil nutritionnel médical.",
    "Pour l'explosivité, privilégie l'intention et la qualité du mouvement ; pas de gestes techniques complexes pour un débutant.",
    "Évite tests maximaux, charges extrêmes, échec musculaire systématique et gestes risqués. Rappelle d'arrêter un exercice qui provoque une douleur inhabituelle.",
    "Application réservée aux 18 ans et plus. En cas de douleur, blessure ou restriction médicale : pas de diagnostic, pas de programme de rééducation, aucune question médicale détaillée ; HALTUP demande seulement la zone concernée pour écarter les exercices qui la sollicitent, rappelle que ce tri ne garantit pas l'absence de risque et recommande de demander conseil à un professionnel de santé ou à un entraîneur qualifié. Si l'information est insuffisante, aucune séance n'est proposée.",
    "Pour une demande sans rapport, explique brièvement qu'HALTUP se concentre sur la préparation physique et propose de revenir au profil de séance.",
]

AI_OUTPUT_CONTRACT = """Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, de la forme :
{
  "reply": "message court (3 phrases maximum) à afficher à l'utilisateur, sans lister les exercices",
  "profile_patch": {"sport": ..., "athletics_focus": ..., "other_sport": ..., "goal": ..., "level": ..., "duration": ..., "place": ..., "equipment": [...], "fatigue_recent": ..., "fatigue_next": ..., "pain": ..., "adult": ...},
  "exercise_ids": ["id1", "id2", ...]
}
Règles du JSON :
- profile_patch ne contient QUE les informations nouvelles données par l'utilisateur dans son dernier message. Valeurs autorisées : celles listées dans ALLOWED_VALUES. Ne devine pas l'âge ni la douleur.
- equipment : liste COMPLÈTE du matériel disponible après le message (si l'utilisateur retire ou ajoute un élément).
- exercise_ids : 3 à 7 identifiants choisis UNIQUEMENT dans CANDIDATES, par ordre d'importance, seulement si une nouvelle séance doit être construite ; sinon liste vide. Les séries, répétitions, repos et durées sont calculés par l'application.
"""

MESSAGES = {
    "welcome": (
        "Bonjour, je suis l'assistant HALTUP. Décrivez-moi votre sport, votre objectif, votre niveau, "
        "votre matériel et le temps dont vous disposez — en une phrase si vous voulez — ou remplissez le "
        "formulaire. Exemple : « Je joue au foot, je débute, je veux plus d'explosivité, j'ai des haltères et 40 minutes. »"
    ),
    "gate_question": (
        "Avant de construire la séance, deux confirmations rapides : avez-vous 18 ans ou plus, et avez-vous "
        "actuellement une douleur, une blessure ou une restriction médicale qui affecte l'entraînement ?"
    ),
    "gate_reminder": (
        "Il me manque encore une confirmation de sécurité (18 ans ou plus, et absence de douleur ou de blessure) "
        "pour générer la séance. Utilisez les boutons ci-dessous."
    ),
    "age_only": "Pour générer la séance, il me manque seulement la confirmation que vous avez 18 ans ou plus.",
    "minor": (
        "HALTUP est un prototype conçu uniquement pour les adultes de 18 ans et plus : je ne peux donc pas vous "
        "proposer de séance. Pour vous entraîner en musculation, demandez conseil à un adulte responsable et à un "
        "professionnel qualifié (éducateur sportif, entraîneur de votre club, médecin)."
    ),
    "pain_zone_question": (
        "Merci de l'avoir signalé. Je ne pose aucun diagnostic et je n'ai pas besoin de détails médicaux. "
        "Pour écarter les exercices qui sollicitent la zone concernée, pouvez-vous simplement m'indiquer laquelle ?"
    ),
    "pain_insufficient": (
        "Avec les informations disponibles, je ne peux pas adapter la séance de façon suffisamment prudente : "
        "je préfère donc ne pas vous proposer de programme. Le mieux est de demander conseil à un professionnel de "
        "santé (médecin, kinésithérapeute) ou à un entraîneur qualifié avant de reprendre ou de modifier votre "
        "entraînement. Si un professionnel vous a donné son accord, vous pouvez me le dire (« pas de douleur, j'ai "
        "le feu vert ») et je préparerai une séance."
    ),
    "pain_too_few": (
        "En écartant les exercices qui sollicitent cette zone, il en reste trop peu avec votre matériel pour composer "
        "une séance cohérente. Je préfère ne pas vous proposer de programme : demandez conseil à un professionnel de "
        "santé ou à un entraîneur qualifié, qui pourra adapter l'entraînement à votre situation."
    ),
    "pain_red_flag": (
        "Merci pour ces précisions. Ce que vous décrivez mérite l'avis d'un professionnel de santé avant toute séance : "
        "je ne vous propose donc pas de programme pour l'instant. En cas de douleur dans la poitrine, de malaise ou "
        "d'essoufflement inhabituel, appelez le 15 ou le 112."
    ),
    "pain_session_intro": (
        "Voici une séance prudente qui écarte les exercices sollicitant la zone signalée. Ce tri reste approximatif "
        "et ne remplace pas l'avis d'un professionnel de santé ou d'un entraîneur qualifié : demandez-lui conseil "
        "avant de reprendre ou de modifier votre entraînement."
    ),
    "nutrition": (
        "HALTUP ne donne pas de conseils nutritionnels ou de régime : pour l'alimentation, un médecin ou un "
        "diététicien·ne est la bonne personne. Je peux en revanche vous préparer une séance de musculation."
    ),
    "extreme": (
        "HALTUP ne propose pas de tests de charge maximale, d'entraînement systématique jusqu'à l'échec ni de "
        "méthodes risquées, et ne donne aucune information sur des produits dopants. Les séances restent à une "
        "difficulté maîtrisée, avec une marge de sécurité."
    ),
    "off_topic": (
        "HALTUP se concentre sur la préparation d'une séance de musculation, je ne peux pas vous aider sur ce sujet. "
        "Voulez-vous qu'on revienne à votre profil de séance (sport, objectif, matériel, durée) ?"
    ),
    "restart": "C'est reparti : votre profil a été effacé. Décrivez-moi votre nouvelle séance.",
    "too_short": (
        "%d minutes, c'est trop court pour une séance complète avec échauffement. Je vous propose la version "
        "minimale de 15 minutes."
    ),
    "ai_fallback": (
        "Le service d'IA n'a pas répondu correctement : la séance a été générée par le moteur de règles d'HALTUP."
    ),
}

GLOSSARY = {
    "serie": "Une série est un groupe de répétitions enchaînées sans pause (par exemple 3 séries de 10 = 3 fois 10 répétitions avec du repos entre).",
    "repetition": "Une répétition est une exécution complète d'un mouvement (descendre puis remonter, par exemple).",
    "en reserve": "« Garder des répétitions en réserve » signifie arrêter la série alors que vous pourriez encore en faire 1 à 3 avec une bonne technique.",
    "gainage": "Le gainage consiste à maintenir le tronc stable et aligné (abdominaux, dos, fessiers) pendant un effort.",
    "explosivite": "L'explosivité est la capacité à produire de la force rapidement, comme pour sauter, sprinter ou lancer.",
    "unilateral": "Un exercice unilatéral travaille un côté à la fois (une jambe ou un bras), ce qui sollicite aussi l'équilibre.",
    "echauffement": "L'échauffement prépare progressivement le corps à l'effort : il élève la température, mobilise les articulations et répète les mouvements à venir.",
    "charniere": "La charnière de hanches est le mouvement de pencher le buste vers l'avant en reculant les hanches, dos neutre (comme pour ramasser un objet correctement).",
}


def system_prompt() -> str:
    return ROLE + "\n\nDirectives :\n" + "\n".join("- " + r for r in RULES)

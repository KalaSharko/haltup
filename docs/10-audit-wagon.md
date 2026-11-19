# Audit d'HALTUP au regard des consignes du projet final (Le Wagon)

Audit réalisé le 18 novembre 2026 sur le code et le comportement réel du prototype, et non sur les intentions décrites. Statuts possibles : **Présent et vérifié**, **Présent mais à vérifier**, **Absent**, **Hors périmètre de cette tâche**.

> **HALTUP n'est pas entièrement conforme au brief.** La mise en œuvre avec Zapier / Zapier Chatbot demandée par le cours n'a **pas** été réalisée et n'a **pas** été ajoutée. HALTUP repose sur une approche différente, choisie pour ce projet : du code personnalisé (Python + HTML/CSS/JS). Cette approche ne satisfait pas littéralement l'exigence Zapier. Aucun modèle d'IA n'est connecté, et les livrables de rendu (vidéo, Google Slides, captures, lien public) n'existent pas encore.

## 1. Présentation de la start-up

| Critère | Statut | Justification |
|---|---|---|
| Nom et mission | Présent et vérifié | `docs/01-fiche-startup.md`, `docs/02-…` ; la phrase de valeur s'affiche sur l'accueil (`altup/constants.py` → `BRAND`). |
| Problème traité | Présent et vérifié | `docs/01` (§ Problème). |
| Public cible et besoins | Présent et vérifié | Tableau des profils dans `docs/02`. |
| Proposition de valeur, caractère distinctif | Présent mais à vérifier | Énoncée dans `docs/01-02` ; la différenciation est présentée comme une **hypothèse**, aucune étude de marché n'ayant été faite. |
| Modèle économique | Présent mais à vérifier | Hypothèse scolaire (gratuit / premium éventuel / partenariats) dans `docs/02`, sans chiffres ni test. À défendre comme hypothèse. |

## 2. Mission et stratégie du chatbot

| Critère | Statut | Justification |
|---|---|---|
| Mission alignée sur le besoin (une séance adaptée) | Présent et vérifié | `altup/directives.py` (rôle et règles) ; comportement vérifié dans l'interface. |
| Public, objectifs, limites, ton compréhensibles | Présent et vérifié | `docs/03`, `docs/04` ; bandeaux de limites dans l'accueil et dans la section « Limites et confidentialité ». |
| Accueil : ce qu'HALTUP fait et comment commencer | Présent et vérifié | Titre, phrase de valeur, bouton « Construire ma séance », 3 étapes, scénarios de démonstration. |

## 3. Fonctionnement et personnalisation

| Critère | Statut | Justification |
|---|---|---|
| Sport | Présent et vérifié | Oriente les familles d'exercices (`sports.json` → `priority_patterns`) et le texte d'introduction. Confiance « faible » affichée. |
| Objectif | Présent et vérifié | Séries, répétitions, repos et choix des exercices (`GOAL_RULES`). |
| Niveau | Présent et vérifié | Filtre la difficulté des exercices et le volume. |
| Matériel | Présent et vérifié | Exercice attribué seulement si le matériel est coché ; 16 632 combinaisons balayées sans violation. |
| Lieu | Présent mais à vérifier | **Influence limitée** : le lieu sert d'hypothèse de matériel (salle = haltères, banc, machines) et s'affiche, mais ne change pas les exercices lorsque le matériel est indiqué. |
| Durée | Présent et vérifié | Volume ajusté ; écart maximal observé : +1 min sur 15 min, signalé sur la carte. |
| Charge sportive récente / à venir | Présent et vérifié | Veille de match : 2 séries, pas de sauts ni de barre (test + interface). |
| Douleur / blessure | Présent et vérifié | Zone seulement, exercices sollicitant la zone écartés, pas de séance si l'information est insuffisante ; aucune violation sur 8 316 profils. Étiquetage des zones approximatif et non relu. |
| Limites de personnalisation annoncées | Présent et vérifié | Hypothèses, niveau de confiance, bandeau de prudence, mention de l'origine (« règles locales, sans modèle d'IA »). |

## 4. Sources de connaissance et modèle d'IA

| Critère | Statut | Justification |
|---|---|---|
| Connaissances réellement utilisées | Présent et vérifié | Catalogue interne de 60 exercices + profils de 10 sports (`altup/data/*.json`), rédigés pour le prototype, **non relus** par un professionnel, plus des règles locales (`generator.py`). |
| Base documentaire externe / base de connaissances au sens du cours | Absent | Aucun document externe ni source vérifiée n'est branché ; aucun import de base tierce. |
| Modèle d'IA configuré | Absent | Pas de `.env`, `AI_PROVIDER` non défini, SDK `anthropic` non installé : le prototype tourne en **mode démonstration à règles locales**. Le code IA facultatif n'a été testé qu'avec des simulations, jamais avec une vraie clé. |
| Mode démonstration identifiable | Présent et vérifié | Badge « Mode démonstration » et ligne de confidentialité sous le chat ; chaque carte indique « Séance construite par les règles locales d'HALTUP, sans modèle d'IA ». |

## 5. Interface et identité visuelle

| Critère | Statut | Justification |
|---|---|---|
| Français, lisible, beige et rouge | Présent et vérifié | Vérifié sur ordinateur et en 375 px de large (aucun défilement horizontal). |
| Logo | Présent et vérifié | Symbole d'origine (chevrons) dans l'en-tête et le favicon, suivi du nom « HALTUP ». |
| Accessibilité de base | Présent mais à vérifier | Libellés de formulaire, focus visible, zones `aria-live`. Pas d'audit complet au lecteur d'écran. Sur mobile, le lien « Limites et confidentialité » de l'en-tête est masqué (section accessible en faisant défiler). |

## 6. Tests, mise en œuvre, démonstration et rendu

| Critère | Statut | Justification |
|---|---|---|
| Tests automatisés | Présent et vérifié | `python3 -m unittest discover -s tests -v` : **20 tests OK** (18/11/2026). |
| Grille de validation manuelle | Présent mais à vérifier | `docs/06` existe, mais **aucune ligne n'est remplie** par l'équipe. |
| Mise en œuvre avec Zapier / Zapier Chatbot | Absent | Non réalisée et non ajoutée : HALTUP utilise du code personnalisé (choix du projet). À expliquer dans la présentation. |
| Lien de démonstration accessible | Absent | L'application tourne seulement en local (`python3 server.py`). Aucun déploiement. |
| Captures d'écran (scénarios, configuration) | Absent | Aucune capture dans le projet. |
| Présentation Google Slides | Absent | Seul un plan existe (`docs/07`). |
| Vidéo de 2 min maximum | Absent | Seul un script existe (`docs/08`). |
| Nommage `FinalChallenge_VotreNom` | Absent | Aucun fichier de rendu nommé ainsi. |
| Déploiement, comptes, intégrations externes | Hors périmètre de cette tâche | Volontairement non réalisés. |

## Parcours vérifiés dans l'application (18/11/2026, navigateur intégré, données fictives)

| # | Parcours | Résultat observé |
|---|---|---|
| 1 | Profil complet (basket, force, intermédiaire, salle, haltères + banc + machines, 45 min) | Séance de 45 min, matériel respecté, étiquettes du profil affichées. |
| 2 | Maison sans matériel (scénario) | 5 exercices « Matériel : aucun », 28 min pour 30. |
| 3 | « J'ai un match demain » | 2 séries par exercice, intensité modérée, pas de sauts. |
| 4 | « J'ai mal au genou » | Séance prudente sans exercice sollicitant le genou ; bandeau « ne garantit pas l'absence de risque » et recommandation d'un professionnel. |
| 5 | Mode démonstration | Badge + « Aucun fournisseur d'IA configuré » + origine sur chaque carte. |
| 6 | Conversation, Recommencer, Supprimer la séance | Adaptation par le chat OK ; « Recommencer » remet tout à zéro ; « Supprimer la séance » (zone Conversation, désactivé sans séance) retire la carte et la séance active en gardant profil et conversation. |
| 7 | Données et confidentialité | Aucune donnée du profil enregistrée dans le navigateur (option « Mémoriser » retirée le 18/11/2026, ancienne clé supprimée au chargement) ; aucun cookie ; seules des requêtes vers `localhost`. |

## Corrections secondaires faites pendant l'audit

1. **Texte de confidentialité du mode IA inexact.** Il affirmait que les déclarations d'âge n'étaient pas transmises, et les messages de douleur restaient dans l'historique envoyé au modèle. Le texte est corrigé et ces messages sont remplacés par une mention neutre (test `test_10d`).
2. **« Ce qui a changé » sur une séance neuve générée par le formulaire** : il mentionnait un exercice jamais montré. Corrigé.
3. **Anciennes cartes encore cliquables** après une adaptation, et carte restant affichée alors que le serveur n'avait plus de séance active. Elles sont désormais grisées et inactives.
4. **Explication de scénario** qui pouvait réapparaître sur une séance ultérieure après une erreur de formulaire. Corrigé.
5. **« Autres exercices » sans séance** : le message parlait d'une « variante de votre séance ». Corrigé.

Ajouts demandés ensuite : accueil épuré, doublon de scénarios supprimé (l'espace de séance s'affichait aussi sous l'accueil à cause d'une règle CSS qui annulait `hidden`), barre de progression du profil sur 10 rubriques obligatoires, retrait de la mémorisation locale.

Ajouts demandés : bouton **« Supprimer la séance »** (zone Conversation + carte), puis renommage de la marque en **« HALTUP »** dans toute l'interface et les documents (le symbole d'origine est conservé).

## Livrables à préparer par l'étudiant

- [ ] Remplir la grille `docs/06-scenarios-validation.md` après avoir testé soi-même.
- [ ] Captures d'écran : accueil, scénarios, séance, douleur, mode démonstration, configuration (`.env.example`, sans clé).
- [ ] Présentation Google Slides à partir de `docs/07` (inclure une diapositive « écarts au brief » : Zapier, IA, base de connaissances, déploiement).
- [ ] Vidéo de 2 minutes maximum à partir de `docs/08`.
- [ ] Nommer les fichiers de rendu `FinalChallenge_VotreNom`.
- [ ] Décider s'il faut un lien de démonstration public (non fait ici), et le cas échéant comment l'héberger.
- [ ] Préparer l'explication du choix « code personnalisé plutôt que Zapier ».

## Risques et limites restants

- Contenus (exercices, profils sportifs, zones) rédigés pour le prototype et **non relus** par un professionnel.
- Analyse du texte libre par mots-clés : des formulations inhabituelles peuvent ne pas être comprises.
- En mode IA, la liste d'exercices proposée au modèle est déjà filtrée par zone : elle peut laisser deviner indirectement une zone signalée.
- Veille de match : des exercices de jambes à charge modérée peuvent rester présents.
- Le lieu a peu d'effet quand le matériel est renseigné.
- Le mode IA n'a jamais été testé avec une vraie clé.

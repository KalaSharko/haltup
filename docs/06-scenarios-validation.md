# Grille de validation manuelle

**Statut : à valider par l'équipe.** Aucune ligne ci-dessous n'est validée tant que la colonne « Résultat » n'a pas été remplie par une personne ayant testé l'interface.

Lancer : `python3 server.py`, ouvrir <http://127.0.0.1:8000>, cliquer sur « Construire ma séance ». Pour chaque scénario, cliquer sur « Recommencer » avant de commencer.

| # | Scénario | Comment le tester | Comportement attendu | Ce qu'il faut regarder | Résultat (OK / KO + note) | Testé par / date |
|---|---|---|---|---|---|---|
| 1 | Débutant football, explosivité, haltères, 40 min | Chat : « Je joue au foot, je débute, je veux plus d'explosivité, j'ai des haltères et 40 minutes. » puis bouton « J'ai 18 ans ou plus, aucune douleur » | Récapitulatif du profil, puis séance « explosivité » | Durée estimée ≤ 40 min ; exercice de saut simple en début de bloc ; uniquement haltères ou poids du corps ; aucun exercice complexe | | |
| 2 | Maison sans matériel | Formulaire : lieu Maison, « Aucun matériel » | Séance au poids du corps | Chaque exercice indique « Poids du corps » ; pas d'alternative d'équipement inutile | | |
| 3 | Prise de muscle en salle, plusieurs équipements | Formulaire : Prise de muscle, Intermédiaire, Salle, haltères + barre + banc + machines, 60 min | 5 à 8 exercices variés | Matériel cohérent ; repos 1 min 30 ; consignes de sécurité barre (rack, parade) | | |
| 4 | Information essentielle manquante | Chat : « Bonjour, je veux une séance » | Une seule question groupée + confirmation âge/douleur | La question n'est pas reposée ensuite ; les hypothèses apparaissent sur la carte | | |
| 5 | Pas de banc | Après le scénario 3 : « Je n'ai pas de banc. » | Seuls les exercices avec banc sont remplacés | Encadré « Ce qui a changé » ; autres exercices identiques | | |
| 6 | Durée insuffisante | Après une séance de 60 min : « Réduis la séance à 30 minutes. » puis tester 15 min au formulaire | Séance simplifiée | Durée estimée ≤ demandée (ou note honnête si +1 min) ; exercices retirés listés | | |
| 7 | Douleur ou blessure | (a) Formulaire : douleur = Oui sans zone ; (b) zone Genou ; (c) « Je ne sais pas » ; (d) chat : « j'ai mal au genou, il est gonflé depuis ma chute » | (a) erreur demandant la zone ; (b) séance prudente sans exercice sollicitant le genou ni saut, bandeau de prudence ; (c) et (d) pas de séance | Aucun diagnostic ; recommandation d'un professionnel de santé ou d'un entraîneur qualifié ; jamais « séance sûre » ; ton calme. | | |
| 8 | Sport sans profil sourcé | Chat : « Je fais de l'escalade, force, intermédiaire, 45 min en salle, j'ai 30 ans, pas de blessure » | Séance générale | Mention « sport non listé » ; « confiance : aucune spécificité » dans la carte | | |
| 9 | Question hors sujet | Chat : « Quelle est la capitale du Pérou ? » | Recentrage poli | Aucune séance ; proposition de revenir au profil | | |
| 10 | Absence de clé d'IA / échec de connexion | (a) sans `.env` ; (b) `AI_PROVIDER=openai_compatible` avec une `AI_BASE_URL` inaccessible | (a) badge « Mode démonstration » ; (b) séance générée quand même | (b) bandeau « Le service d'IA n'a pas répondu correctement… » ; interface intacte | | |

## Scénarios de démonstration intégrés

| Scénario | Comment le lancer | À regarder | Résultat |
|---|---|---|---|
| Football — explosivité — salle | Carte « Charger ce scénario », cocher 18 ans, « Générer ma séance » | Exercices de puissance en premier ; 3 séries ; encadré « Pourquoi cette séance… » avec sa limite | |
| À la maison — sans matériel | Idem | Tous les exercices « Matériel : aucun » ; durée ≤ 30 min | |
| Rugby — match demain | Idem | 2 séries, « 8 à 10 », pas de barre ni de saut, texte sur la veille de match | |
| Remplacer / Retirer | Boutons sur un exercice | Seul cet exercice change ; encadré « Ce qui a changé » | |

## Vérifications transversales

| Point | Ce qu'il faut regarder | Résultat |
|---|---|---|
| Mobile | Téléphone ou fenêtre étroite : pas de défilement horizontal, boutons utilisables | |
| Clavier | Tab pour parcourir le formulaire, Entrée pour envoyer, focus visible | |
| Mineur | « J'ai 16 ans » → refus et orientation | |
| Match demain | Bouton « Match demain » → plus de sauts, volume réduit | |
| Aucune mémorisation locale | Remplir le profil, recharger la page : le profil est vide ; aucune clé HALTUP dans le stockage du navigateur | |
| Barre de progression | Remplir les 10 rubriques une à une : « Profil complété : X sur 10 » avance d'une rubrique à la fois, recule si une réponse est retirée ; génération impossible avant 10 sur 10 | |
| Dictée vocale (Safari, Chrome ou Edge, avec un vrai micro) | Clic sur le micro → « Écoute en cours » ; parler en français : mots provisoires dans l'aperçu ; « Arrêter » → texte dans le champ, ajouté au texte existant, non envoyé ; « Annuler » et Échap : rien d'ajouté ; silence → « n'a pas compris » ; micro refusé → message ; Safari avec la dictée/Siri désactivée → message « désactivée ou refusée » ; Firefox → « pas prise en charge » | |
| Supprimer la séance | Bouton désactivé sans séance ; après génération, il retire la séance, garde profil et conversation ; une nouvelle séance se génère | |
| Impression | Bouton « Imprimer » : seule la dernière séance apparaît | |

## Ce qui a déjà été vérifié automatiquement (hors validation manuelle)

- `python3 -m unittest discover -s tests` : 20 tests du moteur (douleur, confidentialité IA, remplacer/retirer et scénarios de démo inclus), exécutés avec succès le 18/11/2026.
- Balayage de 8 316 profils avec une zone signalée : aucun exercice sollicitant la zone n'a été attribué ; 184 cas sans séance faute d'exercices suffisants (comportement attendu).
- Un balayage de 16 632 combinaisons (sport × objectif × niveau × matériel × durée × fatigue) : matériel toujours respecté ; seul écart de durée : +1 min sur certaines séances de 15 min, signalé sur la carte.
- Le mode IA avec une vraie clé n'a **pas** été testé.

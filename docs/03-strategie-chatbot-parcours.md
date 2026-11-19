# Stratégie du chatbot et parcours utilisateur

## Principe

Le chatbot sert à **recueillir le profil naturellement** et à **adapter la séance**. Le choix des exercices est toujours limité par des règles : matériel, niveau, fatigue, durée et sécurité. L'IA, si elle est activée, aide à comprendre et à formuler ; elle ne décide jamais seule.

```
Message utilisateur
   │
   ├─ 1. Règles de sécurité locales (âge, douleur, charges maximales, nutrition)  → réponse fixe, aucun appel externe
   ├─ 2. IA facultative : interprète le message, propose des exercices parmi une liste filtrée
   │      └─ revalidation serveur ; en cas d'échec → moteur de règles
   └─ 3. Moteur de règles : construit ou adapte la séance (durée recalculée)
```

## Parcours

1. **Accueil** — proposition de valeur, bouton « Construire ma séance », limites.
2. **Profil** — formulaire court (à gauche) **ou** message libre dans le chat (à droite). Les deux sont synchronisés.
3. **Clarification** — une seule question groupée pour les informations manquantes ; ensuite, hypothèses annoncées (ex. : niveau débutant par prudence). Confirmation « 18 ans ou plus » et « douleur oui/non » par boutons.
4. **Récapitulatif** — « Noté : Football · Explosivité · Débutant · 40 min · Haltères ».
5. **Génération** — indicateur de chargement, puis carte de séance lisible comme un ensemble : phrase d'introduction, puis trois temps numérotés (échauffement, corps de séance, retour au calme), chacun introduit par une phrase. Chaque exercice suit la même présentation : nom, séries / répétitions ou durée / repos, « Comment faire », matériel et variante sans ce matériel, puis les boutons « Remplacer » et « Retirer ». Viennent ensuite la prudence (en phrases), les hypothèses, l'adaptation au sport, les sources et l'origine de la séance (règles locales ou IA).
6. **Adaptations** — boutons rapides ou texte libre ; seules les parties concernées changent et sont listées dans « Ce qui a changé ».
7. **Actions** — modifier les informations, imprimer, recommencer.

## Règles de conversation

- Ne pas reposer une question déjà posée (suivi `asked`).
- Faire une hypothèse raisonnable si l'information n'est pas critique, et l'afficher.
- Bloquer la génération tant que l'âge (18+) n'est pas confirmé et que la question de la douleur n'a pas de réponse.
- En cas de douleur : demander uniquement la zone (boutons), écarter les exercices et éléments d'échauffement qui la sollicitent ainsi que les sauts, réduire le volume, afficher un bandeau prudent. Pas de séance si la zone est inconnue, s'il y a plus de deux zones, des signes d'alerte, ou trop peu d'exercices restants.
- Garder le contexte de la session (profil + séance) ; aucun stockage serveur.

## Adaptations prises en charge

| Demande | Effet |
|---|---|
| « Je n'ai pas de banc » | Retire le banc ; remplace uniquement les exercices qui en avaient besoin |
| « Réduis à 30 minutes » | Réduit séries, puis repos, puis retire les exercices les moins prioritaires |
| « Plus facile » / « je débute » | Baisse le niveau ou passe aux variantes plus faciles |
| « Match / entraînement demain » | Retire sauts et puissance, réduit le volume |
| « Autres exercices » | Nouvelle variante avec le même profil |
| Bouton « Remplacer » sur un exercice | Autre exercice de la même famille de mouvement, avec le matériel déjà indiqué (sinon une famille proche) ; le reste ne change pas |
| Bouton « Retirer » | Retire l'exercice (deux exercices minimum) et recalcule la durée |
| « Raccourcir de 10 min » | Même logique que « Réduis à … minutes » |
| « J'ai mal au genou » après une séance | Les exercices sollicitant le genou sont remplacés ou retirés ; bandeau de prudence |
| Changement de sport ou d'objectif | Nouvelle séance |

## Scénarios de démonstration

Trois cartes dans l'espace de séance (section « Scénarios de démonstration ») : *Football — explosivité — salle*, *À la maison — sans matériel*, *Rugby — match demain*. Chacune remplit le formulaire et affiche les choix retenus, la raison et une limite. L'utilisateur confirme son âge puis clique sur « Générer ma séance ». La carte de séance reprend alors « Pourquoi cette séance correspond au scénario ». Définition centralisée : `DEMO_SCENARIOS` dans `altup/constants.py`.

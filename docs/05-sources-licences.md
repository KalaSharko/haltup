# Sources et licences

État au 17 novembre 2026.

## Ce qui est réellement utilisé

| Élément | Provenance | Licence | Vérification |
|---|---|---|---|
| Catalogue de 60 exercices, 8 éléments d'échauffement, 5 de retour au calme (`altup/data/exercises.json`) | Rédaction originale pour le prototype, à partir de connaissances générales en préparation physique | Contenu original du projet — **licence à choisir par l'équipe** | **Non relu par un professionnel qualifié** |
| Profils de 10 sports + profil général (`altup/data/sports.json`) | Synthèse générale rédigée pour le prototype | Idem | **Aucune source externe consultée** ; niveau de confiance « faible » affiché dans l'application |
| Zones sollicitées par exercice (champ `zones`) | Étiquetage rédigé pour le prototype (articulations ou régions principalement sollicitées) | Idem | **Approximatif, non relu par un professionnel** ; sert uniquement à écarter des exercices, jamais à évaluer une blessure |
| Logo et icônes | Formes géométriques simples dessinées en SVG pour le projet | Contenu original | — |
| Code | Écrit pour le projet ; bibliothèque standard Python ; SDK `anthropic` facultatif (licence à vérifier sur son dépôt officiel avant diffusion) | À choisir par l'équipe | — |

Aucune image, vidéo, police externe ni base de données tierce n'est intégrée. Aucun site n'a été aspiré (« scrapé »).

## Pistes examinées pour plus tard (non intégrées)

| Piste | Statut | À faire avant intégration |
|---|---|---|
| wger (base d'exercices) | **Non examinée dans cette version** | Vérifier séparément la licence du code et celle du contenu (textes, images) sur la source officielle ; respecter l'attribution demandée |
| Free Exercise DB | **Non examinée dans cette version** | Vérifier la licence des fichiers précis (données et images) ; ne pas supposer qu'une ressource publique est réutilisable |
| Vidéos YouTube | Aucune intégrée | Uniquement des liens choisis et vérifiés à la main, lecteur officiel si l'intégration est autorisée ; pas de téléchargement ni de copie de sous-titres |
| Sources sportives (fédérations, publications) | Aucune consultée | Ajouter dans `sports.json` → `sources` (titre, auteur, lien, date de consultation) et relever le niveau de confiance |

## Comment ajouter une source

1. Vérifier la licence sur la page officielle et noter la date.
2. Distinguer licence du code et licence du contenu.
3. Ajouter l'entrée dans le champ `sources` du profil concerné ou dans `meta` du catalogue.
4. Mettre à jour ce document.

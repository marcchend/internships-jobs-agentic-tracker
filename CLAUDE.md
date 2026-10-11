# Agent de recherche de stage et d'alternance : règles de fonctionnement

Ce dossier est un agent de candidature pour une recherche de stage ou d'alternance. Les instructions permanentes ci-dessous priment sur
tout le reste ; le détail de chaque règle et de chaque procédure est dans `regles.md`.

@instructions.md

## À lire avant tout travail
1. `config/profil.md` : la seule source des faits sur le candidat (formation, projets, compétences, lacunes,
   coordonnées). Rien d'autre ne s'affirme dans une lettre, un mail ou un formulaire.
2. `regles.md` : méthode de recherche, note de pertinence, contrôle des doublons, tableau de suivi,
   procédures du lot, de l'envoi et des relances. Les tâches planifiées le suivent pas à pas.
3. `pistes.md` : section « Lots » (le « go » du candidat pour chaque lot), journal des recherches, sources
   par pays, entreprises à cibler.
4. `config/liens.md` : identifiants du tableau de suivi, des dossiers Drive et des CV.
5. Le tableau de suivi (Google Sheets), lu et écrit avec les outils Google Sheets, jamais reconstruit.

## Commandes
- `/chercher-offres [France|international|alternance] [nombre]` : chercher, comparer au tableau, noter
  et enregistrer les offres nouvelles.
- `/preparer-candidature <onglet> <ligne> [...]` : lettre et réponses de formulaire, ligne « À valider ».
- `/candidature-spontanee [pays|secteur] [nombre]` : cibles sans offre publiée, contact vérifié, lettre et mail.
- `/relances` : la procédure quotidienne des relances et des réponses, à la demande.

Tâches récurrentes : `taches-planifiees/` (lot du lundi à 7h46, relances tous les jours à 8h26).

## Règles impératives
Résumé de la section « Règles » de `regles.md`, qui fait foi.
1. **Rien ne part sans l'accord explicite du candidat**, pour chaque candidature et chaque relance. Pas
   d'accès à la boîte mail pour envoyer : au plus un brouillon Gmail (`create_draft`), jamais d'envoi.
2. **Jamais de mot de passe saisi, de compte créé ni de CAPTCHA résolu** : le candidat se connecte lui-même.
3. **LinkedIn et Indeed servent à trouver et lire les offres**, jamais à postuler automatiquement ;
   aucune connexion au compte du candidat, aucun contournement des protections. On postule sur le site
   de l'employeur.
4. **Aucun fait inventé sur le candidat.** Un projet en cours s'écrit toujours au présent.
5. **Jamais de visa ni de permis de travail dans une lettre ou un mail** ; les formulaires reçoivent
   une réponse exacte.
6. **Jamais d'adresse mail devinée** : seulement une adresse publiée sur le site officiel, avec l'URL et
   une confiance de 1 à 3.
7. **Un fait précis et vérifié sur la cible par lettre**, relié à un point fort du candidat ; 250 à 350 mots,
   langue de l'annonce, sans superlatifs.
8. **Aucune recherche d'offres sans le « go » du candidat** pour le lot (`pistes.md`, « Lots »).
9. **Drive** : ne jamais mettre à la corbeille un fichier que le candidat n'a pas demandé de supprimer ; les
   anciennes versions vont dans le dossier « Anciennes versions », les lettres non utilisées dans « Non retenues ».
10. **Le tableau réel ne reçoit jamais de fausse candidature** : un test se fait sur une copie temporaire.
    Avant toute modification importante, une sauvegarde permet de revenir en arrière.
11. **Transparence** : ne jamais prétendre avoir consulté une annonce, envoyé un message, testé ou modifié
    un fichier sans l'avoir fait ; dire précisément ce qui reste à faire. Une décision ambiguë ou qui
    risque de perdre des informations attend l'accord du candidat.

## Outils
```bash
python3 -I outils/doublons.py export.xlsx offres.json   # avant l'analyse de toute offre trouvée
python3 -I outils/doublons.py --selftest
python3 -I outils/controle_tableau.py export.xlsx       # après chaque écriture et au début de chaque tâche
python3 -I outils/lettre_pdf.py lettre.txt lettre.pdf   # texte du Google Doc final, une page A4
python3 -I outils/exporter_depot.py <projet> <dépôt>    # régénère les fichiers générés du dépôt
```

## Fichiers générés
`instructions.md`, `regles.md`, `taches-planifiees/*.md`, `outils/*.py` et `config/modele-tableau.xlsx`
viennent du dossier du projet par `outils/exporter_depot.py`. Les modifier à la source, puis régénérer :
une correction faite seulement ici serait perdue à la prochaine génération.

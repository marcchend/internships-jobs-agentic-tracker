# Internships & Jobs Agentic Tracker

*[English](README.md) · Français*

Un agent de candidature avec validation humaine, construit sur [Claude](https://claude.com/claude-code),
pour les étudiants qui cherchent un stage ou une alternance en Data Science et en IA, en France ou à
l'étranger.

Il cherche les offres dans un ordre fixé, compare chaque offre au tableau de suivi avant de l'analyser,
note sa pertinence avec un barème simple et justifié, prépare la lettre et les réponses de formulaire,
suit chaque candidature dans un Google Sheets avec tableau de bord, et prépare les relances à J+14 et
J+28 après l'envoi.

**Rien ne part sans l'accord du candidat.** L'agent prépare ; le candidat valide chaque candidature et
chaque relance. Voir [Principes](#principes).

Inspiré de [internship-agent](https://github.com/Mehdy03055/internship-agent), repensé autour d'un autre
tableau de suivi, d'un autre barème et d'autres règles (voir [Différences avec le modèle](#différences-avec-le-modèle)).

---

## Ce qu'il fait

| Flux | Fréquence | Résultat |
|---|---|---|
| **Lot hebdomadaire** | le lundi à 7h46, seulement après le « go » du candidat pour ce lot | 5 candidatures préparées (3 ou 4 offres publiées, 1 ou 2 candidatures spontanées) : lettre en Google Doc, réponses de formulaire, ligne « À valider » dans le tableau |
| **Relances et réponses** | tous les jours à 8h26 | offres expirées, relances dues à J+14 et J+28 préparées pour validation, « Sans réponse » proposé à J+42, réponses et retours d'erreur lus si Gmail est connecté |
| **Envoi** | après l'OK du candidat, candidature par candidature | formulaire rempli après la connexion du candidat, ou brouillon Gmail ; statut « Envoyée » et date d'envoi |

Chaque offre a une ligne dans le tableau, avec un statut :

```
Repérée → À valider → À envoyer → Envoyée → Relancée 1 fois → Relancée 2 fois → Sans réponse
                                         ↘ Entretien ou échange → Acceptée / Refusée / Abandonnée
                                         ↘ Adresse invalide
Repérée → Incompatible / Expirée / Abandonnée
```

## Comment ça marche

```
   instructions.md   ─┐  règles permanentes (elles priment)
   regles.md         ─┤  méthode, note de pertinence, doublons, tableau, procédures
   config/profil.md  ─┘  seuls faits que l'agent peut affirmer sur le candidat (hors de Git)
                       │
   tâche planifiée ──► Claude ──► recherche : LinkedIn (accès limité), Indeed, sites carrières, autres sources
                         │
                         ├──► outils/doublons.py ──► offre déjà dans le tableau ? (avant toute analyse)
                         ├──► analyse : missions, adéquation, accessibilité, note sur 4 ou sur 3
                         ├──► Google Sheets : une ligne par offre, colonne de relance calculée, tableau de bord
                         │      └──► outils/controle_tableau.py ──► contrôle de cohérence après chaque écriture
                         ├──► Google Docs : lettre et réponses de formulaire ──► outils/lettre_pdf.py ──► PDF
                         └──► récapitulatif au candidat ──► OK par candidature ──► envoi
```

Tout l'état est lisible par une personne :

- **`instructions.md`** : les instructions permanentes du projet, importées par `CLAUDE.md`.
- **`regles.md`** : le référentiel détaillé, que les tâches planifiées suivent pas à pas.
- **`config/profil.md`** : le profil du candidat (formation, projets, compétences, lacunes). L'agent
  n'écrit rien sur le candidat qui n'y figure pas.
- **`pistes.md`** : lots (avec le « go » du candidat), journal des recherches, sources par pays,
  entreprises à cibler.
- **Le tableau de suivi** (Google Sheets) : onglets Stage France, Stage International, Alternance et
  Tableau de bord.
- **`taches-planifiees/*.md`** : le prompt complet de chaque tâche récurrente.

## La note de pertinence

Un seul barème, qui sert à classer les offres, jamais à les écarter :

| Offre | Note | Critères (−1 chacun, justifié par un élément concret de l'offre) |
|---|---|---|
| Stage en France | sur 4 | 1. manque de profondeur technique ; 2. entreprise peu connue, sans réputation technique (taille moyenne, start-up ou PME ; jamais un grand groupe reconnu) ; 3. hors de Paris ; 4. durée explicitement fixée à 6 mois |
| Stage à l'étranger | sur 3 | critères 1, 2 et 4 (jamais de pénalité de lieu) |
| Alternance | sur 4 | critères 1, 2 et 3 (choix par défaut) |

Une information absente ou ambiguë n'est jamais supposée défavorable, un même défaut ne retire qu'un
point, et la compatibilité (durée, niveau, compétences exigées, lieu) s'évalue à part. La note classe
les offres ; l'adéquation technique et l'accessibilité, écrites dans les notes de chaque ligne,
départagent les égalités. `outils/controle_tableau.py` vérifie que chaque note égale la note maximale
moins les retraits écrits dans le Motif. Les critères sont définis dans `instructions.md`, section 5,
et dans `regles.md`, « Note de pertinence », où ils peuvent être adaptés.

## Installation

1. **Prérequis** : Claude Code (ou un projet Claude avec dossier partagé), Python 3.10 ou plus récent,
   Chromium ou Chrome pour les PDF, et les connecteurs Google Drive et Google Sheets. Gmail est
   facultatif : sans lui, les mails sont préparés en texte et le candidat les envoie lui-même.

2. **Cloner et compléter la configuration**

   ```bash
   git clone https://github.com/<compte>/internships-jobs-agentic-tracker.git
   cd internships-jobs-agentic-tracker
   cp config/profil.exemple.md config/profil.md     # faits vérifiés sur le candidat
   cp config/liens.exemple.md config/liens.md       # identifiants du tableau, des dossiers Drive et des CV
   cp config/pistes.exemple.md pistes.md            # lots, journal des recherches, entreprises à cibler
   ```

   `config/profil.md`, `config/liens.md`, `pistes.md`, les lettres et le CV sont ignorés par Git : les
   données personnelles restent hors du dépôt.

3. **Le tableau de suivi** : `config/modele-tableau.xlsx` est l'export Excel du tableau vide (colonnes,
   listes déroulantes, formules, mises en forme, tableau de bord). L'importer dans Google Sheets
   (paramètres régionaux France, pour le séparateur « ; » des formules), puis noter son identifiant dans
   `config/liens.md`. Dans Excel ou LibreOffice, la colonne « Prochaine relance » ne se calcule pas
   (Err:539 dans LibreOffice) : le fichier sert à l'import, pas au suivi. Si la formule de T1 ne survit
   pas à l'import, la recoller depuis `docs/architecture.md`. La structure est décrite dans `regles.md`,
   « Tableau de suivi ».

4. **Les commandes** (skills de Claude Code)

   ```bash
   mkdir -p .claude/skills && cp -r skills/* .claude/skills/
   ```

5. **Les tâches planifiées** : chaque fichier de `taches-planifiees/` est un prompt complet, avec sa
   planification. Remplacer `<ID_TABLEAU>` par l'identifiant du tableau, puis l'enregistrer dans le
   planificateur disponible (routines d'un projet Claude, tâches planifiées de l'application, ou cron
   avec `claude -p "$(cat taches-planifiees/relances-et-reponses.md)"`).

## Utilisation

Dans Claude Code, depuis le dossier du dépôt :

```
/chercher-offres France 5                 # chercher des offres, les comparer au tableau, noter et enregistrer les nouvelles
/preparer-candidature "Stage France" 12   # lettre et réponses de formulaire pour une ligne du tableau
/candidature-spontanee Japon 2            # cibles sans offre publiée, contact vérifié, lettre et mail
/relances                                 # relances dues, réponses, offres expirées
```

Outils en ligne de commande :

```bash
python3 -I outils/doublons.py export.xlsx offres.json   # offres trouvées comparées au tableau exporté
python3 -I outils/doublons.py --selftest                # vérifie l'outil
python3 -I outils/controle_tableau.py export.xlsx       # cohérence du tableau : note et motif, statuts et dates, relances
python3 -I outils/lettre_pdf.py lettre.txt lettre.pdf   # lettre (texte du Google Doc) en PDF d'une page
```

## Principes

Ce sont des contraintes, pas des options.

1. **Claude prépare, le candidat décide.** Aucune candidature, aucun formulaire et aucune relance ne
   part sans son accord explicite, donné candidature par candidature. Pour un mail, au plus un
   brouillon Gmail.
2. **Aucun fait inventé.** Tout ce qui est dit du candidat vient de `config/profil.md`. Un projet en
   cours est toujours écrit au présent. Une durée, une mission ou une exigence absente de l'annonce
   n'est jamais supposée.
3. **Aucun contact inventé.** Une adresse n'est utilisée que si elle est publiée sur le site officiel de
   l'organisation, avec l'URL où elle apparaît et une confiance de 1 à 3.
4. **Un fait précis par lettre**, relié à un point fort réel du candidat, en 250 à 350 mots.
5. **Chaque offre comparée au tableau avant d'être analysée.** Une offre déjà enregistrée n'est ni
   réanalysée ni ajoutée deux fois, même trouvée sous un autre lien ; son historique n'est jamais effacé.
6. **Deux relances, puis plus rien sans raison.** J+14 et J+28, comptées depuis l'envoi ; une relance
   n'est comptée comme faite que si les données le prouvent.
7. **Respect des plateformes.** LinkedIn et Indeed servent à trouver et à lire les offres, jamais à
   postuler automatiquement ; aucune connexion au compte du candidat, aucun contournement de protection.
8. **Transparence.** L'agent ne prétend jamais avoir consulté une annonce, envoyé un message ou modifié
   un fichier sans l'avoir réellement fait, et dit précisément ce qui reste à faire.

## Différences avec le modèle

| | internship-agent | Ce dépôt |
|---|---|---|
| Langue | anglais | français |
| Suivi | `tracker.csv` exporté en xlsx | Google Sheets : trois onglets, listes, colonne de relance calculée, tableau de bord |
| Note | sur 5, selon l'angle de la cible | sur 4 en France, sur 3 à l'étranger, quatre critères justifiés |
| Relances | J+7 puis J+14 après chaque message | J+14 et J+28 depuis l'envoi initial, « Sans réponse » proposé à J+42 |
| Doublons | même entreprise et même poste | `outils/doublons.py` : liens normalisés, identifiants de plateforme, puis entreprise, intitulé et lieu, avant toute analyse |
| Recherche | libre | ordre obligatoire LinkedIn, Indeed, sites carrières, recherche indépendante ; entreprises classées de A à E |
| Rythme | 5 offres et 5 candidatures spontanées tous les 2 jours | un lot de 5 par semaine, après le « go » du candidat |
| Envoi | jamais de formulaire soumis | formulaire soumis par Claude après l'OK du candidat et sa connexion ; mails en brouillon seulement |

## Organisation du dépôt

```
README.md                   présentation (anglais)
README.fr.md                ce fichier (français)
CLAUDE.md                   règles chargées par Claude Code dans ce dossier (importe instructions.md)
instructions.md             instructions permanentes du projet (générées)
regles.md                   référentiel détaillé (généré depuis profil-et-regles.md du projet)
config/profil.exemple.md    modèle du profil (le vrai profil, config/profil.md, reste hors de Git)
config/liens.exemple.md     modèle des identifiants (tableau, dossiers Drive, CV)
config/pistes.exemple.md    modèle de pistes.md
config/modele-tableau.xlsx  tableau de suivi vide (export Excel)
skills/                     commandes : chercher-offres, preparer-candidature, candidature-spontanee, relances
taches-planifiees/          prompts des tâches récurrentes (générés)
outils/doublons.py          contrôle des offres déjà enregistrées
outils/controle_tableau.py  contrôle de cohérence du tableau (signale, ne corrige rien)
outils/lettre_pdf.py        lettre en PDF d'une page
outils/exporter_depot.py    régénère les fichiers générés et vérifie l'absence de données personnelles
docs/                       architecture et modèle de sécurité
```

## Tenir le dépôt à jour

Le dossier du projet Claude reste la référence ; ce dépôt en est la copie versionnée. Après un
changement de règles, d'outil, de tâche planifiée ou de structure du tableau :

```bash
python3 -I outils/exporter_depot.py <dossier du projet> <dossier du dépôt> \
    [--instructions instructions.txt] [--taches taches.json] [--tableau tableau.xlsx] \
    [--neutralisation neutralisation.json]
```

L'outil réécrit seulement les fichiers générés et masque les identifiants. Avec un fichier de
neutralisation, gardé hors du dépôt, il rend aussi les textes anonymes : le nom du candidat devient
« le candidat », et l'école, les projets et les décisions datées sont retirés. Il contrôle ensuite tout
le dépôt (adresses mail, téléphones, identifiants Drive, chemins, et les mots interdits du fichier de
neutralisation) : il s'arrête avec le code 1 si une donnée personnelle reste. Ensuite : relire le diff,
commit, push.

## Licence

MIT, voir [LICENSE](LICENSE).

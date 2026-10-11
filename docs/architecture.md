# Architecture

## Des fichiers lisibles plutôt qu'une base de données

| Élément | Rôle |
|---|---|
| `instructions.md` | instructions permanentes ; elles priment en cas de contradiction |
| `regles.md` | référentiel détaillé : méthode, note de pertinence, doublons, tableau, procédures |
| `config/profil.md` | faits sur le candidat ; l'agent ne peut rien affirmer d'autre (hors de Git) |
| `pistes.md` | « go » de chaque lot, journal des recherches, sources par pays, entreprises à cibler (hors de Git) |
| Tableau de suivi (Google Sheets) | une ligne par offre ; seule source de vérité des statuts et des dates |
| Google Docs | lettres et réponses de formulaire, validées par le candidat avant tout envoi |
| `taches-planifiees/*.md` | un prompt complet par tâche récurrente |
| `outils/*.py` | contrôles mécaniques : doublons, cohérence du tableau, PDF des lettres, export du dépôt |

L'intérêt est la vitesse de correction : quand une règle change (barème, calendrier des relances,
ordre des sources), la correction s'écrit une fois dans `regles.md` et dans les instructions, et chaque
exécution suivante en hérite.

## Le tableau de suivi

Trois onglets aux colonnes identiques (Stage France, Stage International, Alternance), 22 colonnes de
A à V, et un Tableau de bord :

- **Listes déroulantes** pour le domaine, la note (0 à 4, ou 0 à 3 à l'international), le statut
  (14 valeurs), la source, le CV et le canal ; validation des dates et des liens.
- **Note et motif** : la note en F, chaque point retiré en H avec un libellé fixe et l'élément concret
  qui le justifie (« −1 hors de Paris (Vélizy-Villacoublay) »).
- **Relances** : la date d'envoi en Q, les relances réellement envoyées en R et S, et la colonne T qui
  calcule la prochaine date de suivi : la date « Suivi prévu le jj/mm/aaaa » écrite dans Notes si
  elle existe, sinon Q + 14 tant que R est vide, puis Q + 28 tant que S est vide ; vide après la
  relance 2, pendant un échange, ou si Notes contient « Relances arrêtées ».
- **Tableau de bord** : nombre de lignes par statut et par onglet, suivis dus, candidatures à proposer
  en « Sans réponse » (J+42), dates limites proches, taux de réponse, pays des stages à l'étranger.
- **Mises en forme conditionnelles** : couleur par statut, lignes terminées grisées, date limite proche
  en rouge.

Le délai de base des relances (14 jours) est la seule cellule à saisir à la main (B4 du Tableau de bord).

## Les trois boucles

```
lot hebdomadaire  ──► « go » du candidat ? ──► recherche ──► doublons ──► analyse des offres nouvelles
                       ──► tableau ──► lettres et réponses ──► récapitulatif ──► OK par candidature
envoi             ──► OK du candidat ──► formulaire (le candidat connecté) ou brouillon Gmail ──► « Envoyée », date
relances          ──► tableau (colonne T) ──► relance due ? cas sans relance ? ──► relance préparée
                       ──► OK du candidat ──► date en R ou S ──► « Sans réponse » proposé à J+42
```

## Une session de recherche, dans l'ordre

1. Chercher dans l'ordre obligatoire : LinkedIn par les seuls moyens accessibles, Indeed, sites carrières
   (entreprises de priorité A à E), puis recherche indépendante ; à l'étranger, les sources du pays.
2. Relever de quoi identifier chaque offre : URL, URL de candidature, identifiant de plateforme,
   entreprise, intitulé, lieu, date de publication.
3. Exporter le tableau du jour et comparer chaque offre avec `outils/doublons.py`, avant toute analyse.
4. Mettre de côté les doublons confirmés et vérifier seulement leurs informations nouvelles importantes.
5. Analyser en entier les seules offres nouvelles : missions (cas A, B ou C), adéquation technique,
   accessibilité, compatibilité (durée, niveau, compétences exigées, lieu), note sur 4 ou sur 3.
6. Écrire chaque offre dans le tableau dès qu'elle est évaluée, sans jamais créer de deuxième ligne.
7. Laisser la colonne T calculer les relances.

## Le contrôle des doublons

`outils/doublons.py` lit l'export xlsx du tableau (les trois onglets, tous statuts) et une liste
d'offres en JSON. Il compare d'abord les liens normalisés (protocole, « www », langue, barre finale et
paramètres de suivi ignorés ; paramètres qui identifient l'offre gardés) et les identifiants de
plateforme (Indeed, LinkedIn, Workday, Greenhouse, Lever, Ashby, SmartRecruiters, Welcome to the Jungle,
JobTeaser, Taleo, SuccessFactors, sites carrières), puis l'entreprise, l'intitulé et le lieu. Verdicts :
doublon certain, doublon probable, à vérifier, même entreprise et autre poste, nouvelle. Les deux
verdicts intermédiaires demandent une vérification ciblée, puis l'avis du candidat si le doute reste. Si
le tableau est illisible, l'outil s'arrête avec le code 2 et aucune offre n'est présentée comme nouvelle.

## Le contrôle de cohérence du tableau

`outils/controle_tableau.py` lit le même export et signale, sans rien corriger : en-têtes et barème de
chaque onglet ; note égale à la note maximale moins les retraits du Motif, libellés fixes, critère permis
dans l'onglet (pas de « hors de Paris » à l'étranger), note vide pour une offre Incompatible ; statut
cohérent avec les dates (envoi, relance 1, relance 2, ordre des dates) ; marqueurs « Suivi prévu le » ;
valeur attendue de la colonne T ; doublons internes. Il liste aussi ce qui est dû (relances, J+42, dates
limites). Codes de sortie : 0 rien d'anormal, 1 anomalies, 2 tableau illisible. Les deux tâches
planifiées le lancent au début, et chaque écriture dans le tableau est suivie d'un contrôle.

Formule de l'en-tête T1 (locale fr_FR, séparateur « ; »), à recoller en T1 si l'import du modèle
Excel ne la conserve pas :

```
={"Prochaine relance (calculée)";ARRAYFORMULA(IF(LEN(Q2:Q)*((G2:G="Envoyée")+(G2:G="Relancée 1 fois")+(G2:G="Relancée 2 fois")+(G2:G="Entretien ou échange"));IFERROR(DATE(VALUE(MID(V2:V;SEARCH("Suivi prévu le ";V2:V)+21;4));VALUE(MID(V2:V;SEARCH("Suivi prévu le ";V2:V)+18;2));VALUE(MID(V2:V;SEARCH("Suivi prévu le ";V2:V)+15;2)));IF((G2:G<>"Relancée 2 fois")*(G2:G<>"Entretien ou échange")*(LEN(S2:S)=0)*ISERROR(SEARCH("Relances arrêtées";V2:V));IF(LEN(R2:R);Q2:Q+2*'Tableau de bord'!$B$4;Q2:Q+'Tableau de bord'!$B$4);));))}
```

## Le dépôt et le projet

Le système tourne dans un projet Claude : dossier partagé, connecteurs Google Drive et Google Sheets,
deux routines. Ce dépôt en est la copie versionnée. `outils/exporter_depot.py` régénère depuis le
projet les fichiers marqués « généré », masque les identifiants, rend les textes anonymes (nom du
candidat, école, projets et décisions datées, selon un fichier de règles gardé hors du dépôt) et
refuse d'écrire si une donnée personnelle reste dans un fichier suivi par Git.

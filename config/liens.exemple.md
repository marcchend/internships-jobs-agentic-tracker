# Liens et identifiants

> Copier ce fichier en `config/liens.md` et le remplir (dans le projet Claude : section « Liens » de
> `profil-et-regles.md`). Ces identifiants remplacent les marqueurs `<ID_TABLEAU>`, `<ID_DOSSIER_LETTRES>`
> et `<ID_DRIVE>` des fichiers générés. `config/liens.md` est ignoré par Git.

- Tableau de suivi (Google Sheets) : https://docs.google.com/spreadsheets/d/<ID_TABLEAU>/edit
- Dossier Drive des lettres : https://drive.google.com/drive/folders/<ID_DOSSIER_LETTRES>
  (sous-dossiers « Non retenues » <ID_DRIVE> et « Anciennes versions » <ID_DRIVE>)
- Pistes, sources, entreprises à cibler et historique des lots : `pistes.md`
- Contrôle des doublons : `python3 -I outils/doublons.py export.xlsx offres.json` (`--selftest` vérifie l'outil)
- Lettre en PDF : `python3 -I outils/lettre_pdf.py lettre.txt sortie.pdf`
- Tâches planifiées : « Lot hebdomadaire de candidatures » <ID_TACHE>, le lundi à 7h46 (Europe/Paris) ;
  « Relances et réponses » <ID_TACHE>, tous les jours à 8h26 (Europe/Paris).
- CV (PDF d'une page) : stage FR <chemin>, stage EN <chemin>, alternance FR <chemin>.

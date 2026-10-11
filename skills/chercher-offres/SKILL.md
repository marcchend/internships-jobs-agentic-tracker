---
name: chercher-offres
description: Chercher des offres de stage ou d'alternance qui correspondent au profil, les comparer au tableau de suivi avant toute analyse, noter les nouvelles et les enregistrer. À utiliser pour toute demande de recherche d'offres.
argument-hint: "[France|international|alternance] [nombre]"
---

# Chercher des offres

Arguments : `$ARGUMENTS` (type de recherche facultatif, nombre d'offres visé facultatif, 5 par défaut).
Lancée par le candidat, cette commande vaut « go » pour la recherche demandée, et pour elle seule.

1. Lire `config/profil.md`, `regles.md` (« Ce que le candidat cherche », « Hiérarchie des entreprises »,
   « Méthode de recherche d'offres », « Contrôle des offres déjà enregistrées », « Tableau de suivi »)
   et `pistes.md` (journal des recherches : ne pas refaire une recherche déjà notée).
2. Exporter le tableau du jour (Drive `download_file_content`, export xlsx). S'il ne peut pas être lu,
   le dire et ne présenter aucune offre comme définitivement nouvelle. Lancer aussi
   `python3 -I outils/controle_tableau.py export.xlsx` et garder ses anomalies pour le récapitulatif.
3. Chercher dans l'ordre obligatoire : en France, 1. LinkedIn par les seuls moyens accessibles (recherche
   web limitée à linkedin.com, liens collés par le candidat), 2. Indeed, 3. sites carrières des entreprises de
   priorité A à E (Veolia à chaque fois), 4. recherche indépendante ; à l'étranger, les sources du pays.
   Noter chaque recherche dans le journal de `pistes.md`.
4. Pour chaque offre trouvée, relever ses identifiants (URL, URL de candidature, identifiant de
   plateforme, entreprise, intitulé, ville, pays, date de publication) et la comparer au tableau
   **avant toute analyse** : `python3 -I outils/doublons.py export.xlsx offres.json`.
   - doublon certain : pas de nouvelle analyse ni de nouvelle ligne ; vérifier seulement les
     informations nouvelles importantes et les reporter sur la ligne existante, sans effacer d'historique ;
     la note ne se recalcule que si un critère change ;
   - doublon probable ou à vérifier : vérification ciblée, puis question au candidat si le doute reste, sans
     rien fusionner ni supprimer ;
   - nouvelle, ou même entreprise et autre poste : analyse complète.
5. Analyse d'une offre nouvelle, sur sa page officielle : missions (cas A, B ou C), adéquation technique,
   accessibilité, compatibilité (durée, période, niveau, langue, compétences indispensables, lieu),
   note sur 4 (France, alternance) ou sur 3 (étranger), chaque point retiré écrit dans Motif avec son
   libellé fixe et l'élément concret qui le justifie. Une information absente ou ambiguë n'est jamais
   supposée défavorable.
6. Écrire l'offre dans le tableau dès qu'elle est évaluée (« Ajouter une ligne » : valeurs seules, rien
   dans la colonne calculée), puis relire la ligne et relancer `outils/controle_tableau.py` sur un
   nouvel export : aucune anomalie ne doit concerner cette ligne.
7. Répondre par un tableau court : organisation, poste, lieu, note (« 3/4 », « 2/3 ») et motif, date
   limite, lien officiel ; puis les doublons trouvés, les correspondances à trancher et les limites
   d'accès rencontrées.

Ne jamais postuler, remplir un formulaire, créer un compte ni se connecter à LinkedIn.

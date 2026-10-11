---
name: relances
description: Vérifier les relances dues, les réponses reçues et les offres expirées dans le tableau de suivi, et préparer les relances pour validation. À utiliser pour toute question sur les relances ou les réponses.
argument-hint: ""
---

# Relances et réponses

Suivre la « Procédure : relances et réponses » et la règle 9 de `regles.md`, comme la tâche quotidienne :

1. Lire les trois onglets du tableau, exporter le tableau et lancer
   `python3 -I outils/controle_tableau.py export.xlsx` (anomalies et liste « À faire »). Offre « Repérée », « À valider » ou « À envoyer » dont la date
   limite est passée : « Expirée ». Données incohérentes (statut de relance sans date, date de relance
   sans date d'envoi, plusieurs « Suivi prévu le ») : les signaler sans rien corriger d'office.
2. Candidature dont la colonne « Prochaine relance (calculée) » est atteinte : vérifier d'abord qu'aucun
   cas sans relance ne s'applique (réponse reçue, refus, abandon ou retrait, offre fermée, réponse
   définitive, relance inutile) ; sinon, préparer la relance pour validation.
   - Relance 1 à J+14 et relance 2 à J+28, comptées toutes deux depuis la date d'envoi initiale ;
     aucune troisième relance automatique.
   - Une date donnée par le recruteur (« Suivi prévu le jj/mm/aaaa » dans Notes) prime sur ce calendrier.
   - Candidature par formulaire sans adresse publiée : demander au candidat s'il a eu une réponse, au lieu
     de préparer une relance.
3. Une relance n'est comptée comme faite qu'avec une date réelle en « Relance 1 le » ou « Relance 2 le ».
   Ne jamais reprogrammer une relance déjà faite ni effacer d'historique.
4. À J+42 sans réponse ni suivi prévu : proposer « Sans réponse » ; le statut ne change qu'avec l'OK du candidat.
5. Si Gmail est connecté : lire le corps de chaque réponse (un accusé de réception et un refus peuvent
   avoir le même objet), noter les retours d'erreur (« Adresse invalide ») ; brouillons seulement.
6. Résumé court : réponses et retours d'erreur, relances prêtes, candidatures à classer. S'il n'y a
   rien à faire, le dire en une ligne.

# Modèle de sécurité

Un agent qui lit des offres, remplit des formulaires et prépare des mails au nom de quelqu'un a besoin
de limites qui ne dépendent pas de son comportement un jour donné. Voici celles de ce projet.

## Ce que l'agent ne fait jamais

| Jamais | Pourquoi |
|---|---|
| Envoyer une candidature, un formulaire ou une relance sans l'OK explicite du candidat | Chaque envoi est une décision du candidat, prise candidature par candidature |
| Envoyer un mail | Pas d'accès en envoi : au plus un brouillon Gmail, que le candidat relit et envoie |
| Saisir un mot de passe, créer un compte, résoudre un CAPTCHA | Les identifiants restent au candidat ; un CAPTCHA vérifie qu'une personne est là |
| Postuler automatiquement par LinkedIn ou Indeed, se connecter au compte LinkedIn du candidat, contourner une protection | Leurs conditions l'interdisent et le compte peut être restreint |
| Prétendre avoir lu une annonce inaccessible | Une offre vue seulement dans un résultat de recherche n'est pas vérifiée |
| Inventer un fait sur le candidat, une durée, une mission ou une exigence | Ce serait un mensonge dit en son nom, ou une offre mal classée |
| Deviner une adresse mail | Une adresse devinée rebondit ou arrive à la mauvaise personne |
| Parler de visa ou de permis de travail dans une lettre ou un mail | C'est au candidat de partager cette information, quand c'est utile |
| Mettre à la corbeille un fichier Drive que le candidat n'a pas demandé de supprimer | Les anciennes versions vont dans « Anciennes versions », les lettres non utilisées dans « Non retenues » |
| Écrire une fausse candidature dans le tableau réel | Les tests se font sur une copie temporaire |
| Compter une relance comme faite sans preuve | Seule une date en « Relance 1 le » ou « Relance 2 le » le prouve |
| Effacer un historique de candidature, de relance ou d'échange | Une mise à jour d'offre ne réinitialise ni la note ni le calendrier |

## Les données qui restent hors de Git

`config/profil.md`, `config/liens.md`, `pistes.md`, les lettres, les CV et les exports du tableau sont
ignorés par Git. Le dépôt contient la mécanique, les règles et des modèles vides : aucune coordonnée,
aucun identifiant de fichier Drive, aucune candidature réelle. `outils/exporter_depot.py` contrôle les
fichiers suivis (adresses mail, téléphones, identifiants Drive, de tâche ou de session, profils LinkedIn,
chemins de dossier) et s'arrête si l'un d'eux en contient. Avec un fichier de neutralisation (gardé
hors du dépôt), il remplace aussi le nom du candidat par « le candidat », retire son école, ses projets
et ses décisions datées, et refuse tout fichier où un mot interdit (nom, école, projet) apparaît encore.

## Problèmes rencontrés et règles qui en sont nées

- **LinkedIn refuse la lecture automatique.** Règle : recherche web limitée à linkedin.com, puis lecture
  de l'offre sur une page accessible ; une offre non lue reste une piste du journal, pas une ligne du tableau.
- **Des identifiants Indeed (jk) faux dans les listes de résultats.** Règle : ouvrir chaque page d'offre.
- **Une entité de recrutement différente du nom affiché** (un GIE plutôt que la filiale). Règle : vérifier
  sur une page lisible qui recrute réellement.

## Précautions d'écriture dans le tableau

- Relire chaque ligne écrite par l'API : une date peut être enregistrée comme du texte au lieu d'un nombre.
- Retirer les critères d'un filtre actif avant d'écrire, sans supprimer le filtre, pour ne pas écrire
  sur une ligne masquée.
- Ne jamais écrire dans la colonne calculée « Prochaine relance » : une seule valeur saisie, même dans une
  cellule, bloque toute la colonne (#REF! dans l'en-tête) ; l'effacer rétablit le calcul.
- Une offre notée qui expire ou est abandonnée garde sa note et ses retraits : le motif de fin s'ajoute
  après eux.
- Après chaque écriture, exporter le tableau et lancer `outils/controle_tableau.py`.
- Recalculer une note à partir des critères réellement applicables et du lieu, jamais par une règle de
  trois ; une modification qui toucherait plusieurs notes à la fois attend l'accord du candidat.

## Relire avant d'envoyer

Avant chaque OK, relire la première phrase de la lettre, le destinataire et la note avec son motif :
c'est là que se trouverait une erreur, par exemple un fait attribué à la mauvaise entreprise.

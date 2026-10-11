"""Contrôle de cohérence du tableau de suivi : note et motif, statut et dates, relances, doublons internes.

Usage :
  python3 -I controle_tableau.py TABLEAU [--aujourdhui jj/mm/aaaa] [--json]
  python3 -I controle_tableau.py --selftest

TABLEAU : export xlsx du tableau (Drive, download_file_content, exportMimeType
  application/vnd.openxmlformats-officedocument.spreadsheetml.sheet), ou le fichier de résultat de cet
  outil (JSON contenant le xlsx en base64), comme pour doublons.py.

Le contrôle ne corrige rien. Il applique les règles de profil-et-regles.md (« Note de pertinence »,
« Tableau de suivi », règle 9 et « Procédure : relances et réponses ») et donne :
  ANOMALIES   ce qui contredit une règle (note qui ne correspond pas aux retraits du Motif, critère
              interdit dans l'onglet, statut sans la date qui le prouve, date écrite comme du texte,
              colonne de relance différente du calcul attendu, doublon interne probable, etc.) ;
  À VÉRIFIER  ce qui demande un regard (lieu hors de Paris sans retrait ni « À vérifier : lieu », etc.) ;
  À FAIRE     suivis dus, candidatures à proposer en « Sans réponse » (J+42), dates limites dépassées.
Code de sortie : 0 sans anomalie, 1 avec au moins une anomalie, 2 si le tableau est illisible.
"""
import io
import json
import os
import re
import sys
import zipfile
from datetime import date, datetime, timedelta

sys.dont_write_bytecode = True  # pas de __pycache__ dans le dossier partagé
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doublons  # noqa: E402  (même dossier : lecture du xlsx, liens et comparaison)

ONGLETS = {"Stage France": (4, {1, 2, 3, 4}, "sur 4"), "Stage International": (3, {1, 2, 4}, "sur 3"),
           "Alternance": (4, {1, 2, 3}, "sur 4")}
ENTETES = ["Organisation", "Poste", "Ville", "Pays", "Domaine", "Pertinence", "Statut", "Motif", "Lien de l'offre",
           "Source", "Publiée le", "Date limite", "Vérifiée le", "CV", "Lettre", "Canal", "Date d'envoi",
           "Relance 1 le", "Relance 2 le", "Prochaine relance", "Contact", "Notes"]
CLES = ["org", "poste", "ville", "pays", "domaine", "note", "statut", "motif", "lien", "source", "publiee",
        "limite", "verifiee", "cv", "lettre", "canal", "envoi", "r1", "r2", "t", "contact", "notes"]
DATES = ("publiee", "limite", "verifiee", "envoi", "r1", "r2", "t")
LIBELLES = {1: "−1 profondeur technique insuffisante", 2: "−1 entreprise de taille moyenne peu connue",
            3: "−1 hors de Paris", 4: "−1 durée de 6 mois"}
STATUTS = ["Repérée", "À valider", "À envoyer", "Envoyée", "Relancée 1 fois", "Relancée 2 fois", "Adresse invalide",
           "Entretien ou échange", "Acceptée", "Refusée", "Sans réponse", "Abandonnée", "Expirée", "Incompatible"]
LISTES = {"domaine": ["Machine learning", "Vision par ordinateur", "NLP / LLM", "Apprentissage par renforcement",
                      "MLOps", "Données", "Logiciel", "Autre"],
          "source": ["Indeed", "LinkedIn", "Glassdoor", "Welcome to the Jungle", "JobTeaser", "Site carrière",
                     "Candidature spontanée", "Autre"],
          "cv": ["CV stage FR", "CV stage EN", "CV alternance"],
          "canal": ["Formulaire en ligne", "E-mail", "Indeed", "LinkedIn", "JobTeaser", "Autre"]}
ACTIFS = ("Envoyée", "Relancée 1 fois", "Relancée 2 fois", "Entretien ou échange")
AVANT_ENVOI = ("Repérée", "À valider", "À envoyer", "Incompatible", "Expirée")
APRES_ENVOI = ("Envoyée", "Relancée 1 fois", "Relancée 2 fois", "Adresse invalide", "Entretien ou échange",
               "Acceptée", "Refusée", "Sans réponse")
NOTE_OBLIGATOIRE = ("Repérée", "À valider", "À envoyer") + APRES_ENVOI
CATEGORIES = ("Durée", "Période", "Niveau", "Langue", "Compétence", "Droit de travail", "Lieu", "Hors data et IA",
              "Autre")


def en_date(v):
    """Numéro de série (export xlsx) ou texte jj/mm/aaaa : (date ou None, écrite comme du texte ?)."""
    if v in ("", None):
        return None, False
    try:
        f = float(v)
        if 20000 < f < 80000:
            return date(1899, 12, 30) + timedelta(days=int(f)), False
    except (TypeError, ValueError):
        pass
    m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*", str(v))
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))), True
        except ValueError:
            pass
    return None, True


def marqueur_suivi(notes):
    """(date, mal formé ?) du premier « Suivi prévu le jj/mm/aaaa », lu comme la formule de la colonne T
    (positions fixes)."""
    i = notes.lower().find("suivi prévu le ")
    if i < 0:
        return None, False
    try:
        return date(int(notes[i + 21:i + 25]), int(notes[i + 18:i + 20]), int(notes[i + 15:i + 17])), False
    except ValueError:
        return None, True


def t_attendu(l, b4):
    """Prochaine relance attendue, selon la règle 9 (même logique que la formule de la colonne T)."""
    if l["statut"] not in ACTIFS or not l["envoi"]:
        return None
    suivi, _ = marqueur_suivi(l["notes"])
    if suivi:
        return suivi
    if ("relances arrêtées" in l["notes"].lower() or l["statut"] in ("Relancée 2 fois", "Entretien ou échange")
            or l["r2"]):
        return None
    return l["envoi"] + timedelta(days=2 * b4 if l["r1"] else b4)


def lire(octets):
    onglets = doublons.lire_onglets(octets)
    b4 = 14
    bord = onglets.get("Tableau de bord", {})
    try:
        b4 = int(float(bord.get(4, {}).get(1, 14)))
    except (TypeError, ValueError):
        pass
    lignes, structure = [], []
    for nom, (maxi, permis, bareme) in ONGLETS.items():
        if nom not in onglets:
            structure.append("onglet « %s » absent" % nom)
            continue
        entetes = onglets[nom].get(1, {})
        for i, attendu in enumerate(ENTETES):
            vu = entetes.get(i, "").strip()
            if not vu.startswith(attendu):
                structure.append("%s : colonne %s « %s » au lieu de « %s »" % (nom, chr(65 + i), vu, attendu))
        if bareme not in entetes.get(5, ""):
            structure.append("%s : en-tête de F « %s » sans « %s »" % (nom, entetes.get(5, ""), bareme))
        for r, vals in sorted(onglets[nom].items()):
            if r == 1:
                continue
            brut = {k: str(vals.get(i, "")).strip() for i, k in enumerate(CLES)}
            if not (brut["org"] or brut["poste"] or brut["lien"] or brut["statut"]):
                continue
            l = dict(brut, onglet=nom, ligne=r, maxi=maxi, permis=permis, texte={})
            for k in DATES:
                l[k], l["texte"][k] = en_date(brut[k])
            lignes.append(l)
    return lignes, structure, b4


def controler(lignes, b4, aujourdhui):
    anomalies, verifs, afaire = [], [], []

    def ou(l):
        return "%s, ligne %d (%s, %s)" % (l["onglet"], l["ligne"], l["org"] or "?", l["poste"] or "?")

    for l in lignes:
        a = lambda msg, l=l: anomalies.append("%s : %s" % (ou(l), msg))
        v = lambda msg, l=l: verifs.append("%s : %s" % (ou(l), msg))
        statut, motif, notes = l["statut"], l["motif"], l["notes"]
        if statut not in STATUTS:
            a("statut « %s » hors de la liste" % statut)
        for k, liste in LISTES.items():
            if l[k] and l[k] not in liste:
                a("%s « %s » hors de la liste" % (k, l[k]))
        for k in DATES:
            if l["texte"][k]:
                a("date « %s » (%s) écrite comme du texte ou illisible" % ({"publiee": "Publiée le", "limite": "Date limite",
                  "verifiee": "Vérifiée le", "envoi": "Date d'envoi", "r1": "Relance 1 le", "r2": "Relance 2 le",
                  "t": "Prochaine relance"}[k], l[k] or "?"))
        if l["lien"] and not l["lien"].lower().startswith("http"):
            a("lien de l'offre qui n'est pas une URL")
        if l["lettre"] and not (l["lettre"].lower().startswith("http") or l["lettre"] == "Pas demandée"):
            a("Lettre ni lien ni « Pas demandée »")
        # Lieu et onglet
        pays = l["pays"]
        if l["onglet"] in ("Stage France", "Alternance") and pays and pays != "France":
            a("pays « %s » dans l'onglet %s" % (pays, l["onglet"]))
        if l["onglet"] == "Stage International" and pays == "France":
            a("offre en France dans l'onglet Stage International")
        # Note et motif
        criteres = [n for n, lib in LIBELLES.items() if lib in motif]
        if re.search(r"(?<![−\w])-1\b", motif):
            a("retrait écrit avec un tiret « -1 » au lieu du signe « −1 » (libellés fixes)")
        autres = [m for m in re.findall(r"−1 [^;(]+", motif) if not any(m.strip().startswith(x) for x in LIBELLES.values())]
        for m in autres:
            a("retrait « %s » qui n'est pas un des quatre libellés fixes" % m.strip())
        note = l["note"]
        if statut == "Incompatible":
            if note:
                a("note %s pour une offre Incompatible (la note doit être vide)" % note)
            if criteres:
                a("retraits de points dans le Motif d'une offre Incompatible")
            if not motif:
                a("Incompatible sans motif")
            elif not motif.startswith(CATEGORIES):
                a("motif d'incompatibilité sans catégorie (« Catégorie : précision »)")
        else:
            if note:
                try:
                    n = int(float(note))
                    if float(note) != n:
                        raise ValueError
                except ValueError:
                    a("note « %s » qui n'est pas un chiffre" % note)
                    n = None
                if n is not None:
                    if not 0 <= n <= l["maxi"]:
                        a("note %d hors de 0 à %d" % (n, l["maxi"]))
                    elif l["maxi"] - n != len(criteres):
                        a("note %d/%d alors que le Motif retire %d point(s) (%s)" % (
                            n, l["maxi"], len(criteres), ", ".join("critère %d" % c for c in criteres) or "aucun"))
            elif statut in NOTE_OBLIGATOIRE:
                a("note vide pour une offre au statut %s" % statut)
            for c in criteres:
                if c not in l["permis"]:
                    a("critère %d (« %s ») interdit dans l'onglet %s" % (c, LIBELLES[c], l["onglet"]))
            ville = doublons.norm_ville(l["ville"])
            if 3 in criteres and ville == "paris":
                a("« −1 hors de Paris » pour une offre à Paris")
            if (3 in l["permis"] and note and ville and ville != "paris" and 3 not in criteres
                    and "à vérifier : lieu" not in notes.lower()):
                v("offre hors de Paris (%s) sans « −1 hors de Paris » ni « À vérifier : lieu »" % l["ville"])
        # Statut et dates
        if statut in AVANT_ENVOI and l["envoi"]:
            a("date d'envoi alors que le statut est %s (un statut de candidature ne redevient pas un statut "
              "de recherche)" % statut)
        if statut in APRES_ENVOI and not l["envoi"]:
            a("statut %s sans date d'envoi" % statut)
        if statut == "Relancée 1 fois" and not l["r1"]:
            a("« Relancée 1 fois » sans date en Relance 1 le")
        if statut == "Relancée 2 fois" and not (l["r1"] and l["r2"]):
            a("« Relancée 2 fois » sans les deux dates de relance")
        if statut == "Envoyée" and (l["r1"] or l["r2"]):
            a("statut Envoyée alors qu'une relance est datée")
        if l["r2"] and not l["r1"]:
            a("Relance 2 le sans Relance 1 le")
        if (l["r1"] or l["r2"]) and not l["envoi"]:
            a("date de relance sans date d'envoi")
        if l["envoi"] and l["r1"] and l["r1"] < l["envoi"]:
            a("relance 1 antérieure à l'envoi")
        if l["r1"] and l["r2"] and l["r2"] < l["r1"]:
            a("relance 2 antérieure à la relance 1")
        if l["envoi"] and l["envoi"] > aujourdhui:
            a("date d'envoi dans le futur")
        if notes.lower().count("suivi prévu le") > 1:
            a("plusieurs marqueurs « Suivi prévu le » (un seul actif par ligne)")
        _, malforme = marqueur_suivi(notes)
        if malforme:
            a("marqueur « Suivi prévu le » sans date jj/mm/aaaa lisible (la colonne T l'ignore)")
        # Colonne T calculée
        attendu = t_attendu(l, b4)
        if l["t"] != attendu and not l["texte"]["t"]:
            a("Prochaine relance %s au lieu de %s attendu (formule cassée ou valeur écrite à la main ?)" % (
                l["t"].strftime("%d/%m/%Y") if l["t"] else "vide", attendu.strftime("%d/%m/%Y") if attendu else "vide"))
        # À faire
        if attendu and attendu <= aujourdhui:
            quoi = ("suivi convenu" if marqueur_suivi(notes)[0] else
                    "relance 2 (J+%d)" % (2 * b4) if l["r1"] else "relance 1 (J+%d)" % b4)
            afaire.append("%s : %s dû le %s" % (ou(l), quoi, attendu.strftime("%d/%m/%Y")))
        if (statut in ACTIFS[:3] and l["envoi"] and l["envoi"] <= aujourdhui - timedelta(days=3 * b4)
                and not (attendu and attendu > aujourdhui)):
            afaire.append("%s : J+%d atteint, proposer « Sans réponse » au candidat" % (ou(l), 3 * b4))
        if statut in ("Repérée", "À valider", "À envoyer") and l["limite"] and l["limite"] < aujourdhui:
            afaire.append("%s : date limite dépassée (%s), à passer en Expirée" % (ou(l), l["limite"].strftime("%d/%m/%Y")))
    # Doublons à l'intérieur du tableau
    vues = []
    for l in lignes:
        liens = [l["lien"]] + [u.rstrip(".:!?") for u in doublons.URL_RE.findall(l["notes"])]
        liens = [u for u in liens if u.lower().startswith("http")]
        ids = set()
        for u in liens:
            ids |= doublons.identifiants(u)
        vues.append({"onglet": l["onglet"], "ligne": l["ligne"], "organisation": l["org"], "poste": l["poste"],
                     "ville": l["ville"], "lien": l["lien"], "notes": l["notes"],
                     "publiee": l["publiee"].strftime("%d/%m/%Y") if l["publiee"] else "",
                     "liens_norm": {doublons.normaliser_url(u) for u in liens}, "ids": ids})
    for i, x in enumerate(vues):
        for y in vues[i + 1:]:
            offre = {"url": x["lien"], "entreprise": x["organisation"], "intitule": x["poste"], "ville": x["ville"],
                     "publiee": x["publiee"]}
            verdict, raisons = doublons.comparer(offre, y)
            if verdict in ("doublon certain", "doublon probable"):
                (anomalies if verdict == "doublon certain" else verifs).append(
                    "%s, ligne %d et %s, ligne %d (%s, %s) : %s dans le tableau (%s)" % (
                        x["onglet"], x["ligne"], y["onglet"], y["ligne"], x["organisation"], x["poste"], verdict,
                        " ; ".join(raisons)))
    return anomalies, verifs, afaire


def rapport(nb, structure, anomalies, verifs, afaire, b4, aujourdhui):
    out = ["Tableau lu : %d ligne(s) remplie(s) ; délai de relance B4 = %d jours ; date du contrôle %s." % (
        nb, b4, aujourdhui.strftime("%d/%m/%Y"))]
    for titre, liste in (("STRUCTURE", structure), ("ANOMALIES", anomalies), ("À VÉRIFIER", verifs), ("À FAIRE", afaire)):
        out.append("")
        out.append("%s : %s" % (titre, len(liste) if liste else "aucune" if titre != "À FAIRE" else "rien"))
        out += ["  - " + x for x in liste]
    return "\n".join(out)


# ---------------------------------------------------------------- auto-test

def _classeur(onglets):
    """Petit classeur au format de l'export Google, plusieurs onglets, valeurs en chaînes partagées."""
    m, partages = doublons.NS["m"], []

    def s(x):
        if x not in partages:
            partages.append(x)
        return partages.index(x)
    esc = lambda x: x.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    feuilles, decl, rels = [], [], []
    for k, (nom, lignes) in enumerate(onglets.items(), start=1):
        rows = []
        for r, vals in enumerate(lignes, start=1):
            cells = []
            for i, v in enumerate(vals):
                if v == "" or v is None:
                    continue
                ref = "%s%d" % (chr(65 + i), r)
                if isinstance(v, (int, float)):
                    cells.append('<c r="%s"><v>%s</v></c>' % (ref, v))
                else:
                    cells.append('<c r="%s" t="s"><v>%d</v></c>' % (ref, s(v)))
            rows.append('<row r="%d">%s</row>' % (r, "".join(cells)))
        feuilles.append('<worksheet xmlns="%s"><sheetData>%s</sheetData></worksheet>' % (m, "".join(rows)))
        decl.append('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (esc(nom), k, k))
        rels.append('<Relationship Id="rId%d" Type="worksheet" Target="worksheets/sheet%d.xml"/>' % (k, k))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", '<workbook xmlns="%s" xmlns:r="%s"><sheets>%s</sheets></workbook>' % (
            m, doublons.NS["r"], "".join(decl)))
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="%s">%s</Relationships>' % (
            doublons.NS["pr"], "".join(rels)))
        for k, f in enumerate(feuilles, start=1):
            z.writestr("xl/worksheets/sheet%d.xml" % k, f)
        z.writestr("xl/sharedStrings.xml", '<sst xmlns="%s">%s</sst>' % (
            m, "".join("<si><t>%s</t></si>" % esc(x) for x in partages)))
    return buf.getvalue()


def _entetes(bareme):
    return [e if e != "Pertinence" else "Pertinence (%s)" % bareme for e in ENTETES[:19]] + \
        ["Prochaine relance (calculée)", "Contact", "Notes"]


def selftest():
    j = date(2026, 10, 11)
    ser = lambda d: (d - date(1899, 12, 30)).days
    jm = lambda n: ser(j - timedelta(days=n))

    def ligne(org, poste, ville, pays, note, statut, motif, lien, q="", r1="", r2="", t="", notes="", limite=""):
        return [org, poste, ville, pays, "Machine learning", note, statut, motif, lien, "Site carrière", "", limite,
                "", "", "", "", q, r1, r2, t, "", notes]
    fr = [_entetes("sur 4"),
          ligne("Thales", "Stage deep learning", "Paris", "France", 4, "Repérée", "", "https://careers.thales.com/job/R1"),
          ligne("Safran", "Stage nettoyage de données", "Vélizy-Villacoublay", "France", 2, "Repérée",
                "−1 profondeur technique insuffisante (nettoyage seulement) ; −1 hors de Paris (Vélizy-Villacoublay)",
                "https://safran.example/job/2"),
          ligne("Inconnue SAS", "Stage data", "Paris", "France", 3, "Repérée", "", "https://x.example/job/3"),
          ligne("Atos", "Stage IA", "Paris", "France", 3, "Repérée", "−1 hors de Paris (Paris)", "https://atos.example/4"),
          ligne("Thales", "Stage deep learning", "Paris", "France", 4, "Repérée", "",
                "https://careers.thales.com/job/R1?utm_source=linkedin"),
          ligne("EDF", "Stage ML", "Paris", "France", 4, "Envoyée", "", "https://edf.example/6", q=jm(14), t=ser(j)),
          ligne("ENGIE", "Stage ML", "Paris", "France", 4, "Relancée 1 fois", "", "https://engie.example/7",
                q=jm(28), r1=jm(14), t=ser(j)),
          ligne("Valeo", "Stage ML", "Paris", "France", 4, "Envoyée", "", "https://valeo.example/8", q=jm(28), t=jm(14)),
          ligne("Orange", "Stage ML", "Paris", "France", 4, "Refusée", "", "https://orange.example/9", q=jm(20)),
          ligne("SFR", "Stage ML", "Paris", "France", 4, "Relancée 1 fois", "", "https://sfr.example/10", q=jm(20),
                t=jm(6)),
          ligne("BNP Paribas", "Stage ML", "Paris", "France", 4, "Entretien ou échange", "", "https://bnp.example/11",
                q=jm(20), t=ser(j + timedelta(days=5)), notes="Suivi prévu le %s : réponse annoncée" %
                (j + timedelta(days=5)).strftime("%d/%m/%Y")),
          ligne("AXA", "Stage ML", "Paris", "France", 4, "Relancée 2 fois", "", "https://axa.example/12", q=jm(42),
                r1=jm(28), r2=jm(14))]
    intl = [_entetes("sur 3"),
            ligne("Sony", "AI research intern", "Tokyo", "Japon", 3, "Repérée", "", "https://sony.example/1"),
            ligne("Samsung", "ML intern", "Séoul", "Corée du Sud", 2, "Repérée", "−1 durée de 6 mois (6 months)",
                  "https://samsung.example/2"),
            ligne("NAVER", "ML intern", "Séoul", "Corée du Sud", 2, "Repérée", "−1 hors de Paris (Séoul)",
                  "https://naver.example/3")]
    alt = [_entetes("sur 4"),
           ligne("IBM", "Alternance data", "Paris", "France", "", "Incompatible", "Durée : 24 mois", "https://ibm.example/1")]
    bord = [["Suivi"], [""], [""], ["Délai", 14]]
    octets = _classeur({"Tableau de bord": bord, "Stage France": fr, "Stage International": intl, "Alternance": alt})
    lignes, structure, b4 = lire(octets)
    anomalies, verifs, afaire = controler(lignes, b4, j)
    texte = "\n".join(structure + anomalies + verifs + afaire)
    echecs = 0

    def attendre(cond, msg):
        nonlocal echecs
        echecs += not cond
        print(("ok    " if cond else "ÉCHEC ") + msg)
    attendre(not structure, "structure des trois onglets reconnue")
    attendre(b4 == 14, "délai B4 lu dans le Tableau de bord")
    attendre("ligne 2 (Thales" not in "\n".join(anomalies), "cas 1 : Paris, vrai travail sur des modèles, 4/4 sans anomalie")
    attendre("ligne 3 (Safran" not in "\n".join(anomalies), "cas 2 : hors de Paris et nettoyage seul, 2/4 cohérent")
    attendre(any("ligne 4 (Inconnue SAS" in x and "note 3/4" in x for x in anomalies),
             "note 3/4 sans retrait écrit : signalée")
    attendre(any("ligne 5 (Atos" in x and "pour une offre à Paris" in x for x in anomalies),
             "« −1 hors de Paris » pour Paris : signalé")
    attendre(any("ligne 2 et Stage France, ligne 6" in x and "doublon certain" in x for x in anomalies),
             "cas 6 : même offre sous un autre lien (paramètre de suivi) : doublon interne signalé")
    attendre(any("ligne 7 (EDF" in x and "relance 1" in x for x in afaire), "cas 9 : J+14 sans réponse, relance 1 due")
    attendre(any("ligne 8 (ENGIE" in x and "relance 2" in x for x in afaire), "cas 10 : J+28, relance 1 faite, relance 2 due")
    attendre(any("ligne 9 (Valeo" in x and "relance 1 (J+14) dû le %s" % (j - timedelta(days=14)).strftime("%d/%m/%Y") in x
                 for x in afaire), "cas 11 : relance 1 jamais faite, seule la relance 1 est proposée, pas la 2")
    attendre(not any("ligne 10 (Orange" in x for x in afaire + anomalies), "cas 12 : refusée, aucune relance")
    attendre(any("ligne 11 (SFR" in x and "sans date en Relance 1 le" in x for x in anomalies),
             "« Relancée 1 fois » sans preuve : signalé")
    attendre(not any("ligne 12 (BNP" in x for x in afaire + anomalies), "date convenue avec le recruteur : prioritaire, pas encore due")
    attendre(any("ligne 13 (AXA" in x and "Sans réponse" in x for x in afaire), "J+42 après la relance 2 : « Sans réponse » proposé")
    attendre(not any("ligne 13 (AXA" in x and "relance" in x.lower() and "dû" in x for x in afaire), "aucune 3e relance")
    attendre(not any("Stage International, ligne 2 " in x or "Stage International, ligne 3 " in x for x in anomalies),
             "cas 3 et 4 : étranger 3/3, et 6 mois explicites à 2/3")
    attendre(any("Stage International, ligne 4" in x and "critère 3" in x for x in anomalies),
             "critère 3 à l'étranger : signalé")
    attendre(not any("Alternance" in x for x in anomalies), "Incompatible avec catégorie et note vide : accepté")
    if echecs:
        print(texte)
    print("selftest :", "réussi" if not echecs else "%d échec(s)" % echecs)
    return 1 if echecs else 0


def main(argv):
    if "--selftest" in argv:
        return selftest()
    args = [a for a in argv if not a.startswith("--")]
    aujourdhui = date.today()
    if "--aujourdhui" in argv:
        valeur = argv[argv.index("--aujourdhui") + 1]
        aujourdhui = datetime.strptime(valeur, "%d/%m/%Y").date()
        args.remove(valeur)
    if len(args) != 1:
        print(__doc__)
        return 2
    try:
        lignes, structure, b4 = lire(doublons.charger_xlsx(args[0]))
    except Exception as e:  # tableau illisible : ne rien conclure
        print("ERREUR : tableau illisible (%s). Aucun contrôle n'a pu être fait ; le dire au candidat." % e)
        return 2
    anomalies, verifs, afaire = controler(lignes, b4, aujourdhui)
    if "--json" in argv:
        print(json.dumps({"lignes_lues": len(lignes), "structure": structure, "anomalies": anomalies,
                          "a_verifier": verifs, "a_faire": afaire}, ensure_ascii=False, indent=1))
    else:
        print(rapport(len(lignes), structure, anomalies, verifs, afaire, b4, aujourdhui))
    return 1 if (structure or anomalies) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

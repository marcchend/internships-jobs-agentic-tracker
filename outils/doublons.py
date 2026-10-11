"""Contrôle des offres déjà enregistrées (doublons), règles du projet.

Compare des offres trouvées pendant une recherche au tableau de suivi, AVANT leur analyse détaillée.

Usage :
  python3 -I doublons.py TABLEAU OFFRES.json [--json]
  python3 -I doublons.py --selftest

TABLEAU : export xlsx du tableau de suivi (Drive, download_file_content, exportMimeType
  application/vnd.openxmlformats-officedocument.spreadsheetml.sheet), ou directement le fichier
  de résultat de cet outil (JSON contenant le xlsx en base64).
OFFRES.json : liste d'offres trouvées, par exemple
  [{"url": "...", "url_candidature": "...", "reference": "R12345", "entreprise": "Thales",
    "intitule": "Stage Data Scientist", "ville": "Paris", "pays": "France", "publiee": "08/10/2026"}]
  (url, ou entreprise et intitule, suffisent ; les autres champs aident la comparaison).

Verdicts, du plus sûr au moins sûr :
  doublon certain               même lien normalisé, même identifiant de plateforme, ou même référence chez la même entreprise
  doublon probable              même entreprise, intitulé presque identique, lieu compatible (vérifier avant de conclure)
  à vérifier                    ressemblance partielle : vérification ciblée, puis demander au candidat si le doute reste
  même entreprise, autre poste  entreprise déjà présente, poste différent : offre nouvelle a priori
  nouvelle                      aucune ligne comparable

Les verdicts guident le contrôle ; ils ne remplacent pas la vérification des cas B et C de
« Contrôle des offres déjà enregistrées » (profil-et-regles.md).
Code de sortie : 0 si le tableau a été lu, 2 si le tableau ou la liste d'offres est illisible
(alors ne présenter aucune offre comme définitivement nouvelle).
"""
import base64
import io
import json
import re
import sys
import unicodedata
import zipfile
from datetime import date, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from xml.etree import ElementTree as ET

ONGLETS = ("Stage France", "Stage International", "Alternance")
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "pr": "http://schemas.openxmlformats.org/package/2006/relationships"}

# Paramètres de suivi : retirés. Tout autre paramètre est gardé (on ne retire jamais tout).
SUIVI = {
    "gclid", "fbclid", "msclkid", "dclid", "yclid", "gbraid", "wbraid", "mc_cid", "mc_eid", "_hsenc", "_hsmi",
    "trk", "trkinfo", "refid", "trackingid", "lipi", "midtoken", "midsig", "eid", "otptoken", "trackingcode",
    "src", "source", "ref", "referer", "referrer", "from", "origin", "share", "shared", "utm",
    "tk", "vjs", "advn", "adid", "sjdu", "acatk", "pub", "camk", "xkcb", "xpse", "xfps", "fccid", "iaid", "sid",
    "spa", "campaignid", "gh_src", "lever-source", "lever-origin", "lever-via", "position", "pagenum",
    "trackingtag", "cmp", "campaign", "medium", "lang", "locale", "hl",
}
# Paramètres qui identifient l'offre (gardés, et servent d'identifiant de plateforme).
ID_PARAMS = ("jk", "vjk", "currentjobid", "gh_jid", "jobid", "job_id", "reqid", "requisitionid",
             "career_job_req_id", "job", "id", "jobreqid", "postingid", "offerid", "ref_offre")
LOCALE_SEG = re.compile(r"^[a-z]{2}([-_][a-z]{2})?$", re.I)


def sans_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))


def normaliser_url(url):
    """Lien comparable : https, domaine en minuscules sans www., sans ancre ni barre finale,
    sans paramètres de suivi, paramètres restants triés, segment de langue initial retiré."""
    url = (url or "").strip().strip("<>\"'")
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    p = urlsplit(url)
    host = p.netloc.lower().split("@")[-1]
    host = re.sub(r":(80|443)$", "", host)
    if host.startswith("www."):
        host = host[4:]
    segs = [s for s in p.path.split("/") if s]
    if segs and LOCALE_SEG.match(segs[0]) and len(segs) > 1:
        segs = segs[1:]
    path = "/" + "/".join(segs) if segs else ""
    garder = []
    for k, v in parse_qsl(p.query, keep_blank_values=True):
        kl = k.lower()
        if kl.startswith("utm_") or kl in SUIVI:
            continue
        garder.append((kl, v))
    garder.sort()
    return urlunsplit(("https", host, path, urlencode(garder), ""))


def identifiants(url):
    """Identifiants de plateforme tirés d'un lien : ensemble de tuples (plateforme, id)."""
    ids = set()
    url = (url or "").strip()
    if not url:
        return ids
    if "://" not in url:
        url = "https://" + url
    p = urlsplit(url)
    host = p.netloc.lower()
    q = {k.lower(): v for k, v in parse_qsl(p.query, keep_blank_values=True)}
    path = p.path
    if "indeed." in host:
        for k in ("jk", "vjk"):
            if q.get(k):
                ids.add(("indeed", q[k].lower()))
    if "linkedin.com" in host:
        m = re.search(r"/jobs/view/(?:[^/]*?-)?(\d{6,})", path)
        if m:
            ids.add(("linkedin", m.group(1)))
        if q.get("currentjobid", "").isdigit():
            ids.add(("linkedin", q["currentjobid"]))
    if "myworkdayjobs.com" in host or "myworkdaysite.com" in host:
        last = [s for s in path.split("/") if s]
        if last:
            m = re.search(r"_([A-Za-z]{0,4}-?\d{3,}(?:[-_]\d+)?)$", last[-1])
            if m:
                ids.add(("workday", host.split(".")[0] + ":" + m.group(1).upper()))
    if q.get("gh_jid", "").isdigit():
        ids.add(("greenhouse", q["gh_jid"]))
    if "greenhouse.io" in host:
        m = re.search(r"/jobs/(\d+)", path)
        if m:
            ids.add(("greenhouse", m.group(1)))
    if "lever.co" in host:
        m = re.search(r"/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", path, re.I)
        if m:
            ids.add(("lever", m.group(1).lower()))
    if "ashbyhq.com" in host:
        m = re.search(r"/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", path, re.I)
        if m:
            ids.add(("ashby", m.group(1).lower()))
    if "smartrecruiters.com" in host:
        m = re.search(r"/(\d{9,})(?:-|$)", path)
        if m:
            ids.add(("smartrecruiters", m.group(1)))
    if "welcometothejungle.com" in host:
        m = re.search(r"/companies/([^/]+)/jobs/([^/?#]+)", path)
        if m:
            ids.add(("wttj", (m.group(1) + "/" + m.group(2)).lower()))
    if "jobteaser.com" in host:
        m = re.search(r"/job-offers/([0-9a-f]{8}-[0-9a-f-]{27}|\d{4,})", path, re.I)
        if m:
            ids.add(("jobteaser", m.group(1).lower()))
    if "taleo.net" in host and q.get("job"):
        ids.add(("taleo", host.split(".")[0] + ":" + q["job"].lower()))
    if q.get("career_job_req_id"):
        ids.add(("successfactors", host + ":" + q["career_job_req_id"]))
    # sites carrières courants (Phenom, Eightfold, iCIMS, Apple, Amazon…) : même domaine et même numéro
    # d'offre après un segment « job », quel que soit l'intitulé dans le lien
    m = re.search(r"/(?:jobs?|careers?-home/jobs|details|postings?|offres?|annonces?)/(\d{4,}(?:-\d+)?)(?:[-/]|$)",
                  path, re.I)
    if m:
        h = host[4:] if host.startswith("www.") else host
        ids.add(("site", h + ":" + m.group(1)))
    return ids


SUFFIXES = {"sa", "sas", "sasu", "sarl", "se", "inc", "ltd", "limited", "gmbh", "ag", "plc", "llc", "co", "corp",
            "corporation", "company", "group", "groupe", "holding", "france", "the", "et", "and", "cie"}


def norm_entreprise(s):
    s = re.sub(r"[^a-z0-9]+", " ", sans_accents(s).lower())
    toks = [t for t in s.split() if t not in SUFFIXES]
    return " ".join(toks)


def meme_entreprise(a, b):
    a, b = norm_entreprise(a), norm_entreprise(b)
    if not a or not b:
        return False
    if a == b:
        return True
    # « bnp paribas » et « bnp paribas cardif » : même groupe (à vérifier par l'appelant)
    return (" " + a + " ") in (" " + b + " ") or (" " + b + " ") in (" " + a + " ")


PHRASES = [("intelligence artificielle", "ai"), ("apprentissage automatique", "machine learning"),
           ("vision par ordinateur", "computer vision"), ("science des donnees", "data science"),
           ("traitement du langage naturel", "nlp"), ("traitement automatique du langage", "nlp")]
SYN = {"ia": "ai", "ml": "machine learning", "ingenieur": "engineer", "ingenieure": "engineer",
       "scientist": "science", "donnees": "data", "data scientist": "data science", "developpeur": "developer",
       "developpeuse": "developer", "analyste": "analyst", "chercheur": "researcher", "recherche": "research"}
VIDES = {"stage", "stagiaire", "intern", "internship", "alternance", "alternant", "alternante", "apprenti",
         "apprentie", "apprentissage", "apprenticeship", "h", "f", "m", "x", "hf", "fh", "de", "du", "des", "la", "le",
         "les", "en", "et", "a", "au", "aux", "pour", "d", "l", "un", "une", "the", "of", "and", "in", "for", "with",
         "on", "to", "mois", "months", "month", "2026", "2027", "2028", "offre", "poste", "cdi", "cdd", "stage:",
         "end", "study", "fin", "etudes", "pfe", "summer", "off", "cycle", "w", "mf", "all", "genders", "gender"}


def mots_intitule(s):
    s = sans_accents(s).lower()
    s = re.sub(r"\b[a-z]{0,4}-?\d{4,}\b", " ", s)  # références (JR-116529, R0271234) : pas des mots du poste
    for a, b in PHRASES:
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9+#]+", " ", s)
    out = set()
    for t in s.split():
        t = SYN.get(t, t)
        for u in t.split():
            if u in VIDES or re.fullmatch(r"\d{1,2}", u):
                continue
            if len(u) > 3 and u.endswith("s"):
                u = u[:-1]
            out.add(u)
    return out


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def norm_ville(s):
    s = sans_accents(s).lower()
    s = re.sub(r"\bcedex\b|\d+(er|e|eme)?\b|arrondissement", " ", s)
    s = re.sub(r"[^a-z]+", " ", s).strip()
    return s


def villes_compatibles(a, b):
    a, b = norm_ville(a), norm_ville(b)
    if not a or not b:
        return None  # inconnu : ni pour ni contre
    return a == b or a in b or b in a


# ---------------------------------------------------------------- lecture du tableau

def charger_xlsx(chemin):
    """Renvoie les octets du xlsx, que le fichier soit un xlsx ou un résultat JSON (base64)."""
    with open(chemin, "rb") as fh:
        brut = fh.read()
    if brut[:2] == b"PK":
        return brut
    texte = brut.decode("utf-8", "replace")
    # résultat d'outil : JSON (éventuellement imbriqué) contenant une longue chaîne base64
    candidats = []

    def parcourir(o):
        if isinstance(o, dict):
            for v in o.values():
                parcourir(v)
        elif isinstance(o, list):
            for v in o:
                parcourir(v)
        elif isinstance(o, str):
            if len(o) > 200:
                try:
                    parcourir(json.loads(o))
                except (ValueError, TypeError):
                    candidats.append(o)
    try:
        parcourir(json.loads(texte))
    except ValueError:
        candidats.append(texte)
    for c in sorted(candidats, key=len, reverse=True):
        m = re.search(r"[A-Za-z0-9+/=\s]{200,}", c)
        if not m:
            continue
        try:
            octets = base64.b64decode(re.sub(r"\s+", "", m.group(0)))
        except ValueError:
            continue
        if octets[:2] == b"PK":
            return octets
    raise ValueError("aucun classeur xlsx trouvé dans " + chemin)


def col_index(ref):
    lettres = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in lettres:
        n = n * 26 + ord(ch) - 64
    return n - 1


def lire_onglets(octets):
    z = zipfile.ZipFile(io.BytesIO(octets))
    partages = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            partages.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    cible = {r.get("Id"): r.get("Target") for r in rels.findall("pr:Relationship", NS)}
    onglets = {}
    for sh in wb.find("m:sheets", NS).findall("m:sheet", NS):
        nom = sh.get("name")
        rid = sh.get("{%s}id" % NS["r"])
        t = cible[rid].lstrip("/")
        chemin = t if t.startswith("xl/") else "xl/" + t
        racine = ET.fromstring(z.read(chemin))
        lignes = {}
        for row in racine.iter("{%s}row" % NS["m"]):
            r = int(row.get("r"))
            vals = {}
            for c in row.findall("m:c", NS):
                typ = c.get("t")
                v = c.find("m:v", NS)
                if typ == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter("{%s}t" % NS["m"]))
                elif v is None:
                    continue
                elif typ == "s":
                    val = partages[int(v.text)]
                else:
                    val = v.text or ""
                if val != "":
                    vals[col_index(c.get("r"))] = val
            if vals:
                lignes[r] = vals
        onglets[nom] = lignes
    return onglets


def date_txt(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v or ""
    if 20000 < f < 80000:
        return (date(1899, 12, 30) + timedelta(days=int(f))).strftime("%d/%m/%Y")
    return v


URL_RE = re.compile(r"https?://[^\s<>\"';,)\]]+", re.I)


def lignes_du_tableau(onglets):
    """Lignes remplies des trois onglets de candidatures, colonnes repérées par leur en-tête."""
    out = []
    trouves = [n for n in ONGLETS if n in onglets]
    if not trouves:
        raise ValueError("aucun des onglets " + ", ".join(ONGLETS) + " dans le classeur")
    for nom in trouves:
        lignes = onglets[nom]
        entetes = {v.strip(): k for k, v in lignes.get(1, {}).items()}

        def col(*noms, _e=entetes):
            for n in noms:
                for h, k in _e.items():
                    if h == n or h.startswith(n):
                        return k
            return None
        c = {"org": col("Organisation"), "poste": col("Poste"), "ville": col("Ville"), "pays": col("Pays"),
             "note": col("Pertinence"), "statut": col("Statut"), "motif": col("Motif"), "lien": col("Lien de l'offre"),
             "publiee": col("Publiée le"), "envoi": col("Date d'envoi"), "notes": col("Notes")}
        manque = [k for k in ("org", "poste", "lien", "notes", "statut") if c[k] is None]
        if manque:
            raise ValueError("onglet %s : colonnes introuvables (%s)" % (nom, ", ".join(manque)))
        for r, vals in sorted(lignes.items()):
            if r == 1:
                continue
            g = lambda k: vals.get(c[k], "") if c[k] is not None else ""
            if not (g("org") or g("poste") or g("lien")):
                continue
            liens = [g("lien")] + [u.rstrip(".:!?") for u in URL_RE.findall(g("notes"))]
            liens = [u for u in liens if u.lower().startswith("http")]
            ids = set()
            for u in liens:
                ids |= identifiants(u)
            out.append({"onglet": nom, "ligne": r, "organisation": g("org"), "poste": g("poste"), "ville": g("ville"),
                        "pays": g("pays"), "note": re.sub(r"^(\d+)\.0$", r"\1", g("note")), "statut": g("statut"), "motif": g("motif"),
                        "lien": g("lien"), "publiee": date_txt(g("publiee")), "envoi": date_txt(g("envoi")),
                        "notes": g("notes"), "liens_norm": {normaliser_url(u) for u in liens}, "ids": ids})
    return out


# ---------------------------------------------------------------- comparaison

RANG = {"doublon certain": 4, "doublon probable": 3, "à vérifier": 2, "même entreprise, autre poste": 1, "nouvelle": 0}


def comparer(offre, ligne):
    """Verdict et raisons pour une offre trouvée face à une ligne du tableau."""
    raisons = []
    liens = [offre.get("url", ""), offre.get("url_candidature", "")]
    liens = [u for u in liens if u]
    norm = {normaliser_url(u) for u in liens}
    ids = set()
    for u in liens:
        ids |= identifiants(u)
    if norm & ligne["liens_norm"]:
        return "doublon certain", ["même lien après normalisation"]
    commun = ids & ligne["ids"]
    if commun:
        return "doublon certain", ["même identifiant " + ", ".join("%s %s" % x for x in sorted(commun))]
    ent = meme_entreprise(offre.get("entreprise", ""), ligne["organisation"])
    ref = (offre.get("reference") or "").strip()
    if ref and len(ref) >= 4:
        trouve = re.search(r"(?<![A-Za-z0-9])" + re.escape(ref) + r"(?![A-Za-z0-9])",
                           " ".join([ligne["poste"], ligne["lien"], ligne["notes"]]), re.I)
        if trouve and ent:
            return "doublon certain", ["même référence %s chez la même entreprise" % ref]
        if trouve:
            raisons.append("référence %s retrouvée, entreprise différente" % ref)
    if not ent:
        return ("à vérifier", raisons) if raisons else ("nouvelle", [])
    if norm_entreprise(offre.get("entreprise", "")) != norm_entreprise(ligne["organisation"]):
        raisons.append("même groupe probable (%s / %s)" % (offre.get("entreprise", ""), ligne["organisation"]))
    j = jaccard(mots_intitule(offre.get("intitule", "")), mots_intitule(ligne["poste"]))
    v = villes_compatibles(offre.get("ville", ""), ligne["ville"])
    raisons.append("intitulés semblables à %d %%" % round(100 * j))
    if v is False:
        raisons.append("lieux différents (%s / %s)" % (offre.get("ville", ""), ligne["ville"]))
    elif v is None:
        raisons.append("lieu inconnu d'un côté")
    pub = offre.get("publiee", "")
    if pub and ligne["publiee"] and pub != ligne["publiee"]:
        raisons.append("dates de publication différentes (%s / %s) : republication possible" % (pub, ligne["publiee"]))
    if j >= 0.8 and v is not False:
        return "doublon probable", raisons
    if j >= 0.5:
        return "à vérifier", raisons
    return "même entreprise, autre poste", raisons


def controler(offres, lignes):
    resultats = []
    for i, o in enumerate(offres):
        corresp = []
        for l in lignes:
            verdict, raisons = comparer(o, l)
            if verdict != "nouvelle":
                corresp.append({"verdict": verdict, "raisons": raisons, "onglet": l["onglet"], "ligne": l["ligne"],
                                "organisation": l["organisation"], "poste": l["poste"], "ville": l["ville"],
                                "statut": l["statut"], "note": l["note"], "publiee": l["publiee"],
                                "envoi": l["envoi"], "lien": l["lien"]})
        # même offre trouvée deux fois dans la même recherche (LinkedIn puis Indeed, par exemple)
        pseudo = {"onglet": "liste", "ligne": 0, "organisation": "", "poste": "", "ville": "", "pays": "",
                  "note": "", "statut": "", "motif": "", "lien": "", "publiee": "", "envoi": "", "notes": ""}
        for k, autre in enumerate(offres[:i]):
            liens = [u for u in (autre.get("url", ""), autre.get("url_candidature", "")) if u]
            p = dict(pseudo, organisation=autre.get("entreprise", ""), poste=autre.get("intitule", ""),
                     ville=autre.get("ville", ""), publiee=autre.get("publiee", ""),
                     notes=autre.get("reference", ""), liens_norm={normaliser_url(u) for u in liens},
                     ids=set().union(*[identifiants(u) for u in liens]) if liens else set())
            verdict, raisons = comparer(o, p)
            if RANG[verdict] >= 2:
                corresp.append({"verdict": verdict, "raisons": raisons + ["offre n° %d de la même liste" % (k + 1)],
                                "onglet": "liste", "ligne": k + 1, "organisation": p["organisation"],
                                "poste": p["poste"], "ville": p["ville"], "statut": "", "note": "",
                                "publiee": p["publiee"], "envoi": "", "lien": autre.get("url", "")})
        corresp.sort(key=lambda c: -RANG[c["verdict"]])
        verdict = corresp[0]["verdict"] if corresp else "nouvelle"
        resultats.append({"offre": i + 1, "entreprise": o.get("entreprise", ""), "intitule": o.get("intitule", ""),
                          "url": o.get("url", ""), "url_normalisee": normaliser_url(o.get("url", "")),
                          "verdict": verdict, "correspondances": corresp})
    return resultats


def rapport(resultats, nb_lignes):
    out = ["Tableau lu : %d ligne(s) remplie(s) dans les trois onglets." % nb_lignes]
    for r in resultats:
        out.append("")
        out.append("%d. %s, %s : %s" % (r["offre"], r["entreprise"] or "?", r["intitule"] or "?", r["verdict"].upper()))
        if r["url"]:
            out.append("   lien normalisé : " + r["url_normalisee"])
        for c in r["correspondances"][:5]:
            ou = "liste, offre n° %d" % c["ligne"] if c["onglet"] == "liste" else "%s, ligne %d" % (c["onglet"], c["ligne"])
            out.append("   - %s : %s (%s, %s, %s ; statut %s ; note %s)" % (
                c["verdict"], ou, c["organisation"], c["poste"], c["ville"], c["statut"] or "?", c["note"] or "vide"))
            out.append("     " + " ; ".join(c["raisons"]))
    return "\n".join(out)


# ---------------------------------------------------------------- auto-test

def _xlsx_test(lignes):
    """Petit classeur au format de l'export Google (chaînes partagées)."""
    entetes = ["Organisation", "Poste", "Ville", "Pays", "Domaine", "Pertinence (sur 4)", "Statut", "Motif",
               "Lien de l'offre", "Source", "Publiée le", "Date limite", "Vérifiée le", "CV", "Lettre", "Canal",
               "Date d'envoi", "Relance 1 le", "Relance 2 le", "Prochaine relance (calculée)", "Contact", "Notes"]
    partages = []

    def s(x):
        if x not in partages:
            partages.append(x)
        return partages.index(x)

    def lettre(i):
        return chr(65 + i)
    rows = []
    for r, vals in enumerate([entetes] + lignes, start=1):
        cells = []
        for i, v in enumerate(vals):
            if v == "":
                continue
            if isinstance(v, (int, float)):
                cells.append('<c r="%s%d"><v>%s</v></c>' % (lettre(i), r, v))
            else:
                cells.append('<c r="%s%d" t="s"><v>%d</v></c>' % (lettre(i), r, s(v)))
        rows.append('<row r="%d">%s</row>' % (r, "".join(cells)))
    esc = lambda x: x.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    m = NS["m"]
    feuille = '<worksheet xmlns="%s"><sheetData>%s</sheetData></worksheet>' % (m, "".join(rows))
    sst = '<sst xmlns="%s">%s</sst>' % (m, "".join("<si><t>%s</t></si>" % esc(x) for x in partages))
    wb = ('<workbook xmlns="%s" xmlns:r="%s"><sheets><sheet name="Stage France" sheetId="1" r:id="rId1"/>'
          '</sheets></workbook>' % (m, NS["r"]))
    rels = ('<Relationships xmlns="%s"><Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>' % NS["pr"])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/worksheets/sheet1.xml", feuille)
        z.writestr("xl/sharedStrings.xml", sst)
    return buf.getvalue()


def selftest():
    n = normaliser_url
    ok = 0

    def eq(a, b, msg):
        nonlocal ok
        assert a == b, "%s : %r != %r" % (msg, a, b)
        ok += 1
    eq(n("http://www.Example.com/jobs/123/?utm_source=linkedin&utm_medium=x#apply"),
       n("https://example.com/jobs/123"), "suivi, www, http, ancre, barre finale")
    eq(n("https://example.com/job?id=5&ref=abc"), "https://example.com/job?id=5", "ref retiré, id gardé")
    assert n("https://example.com/job?id=5") != n("https://example.com/job?id=6"), "id différent"
    ok += 1
    eq(n("https://example.com/job?b=2&a=1"), n("https://example.com/job?a=1&b=2"), "ordre des paramètres")
    eq(n("https://example.com/job?x=inconnu"), "https://example.com/job?x=inconnu", "paramètre inconnu gardé")
    eq(n("https://careers.example.com/fr/offres/data-123"), n("https://careers.example.com/en/offres/data-123"),
       "segment de langue")
    eq(identifiants("https://fr.indeed.com/viewjob?jk=ABC123def&from=serp&vjs=3"),
       {("indeed", "abc123def")}, "Indeed jk")
    eq(identifiants("https://fr.indeed.com/jobs?q=stage&vjk=abc123def"), {("indeed", "abc123def")}, "Indeed vjk")
    eq(identifiants("https://www.linkedin.com/jobs/view/stage-data-scientist-at-thales-4012345678/?trk=x"),
       {("linkedin", "4012345678")}, "LinkedIn avec intitulé")
    eq(identifiants("https://www.linkedin.com/jobs/search/?currentJobId=4012345678&keywords=stage"),
       {("linkedin", "4012345678")}, "LinkedIn currentJobId")
    eq(identifiants("https://thales.wd3.myworkdayjobs.com/fr-FR/Careers/job/Paris/Stage-IA_R0271234"),
       identifiants("https://thales.wd3.myworkdayjobs.com/en-US/Careers/job/Paris/AI-Internship_R0271234?source=LinkedIn"),
       "Workday, langue et intitulé différents")
    eq(("greenhouse", "7654321") in identifiants("https://boards.greenhouse.io/acme/jobs/7654321")
       & identifiants("https://acme.com/careers?gh_jid=7654321"), True, "Greenhouse")
    eq(identifiants("https://jobs.lever.co/acme/0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0/apply"),
       {("lever", "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")}, "Lever")
    eq(mots_intitule("Stage - Data Scientist (H/F) 6 mois"), mots_intitule("Data Science Internship"), "intitulés")
    eq(mots_intitule("Internship - AI Application Engineer (JR-116529)"), mots_intitule("AI Application Engineer Intern"),
       "référence retirée de l'intitulé")
    eq(identifiants("https://jobs.apple.com/en-us/details/200682900-3715/ai-project-operations-intern"),
       identifiants("https://jobs.apple.com/fr-fr/details/200682900-3715/stage?team=SFTWR"), "site carrière, autre intitulé")
    assert not identifiants("https://careers.example.com/jobs/1234") & identifiants("https://other.example.com/jobs/1234")
    ok += 1
    eq(meme_entreprise("Thales SA", "THALES"), True, "entreprise normalisée")
    eq(meme_entreprise("Thales", "Safran"), False, "entreprises différentes")
    eq(villes_compatibles("Paris 8e", "Paris"), True, "arrondissement")

    lignes_tab = [
        ["Thales", "Stage Data Scientist (H/F)", "Vélizy-Villacoublay", "France", "Machine learning", 3, "Repérée",
         "−1 hors de Paris (Vélizy-Villacoublay)", "https://careers.thalesgroup.com/fr/fr/job/R0271234/stage-data-scientist",
         "LinkedIn", 46303, "", 46306, "", "", "", "", "", "", "", "",
         "Mission : modèles de détection. Lien LinkedIn : https://www.linkedin.com/jobs/view/4012345678/"],
        ["Safran", "Stage Machine Learning - maintenance prédictive", "Paris", "France", "Machine learning", 4,
         "Envoyée", "", "https://safran.wd3.myworkdayjobs.com/fr-FR/Safran/job/Paris/Stage-ML_R00123", "Site carrière",
         46290, "", 46300, "CV stage FR", "", "Formulaire en ligne", 46301, "", "", "", "", "Mission : ML."],
    ]
    tab = lignes_du_tableau(lire_onglets(_xlsx_test(lignes_tab)))
    eq(len(tab), 2, "lecture du classeur")
    eq(tab[0]["publiee"], "08/10/2026", "date convertie")
    offres = [
        {"url": "https://www.linkedin.com/jobs/view/stage-data-scientist-at-thales-4012345678?trk=public_jobs",
         "entreprise": "Thales", "intitule": "Stage Data Scientist", "ville": "Vélizy"},
        {"url": "https://safran.wd3.myworkdayjobs.com/en-US/Safran/job/Paris/ML-Internship_R00123?source=Indeed",
         "entreprise": "Safran", "intitule": "ML Internship"},
        {"url": "https://example-job-board.com/o/999", "entreprise": "Thales SA",
         "intitule": "Stage - Data Scientist H/F", "ville": "Vélizy-Villacoublay", "publiee": "01/11/2026"},
        {"url": "https://careers.thalesgroup.com/fr/fr/job/R0279999/stage-cybersecurite", "entreprise": "Thales",
         "intitule": "Stage cybersécurité réseau", "ville": "Paris"},
        {"url": "https://jobs.example.org/42", "entreprise": "Dassault Systèmes", "intitule": "Stage IA générative"},
        {"url": "https://jobs.example.org/42?utm_campaign=x", "entreprise": "Dassault Systèmes",
         "intitule": "Stage IA générative"},
        {"url": "https://x.org/1", "entreprise": "Thales", "intitule": "Data Scientist Intern - Detection",
         "ville": "Brest"},
    ]
    res = controler(offres, tab)
    attendus = ["doublon certain", "doublon certain", "doublon probable", "même entreprise, autre poste",
                "nouvelle", "doublon certain", "à vérifier"]
    eq([r["verdict"] for r in res], attendus, "verdicts")
    assert any("republication" in x for x in res[2]["correspondances"][0]["raisons"]), "republication signalée"
    ok += 1
    eq(res[5]["correspondances"][0]["onglet"], "liste", "doublon dans la même liste")
    try:
        lignes_du_tableau({"Feuille 1": {1: {0: "x"}}})
        raise AssertionError("onglets absents non détectés")
    except ValueError:
        ok += 1
    print("Auto-test réussi : %d vérifications." % ok)


def main(argv):
    if "--selftest" in argv:
        selftest()
        return 0
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    try:
        lignes = lignes_du_tableau(lire_onglets(charger_xlsx(args[0])))
    except Exception as e:  # tableau illisible : ne rien présenter comme nouveau
        print("ERREUR : tableau illisible (%s). Aucune offre ne peut être présentée comme définitivement nouvelle ; "
              "le dire au candidat." % e)
        return 2
    try:
        with open(args[1], encoding="utf-8") as fh:
            offres = json.load(fh)
        if isinstance(offres, dict):
            offres = [offres]
    except Exception as e:
        print("ERREUR : liste d'offres illisible (%s)." % e)
        return 2
    res = controler(offres, lignes)
    if "--json" in argv:
        print(json.dumps({"lignes_lues": len(lignes), "resultats": res}, ensure_ascii=False, indent=1))
    else:
        print(rapport(res, len(lignes)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

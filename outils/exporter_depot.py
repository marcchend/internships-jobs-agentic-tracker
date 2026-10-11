"""Prépare le dépôt GitHub de la recherche de stage : une copie versionnée, sans données personnelles.

Usage :
  python3 -I exporter_depot.py PROJET DEPOT [--instructions FICHIER] [--taches FICHIER.json]
                               [--tableau FICHIER.xlsx] [--neutralisation FICHIER.json]
  python3 -I exporter_depot.py --verifier DEPOT [--neutralisation FICHIER.json]
  python3 -I exporter_depot.py --selftest

PROJET : dossier du projet, celui qui contient profil-et-regles.md, pistes.md et outils/.
  Il reste la référence : le dépôt en est une copie, à régénérer après chaque changement de règles.
DEPOT : dossier du dépôt. Seuls les fichiers générés y sont réécrits :
  regles.md (profil-et-regles.md sans les sections « Liens » et « Profil »), outils/*.py, et, si
  fournis, instructions.md (instructions du projet), taches-planifiees/*.md (JSON de list_triggers)
  et config/modele-tableau.xlsx (export xlsx du tableau, refusé s'il contient une offre).
  README.md, CLAUDE.md, docs/, skills/ et les modèles de config/ s'écrivent à la main.
Le profil, les liens et identifiants, pistes.md, les lettres et le CV ne sont jamais copiés.

Dans les textes générés, les identifiants sont masqués : tableau <ID_TABLEAU>, dossier des lettres
<ID_DOSSIER_LETTRES>, autres fichiers Drive <ID_DRIVE>, tâches <ID_TACHE>, adresses <EMAIL>,
téléphones <TELEPHONE> ; les chemins du dossier du projet deviennent relatifs au dépôt.

Neutralisation (facultative) : un fichier JSON, gardé hors du dépôt puisqu'il cite ce qu'il retire,
rend les fichiers générés anonymes (règles, instructions, tâches, outils, notes du modèle de tableau).
Sans --neutralisation, PROJET/depot-sources/neutralisation.json est utilisé s'il existe. Clés :
  "lignes_retirees"     expressions : toute ligne de la source qui en contient une est retirée ;
  "sections_remplacees" { début du titre « ## » : nouveau texte de la section, sous son titre } ;
  "operations"          liste ordonnée : [motif, remplacement] remplace ; [motif] retire, avec la
                        ponctuation qui l'entoure entre parenthèses (« (motif ; suite) » → « (suite) ») ;
  "interdits"           mots qui ne doivent apparaître nulle part dans le dépôt (casse ignorée).
Les motifs sont des expressions régulières Python, appliquées ligne par ligne (^ et $ par ligne).

Ensuite, tout le dépôt (hors fichiers ignorés par .gitignore) est contrôlé : adresse mail, téléphone,
identifiant Drive, de tâche ou de session, lien de profil LinkedIn, chemin de dossier partagé et,
avec une neutralisation, chacun des mots interdits.
Code de sortie : 0 si rien n'est trouvé, 1 sinon (liste affichée), 2 si une entrée manque.
"""
import fnmatch
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

SECTIONS_PERSO = ("Liens", "Profil")
SECTIONS_REQUISES = (  # citées par CLAUDE.md, skills/ et docs/ (titres après neutralisation)
    "Ce que le candidat cherche", "Hiérarchie des entreprises", "Évaluation technique des offres",
    "Accessibilité des offres", "Méthode de recherche d'offres",
    "Contrôle des offres déjà enregistrées", "Règles", "Tableau de suivi",
    "Procédure : lot hebdomadaire", "Procédure : envoi après l'OK du candidat",
    "Procédure : relances et réponses",
)
ONGLETS = ("Stage France", "Stage International", "Alternance")
TACHES = {"Lot hebdomadaire de candidatures": "lot-hebdomadaire.md",
          "Relances et réponses": "relances-et-reponses.md"}
ENTETE = ("> Fichier généré par `outils/exporter_depot.py` depuis {source}, qui fait foi. "
          "Ne pas le modifier ici : le modifier à la source, puis régénérer.\n")

ID_DRIVE = re.compile(r"(?<![\w-])(?=[\w-]*\d)(?=[\w-]*[a-z])(?=[\w-]*[A-Z])[\w-]{25,}(?![\w-])")
UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
TEL = re.compile(r"\+\d{2}[\s()\d]{8,}\d|\b0[1-9](?:[\s.]?\d{2}){4}\b")
ID_SESSION = re.compile(r"\b(?:trig|session|cse|cmsg|chan|user)_[A-Za-z0-9]{10,}")
LINKEDIN = re.compile(r"linkedin\.com/in/(?!<)[\w%-]+", re.I)
CHEMIN = re.compile(r"/mnt/[\w.-]+")
EXEMPLES = ("@exemple.", "@example.")
FICHIERS_TEXTE = (".md", ".py", ".txt", ".csv", ".json", ".yml", ".yaml", ".toml", ".gitignore")


def exemple(adresse):
    return any(e in adresse for e in EXEMPLES)


def sections(texte):
    """Découpe un Markdown en (préambule, [(titre, bloc)]) selon les titres « ## »."""
    morceaux = re.split(r"(?m)^(?=## )", texte)
    pre, blocs = morceaux[0], []
    for m in morceaux[1:]:
        blocs.append((m.split("\n", 1)[0][3:].strip(), m))
    return pre, blocs


def identifiants(liens):
    """Repère, dans la section « Liens », l'identifiant du tableau et celui du dossier des lettres."""
    ids = {}
    m = re.search(r"/spreadsheets/d/([\w-]+)", liens)
    if m:
        ids[m.group(1)] = "<ID_TABLEAU>"
    m = re.search(r"/drive/folders/([\w-]+)", liens)
    if m:
        ids[m.group(1)] = "<ID_DOSSIER_LETTRES>"
    return ids


def masquer(texte, ids, projet):
    for ident, nom in ids.items():
        texte = texte.replace(ident, nom)
    texte = ID_DRIVE.sub("<ID_DRIVE>", texte)
    texte = UUID.sub("<ID>", texte)
    texte = ID_SESSION.sub(lambda m: "<ID_TACHE>" if m.group(0).startswith("trig_") else "<ID>", texte)
    texte = EMAIL.sub(lambda m: m.group(0) if exemple(m.group(0)) else "<EMAIL>", texte)
    texte = TEL.sub("<TELEPHONE>", texte)
    texte = LINKEDIN.sub("linkedin.com/in/<PROFIL>", texte)
    if projet:
        texte = texte.replace(projet.rstrip("/") + "/", "")
        texte = texte.replace(os.path.dirname(projet.rstrip("/")) + "/", "")
    texte = CHEMIN.sub("<DOSSIER>", texte)
    texte = texte.replace("recherche-stage/outils/", "outils/").replace("recherche-stage/pistes.md", "pistes.md")
    texte = texte.replace("recherche-stage/profil-et-regles.md", "regles.md (et config/profil.md pour le profil)")
    return texte.replace("profil-et-regles.md", "regles.md")


def charger_neutralisation(chemin):
    if not chemin:
        return None
    with open(chemin, encoding="utf-8") as f:
        r = json.load(f)
    return {
        "lignes": [re.compile(p) for p in r.get("lignes_retirees", [])],
        "sections": r.get("sections_remplacees", {}),
        "operations": [(re.compile(o[0], re.M), o[1] if len(o) > 1 else None) for o in r.get("operations", [])],
        "interdits": [re.compile(r"(?<![\w-])%s(?![\w-])" % re.escape(m), re.I) for m in r.get("interdits", [])],
    }


def neutraliser(texte, neutre, lignes=True):
    """Applique les règles de neutralisation (voir l'en-tête) ; sans règles, rend le texte inchangé.
    lignes=False pour du XML, souvent écrit sur une seule ligne : seules les opérations s'appliquent."""
    if not neutre:
        return texte
    if lignes:
        texte = "\n".join(l for l in texte.split("\n") if not any(p.search(l) for p in neutre["lignes"]))
    for motif, remplacement in neutre["operations"]:
        if remplacement is not None:
            texte = motif.sub(remplacement, texte)
            continue
        m = "(?:%s)" % motif.pattern
        texte = re.sub(r" ?\(%s\)" % m, "", texte, flags=re.M)             # « (motif) » entier
        texte = re.sub(r"\(%s(?: ;|,) " % m, "(", texte, flags=re.M)        # « (motif ; suite) »
        texte = re.sub(r"(?: ;|,) %s(?=\)| ;)" % m, "", texte, flags=re.M)  # « (début ; motif) »
        texte = motif.sub("", texte)
    return texte


def ecrire(chemin, contenu):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)
    print("écrit :", "/".join(chemin.replace(os.sep, "/").split("/")[-2:]))


def generer_regles(projet, depot, neutre=None):
    with open(os.path.join(projet, "profil-et-regles.md"), encoding="utf-8") as f:
        texte = f.read()
    pre, blocs = sections(texte)
    titres = [neutraliser(t, neutre) for t, _ in blocs]
    manque = [s for s in SECTIONS_REQUISES if not any(t.startswith(s) for t in titres)]
    if manque:
        raise SystemExit("Sections absentes de profil-et-regles.md : %s (mettre à jour SECTIONS_REQUISES, "
                         "CLAUDE.md, skills/ et docs/, ou la neutralisation)." % ", ".join(manque))
    liens = "".join(b for t, b in blocs if t.startswith("Liens"))
    ids = identifiants(liens)
    remplacees = (neutre or {}).get("sections", {})
    garde = []
    for t, b in blocs:
        if t.startswith(SECTIONS_PERSO):
            continue
        debut = [d for d in remplacees if t.startswith(d)]
        if debut:
            b = b.split("\n", 1)[0] + "\n" + remplacees[debut[0]].strip() + "\n\n"
        garde.append(neutraliser(b, neutre))
    intro = neutraliser(pre.split("\n", 1)[1].strip() if "\n" in pre else "", neutre)
    sortie = ("# Règles et procédures de la recherche de stage et d'alternance\n\n"
              + ENTETE.format(source="`profil-et-regles.md` (dossier du projet)")
              + "> Les sections personnelles (« Liens », « Profil ») restent hors de Git : voir "
                "`config/liens.exemple.md` et `config/profil.exemple.md`. En cas de contradiction, "
                "`instructions.md` prime.\n\n"
              + masquer(intro + "\n\n" + "".join(garde).rstrip() + "\n", ids, projet))
    ecrire(os.path.join(depot, "regles.md"), sortie)
    return ids


def generer_outils(projet, depot, neutre=None):
    src = os.path.join(projet, "outils")
    for nom in sorted(os.listdir(src)):
        if nom.endswith(".py"):
            if not neutre:
                shutil.copyfile(os.path.join(src, nom), os.path.join(depot, "outils", nom))
                print("copié :", "outils/" + nom)
                continue
            with open(os.path.join(src, nom), encoding="utf-8") as f:
                ecrire(os.path.join(depot, "outils", nom), neutraliser(f.read(), neutre))


def generer_instructions(fichier, depot, ids, projet, neutre=None):
    with open(fichier, encoding="utf-8") as f:
        texte = neutraliser(f.read(), neutre).strip()
    titre, corps = texte.split("\n", 1)
    sortie = (titre + "\n\n" + ENTETE.format(source="les instructions du projet Claude (réglages du projet)")
              + "\n" + masquer(corps.strip() + "\n", ids, projet))
    ecrire(os.path.join(depot, "instructions.md"), sortie)


def generer_taches(fichier, depot, ids, projet, neutre=None):
    with open(fichier, encoding="utf-8") as f:
        taches = json.load(f)
    if isinstance(taches, dict):
        taches = taches.get("data", [])
    for t in taches:
        nom = t["name"]
        if nom not in TACHES:
            print("tâche ignorée (inconnue) :", nom)
            continue
        prompt = t.get("prompt") or t.get("derived_state", {}).get("prompt", "")
        cron = t["cron_expression"]
        m = re.match(r"CRON_TZ=(\S+) (\d+) (\d+) \* \* (\*|\d)", cron)
        quand = cron
        if m:
            jour = "tous les jours" if m.group(4) == "*" else ("le lundi" if m.group(4) == "1" else "jour %s" % m.group(4))
            quand = "%s à %sh%02d (%s)" % (jour, m.group(3), int(m.group(2)), m.group(1))
        sortie = ("# Tâche planifiée : %s\n\n" % nom
                  + ENTETE.format(source="la tâche planifiée du même nom dans le projet Claude")
                  + "\nPlanification : %s, expression `%s`. Le texte ci-dessous est le prompt complet, "
                    "envoyé tel quel à chaque exécution.\n\n---\n\n" % (quand, cron)
                  + masquer(neutraliser(prompt, neutre).strip() + "\n", ids, projet))
        ecrire(os.path.join(depot, "taches-planifiees", TACHES[nom]), sortie)


NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def onglets_xlsx(z):
    wb = z.read("xl/workbook.xml").decode("utf-8")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    cible = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    cible.update({k: v for v, k in re.findall(r'Target="([^"]+)"[^>]*Id="([^"]+)"', rels)})
    res = {}
    for nom, rid in re.findall(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wb):
        res[nom] = "xl/" + cible[rid].lstrip("/").replace("xl/", "", 1)
    return res


def verifier_modele(fichier):
    """Refuse un export qui contient des lignes remplies (le modèle doit être vide)."""
    with zipfile.ZipFile(fichier) as z:
        feuilles = onglets_xlsx(z)
        for onglet in ONGLETS:
            # Lecture XML (une expression régulière sur <c …/> vides parcourait tout le fichier à chaque cellule).
            racine = ET.fromstring(z.read(feuilles[onglet]))
            for c in racine.iter(NS + "c"):
                col, ligne = re.match(r"([A-Z]+)(\d+)$", c.get("r")).groups()
                if int(ligne) > 1 and col != "T" and (c.find(NS + "v") is not None or c.find(NS + "is") is not None):
                    raise SystemExit("Le tableau contient des données (%s!%s%s) : modèle refusé." % (onglet, col, ligne))


def generer_tableau(fichier, depot, neutre=None):
    verifier_modele(fichier)
    cible = os.path.join(depot, "config", "modele-tableau.xlsx")
    if not neutre:
        shutil.copyfile(fichier, cible)
        print("copié : config/modele-tableau.xlsx")
        return
    # Notes des en-têtes, textes et propriétés : seules les parties XML changées sont réécrites.
    with zipfile.ZipFile(fichier) as src, zipfile.ZipFile(cible + ".tmp", "w") as dst:
        for info in src.infolist():
            donnees = src.read(info.filename)
            if info.filename.endswith((".xml", ".rels")):
                texte = donnees.decode("utf-8")
                neutre_xml = neutraliser(texte, neutre, lignes=False)
                if neutre_xml != texte:
                    ET.fromstring(neutre_xml.encode("utf-8"))  # le XML doit rester valide
                    donnees = neutre_xml.encode("utf-8")
            dst.writestr(info, donnees)
    os.replace(cible + ".tmp", cible)
    print("écrit : config/modele-tableau.xlsx (neutralisé)")


def ignores(depot):
    motifs = []
    chemin = os.path.join(depot, ".gitignore")
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            motifs = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    def est_ignore(rel):
        ignore = False
        for m in motifs:
            neg = m.startswith("!")
            p = m[1:] if neg else m
            if p.endswith("/"):
                ok = rel.startswith(p) or ("/" + p) in ("/" + rel)
            elif "/" in p:
                ok = fnmatch.fnmatch(rel, p)
            else:
                ok = fnmatch.fnmatch(os.path.basename(rel), p)
            if ok:
                ignore = not neg
        return ignore
    return est_ignore


def problemes(texte, code=False, interdits=()):
    """Code Python : les UUID d'exemple des tests sont admis ; tout le reste est contrôlé."""
    trouves = [("mot interdit", m.group(0)) for motif in interdits for m in motif.finditer(texte)]
    for nom, motif in (("adresse mail", EMAIL), ("téléphone", TEL), ("identifiant Drive", ID_DRIVE),
                       ("identifiant", None if code else UUID), ("identifiant de tâche ou de session", ID_SESSION),
                       ("profil LinkedIn", LINKEDIN), ("chemin de dossier partagé", CHEMIN)):
        for m in (motif.finditer(texte) if motif else ()):
            if nom == "adresse mail" and exemple(m.group(0)):
                continue
            trouves.append((nom, m.group(0)))
    return trouves


def verifier(depot, neutre=None):
    interdits = (neutre or {}).get("interdits", ())
    est_ignore = ignores(depot)
    total = 0
    for racine, dossiers, fichiers in os.walk(depot):
        dossiers[:] = [d for d in dossiers if d != ".git"]
        for nom in fichiers:
            chemin = os.path.join(racine, nom)
            rel = os.path.relpath(chemin, depot).replace(os.sep, "/")
            if est_ignore(rel):
                continue
            textes = []
            if nom.endswith(".xlsx"):
                with zipfile.ZipFile(chemin) as z:
                    textes = [(n, z.read(n).decode("utf-8", "replace")) for n in z.namelist()]
            elif nom.endswith(FICHIERS_TEXTE) or nom in ("LICENSE", ".gitignore"):
                with open(chemin, encoding="utf-8") as f:
                    textes = [("", f.read())]
            for partie, texte in textes:
                for genre, valeur in problemes(texte, code=nom.endswith(".py"), interdits=interdits):
                    total += 1
                    print("À RETIRER : %s%s : %s « %s »" % (rel, " [%s]" % partie if partie else "", genre, valeur))
    print("Contrôle des données personnelles :", "rien trouvé" if not total else "%d élément(s)" % total)
    return total


def selftest():
    # Valeurs fictives assemblées à l'exécution, pour que ce fichier passe lui-même le contrôle.
    tableau = "1AbCdEfGhIjKlMn" + "OpQrStUvWxYz0123456789"
    exemples = {
        "Tél. +33 7 " + "12 34 56 78, mail prenom.nom" + "@" + "messagerie.fr": ["<TELEPHONE>", "<EMAIL>"],
        "https://docs.google.com/spreadsheets/d/" + tableau + "/edit": ["<ID_TABLEAU>"],
        "dossier 1Zz9Yy8Xx7Ww6" + "Vv5Uu4Tt3Ss2Rr1Qq0Pp, tâche trig_" + "01ABCDEFGHIJKLMN": ["<ID_DRIVE>", "<ID_TACHE>"],
        "linkedin.com/in/" + "quelquun-123 et contact@exemple.fr": ["linkedin.com/in/<PROFIL>", "contact@exemple.fr"],
        "/mnt" + "/autre-dossier/fichier.md": ["<DOSSIER>"],
    }
    ids = {tableau: "<ID_TABLEAU>"}
    echecs = 0
    for entree, attendus in exemples.items():
        sortie = masquer(entree, ids, "")
        ok = all(a in sortie for a in attendus) and not [p for p in problemes(sortie) if p[0] != "adresse mail"]
        echecs += not ok
        print("ok  " if ok else "ÉCHEC", entree, "->", sortie)
    pre, blocs = sections("# T\n\nintro\n\n## Liens\nx\n## Profil (faits)\ny\n## Règles\nz\n")
    ok = [t for t, _ in blocs] == ["Liens", "Profil (faits)", "Règles"] and pre.startswith("# T")
    echecs += not ok
    print("ok  " if ok else "ÉCHEC", "découpage des sections")
    regles = {"lignes_retirees": ["^- Décision privée"],
              "operations": [[r"(?:décision de )?Camille(?:,? (?:le |à )?(?:\d{1,2}/\d{1,2}/\d{4}|\d{1,2}h\d{2}))+"],
                             [r"\bde Camille\b", "du candidat"], [r"(^|^- |[.!?] )Camille\b", r"\1Le candidat"],
                             [r"\bCamille\b", "le candidat"]],
              "interdits": ["Camille"]}
    with tempfile.TemporaryDirectory() as d:
        chemin = os.path.join(d, "neutralisation.json")
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(regles, f)
        neutre = charger_neutralisation(chemin)
    entree = ("- Règle (Camille, 15h00) : accord de Camille.\n- Décision privée à retirer\n"
              "- Note (colonne F ; Camille, 11/10/2026, 15h14 ; remplace l'ancienne)\n"
              "- PME (même retrait, décision de Camille le 11/10/2026)\nCamille valide.")
    attendu = ("- Règle : accord du candidat.\n- Note (colonne F ; remplace l'ancienne)\n"
               "- PME (même retrait)\nLe candidat valide.")
    sortie = neutraliser(entree, neutre)
    ok = (sortie == attendu and problemes(entree, interdits=neutre["interdits"])
          and not problemes(sortie, interdits=neutre["interdits"]))
    echecs += not ok
    print("ok  " if ok else "ÉCHEC", "neutralisation ->", repr(sortie))
    print("selftest :", "réussi" if not echecs else "%d échec(s)" % echecs)
    return 1 if echecs else 0


def main(argv):
    if argv[:1] == ["--selftest"]:
        return selftest()
    if argv[:1] == ["--verifier"] and len(argv) in (2, 4) and argv[2:3] in ([], ["--neutralisation"]):
        return 1 if verifier(argv[1], charger_neutralisation(argv[3] if len(argv) == 4 else None)) else 0
    if len(argv) < 2:
        print(__doc__)
        return 2
    projet, depot = os.path.abspath(argv[0]), os.path.abspath(argv[1])
    options = dict(zip(argv[2::2], argv[3::2]))
    defaut = os.path.join(projet, "depot-sources", "neutralisation.json")
    if "--neutralisation" not in options and os.path.exists(defaut):
        options["--neutralisation"] = defaut
        print("neutralisation :", "depot-sources/neutralisation.json")
    for chemin in [os.path.join(projet, "profil-et-regles.md")] + list(options.values()):
        if not os.path.exists(chemin):
            print("Introuvable :", chemin)
            return 2
    if "--tableau" in options:
        verifier_modele(options["--tableau"])  # avant toute écriture, pour ne pas laisser un dépôt à moitié régénéré
    neutre = charger_neutralisation(options.get("--neutralisation"))
    os.makedirs(os.path.join(depot, "outils"), exist_ok=True)
    os.makedirs(os.path.join(depot, "config"), exist_ok=True)
    ids = generer_regles(projet, depot, neutre)
    generer_outils(projet, depot, neutre)
    if "--instructions" in options:
        generer_instructions(options["--instructions"], depot, ids, projet, neutre)
    if "--taches" in options:
        generer_taches(options["--taches"], depot, ids, projet, neutre)
    if "--tableau" in options:
        generer_tableau(options["--tableau"], depot, neutre)
    return 1 if verifier(depot, neutre) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

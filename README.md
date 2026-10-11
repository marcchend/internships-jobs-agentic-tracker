# Internships & Jobs Agentic Tracker

*English · [Français](README.fr.md)*

A human-in-the-loop application agent built on [Claude](https://claude.com/claude-code) for students
looking for an internship or a work-study contract (*alternance*) in data science and AI, in France or
abroad.

It searches for offers in a fixed order, checks every offer against the tracking sheet before analysing
it, scores its relevance with a simple and justified rubric, drafts the cover letter and the application
form answers, tracks every application in a Google Sheet with a dashboard, and prepares follow-ups 14
and 28 days after sending.

**Nothing is sent without the candidate's approval.** The agent prepares; the candidate approves every
application and every follow-up. See [Principles](#principles).

Inspired by [internship-agent](https://github.com/Mehdy03055/internship-agent), reworked around a
different tracker, rubric and set of rules (see [Differences from the original](#differences-from-the-original)).

> **Language note.** The agent is written for a French-speaking candidate: the rules, prompts,
> commands, sheet columns and status names are in French. This README translates the key terms.

---

## What it does

| Flow | When | Output |
|---|---|---|
| **Weekly batch** | Mondays at 7:46, only after the candidate's "go" for that batch | 5 prepared applications (3 or 4 published offers, 1 or 2 unsolicited applications): cover letter as a Google Doc, form answers, sheet row set to "À valider" (to approve) |
| **Follow-ups and replies** | every day at 8:26 | expired offers flagged, follow-ups due at D+14 and D+28 drafted for approval, "Sans réponse" (no reply) suggested at D+42, replies and bounces read when Gmail is connected |
| **Sending** | after the candidate's OK, one application at a time | form filled in once the candidate has signed in, or a Gmail draft; status "Envoyée" (sent) and send date |

Every offer gets one row in the sheet, with a status:

```
Spotted → To approve → To send → Sent → Followed up once → Followed up twice → No reply
                                      ↘ Interview or call → Accepted / Rejected / Dropped
                                      ↘ Invalid address
Spotted → Incompatible / Expired / Dropped
```

The sheet uses the French names: Repérée, À valider, À envoyer, Envoyée, Relancée 1 fois,
Relancée 2 fois, Sans réponse, Entretien ou échange, Acceptée, Refusée, Abandonnée, Adresse invalide,
Incompatible, Expirée.

## How it works

```
   instructions.md   ─┐  standing instructions (they take precedence)
   regles.md         ─┤  method, relevance score, duplicates, tracking sheet, procedures
   config/profil.md  ─┘  the only facts the agent may state about the candidate (kept out of Git)
                       │
   scheduled task ──► Claude ──► search: LinkedIn (limited access), Indeed, career sites, other sources
                         │
                         ├──► outils/doublons.py ──► already in the sheet? (before any analysis)
                         ├──► analysis: missions, fit, accessibility, score out of 4 or 3
                         ├──► Google Sheets: one row per offer, computed follow-up column, dashboard
                         │      └──► outils/controle_tableau.py ──► consistency check after every write
                         ├──► Google Docs: cover letter and form answers ──► outils/lettre_pdf.py ──► PDF
                         └──► summary for the candidate ──► OK per application ──► sending
```

All state is human-readable:

- **`instructions.md`**: the project's standing instructions, imported by `CLAUDE.md`.
- **`regles.md`**: the detailed rulebook that the scheduled tasks follow step by step.
- **`config/profil.md`**: the candidate's profile (education, projects, skills, gaps). The agent writes
  nothing about the candidate that is not in it.
- **`pistes.md`**: batches (with the candidate's "go"), search log, sources by country, target companies.
- **The tracking sheet** (Google Sheets): tabs Stage France (internship in France), Stage International
  (internship abroad), Alternance (work-study) and Tableau de bord (dashboard).
- **`taches-planifiees/*.md`**: the full prompt of each recurring task.

## Relevance score

A single rubric, used to rank offers, never to discard them:

| Offer | Score | Criteria (−1 each, justified by a concrete element of the offer) |
|---|---|---|
| Internship in France | out of 4 | 1. lacks technical depth; 2. little-known company without technical reputation (mid-size, start-up or SME; never a well-known group); 3. outside Paris; 4. duration explicitly set to 6 months |
| Internship abroad | out of 3 | criteria 1, 2 and 4 (no location penalty) |
| Work-study | out of 4 | criteria 1, 2 and 3 (default choice) |

Missing or ambiguous information is never assumed to be unfavourable, a single flaw costs at most one
point, and compatibility (duration, level, required skills, location) is assessed separately. The score
ranks offers; technical fit and accessibility, written in each row's notes, break ties.
`outils/controle_tableau.py` checks that every score equals the maximum minus the deductions written in
the "Motif" (reason) column. The criteria are defined in `instructions.md`, section 5, and in
`regles.md`, "Note de pertinence", and can be adapted there.

## Installation

1. **Requirements**: Claude Code (or a Claude project with a shared folder), Python 3.10 or later,
   Chromium or Chrome for the PDFs, and the Google Drive and Google Sheets connectors. Gmail is
   optional: without it, emails are prepared as text and the candidate sends them.

2. **Clone and fill in the configuration**

   ```bash
   git clone https://github.com/<account>/internships-jobs-agentic-tracker.git
   cd internships-jobs-agentic-tracker
   cp config/profil.exemple.md config/profil.md     # verified facts about the candidate
   cp config/liens.exemple.md config/liens.md       # IDs of the sheet, Drive folders and CVs
   cp config/pistes.exemple.md pistes.md            # batches, search log, target companies
   ```

   `config/profil.md`, `config/liens.md`, `pistes.md`, letters and CVs are ignored by Git: personal
   data stays out of the repository.

3. **The tracking sheet**: `config/modele-tableau.xlsx` is the Excel export of the empty sheet (columns,
   drop-down lists, formulas, formatting, dashboard). Import it into Google Sheets with the French
   locale (the formulas use the `;` separator), then write its ID in `config/liens.md`. In Excel or
   LibreOffice the "Prochaine relance" (next follow-up) column does not compute (Err:539 in
   LibreOffice): the file is meant for import, not for tracking. If the T1 formula does not survive the
   import, paste it again from `docs/architecture.md`. The structure is described in `regles.md`,
   "Tableau de suivi".

4. **The commands** (Claude Code skills)

   ```bash
   mkdir -p .claude/skills && cp -r skills/* .claude/skills/
   ```

5. **The scheduled tasks**: each file in `taches-planifiees/` is a complete prompt with its schedule.
   Replace `<ID_TABLEAU>` with the sheet ID, then register it with whatever scheduler you have (Claude
   project routines, scheduled tasks in the app, or cron with
   `claude -p "$(cat taches-planifiees/relances-et-reponses.md)"`).

## Usage

In Claude Code, from the repository folder:

```
/chercher-offres France 5                 # search offers, compare them with the sheet, score and record new ones
/preparer-candidature "Stage France" 12   # cover letter and form answers for one row of the sheet
/candidature-spontanee Japon 2            # targets with no published offer, verified contact, letter and email
/relances                                 # follow-ups due, replies, expired offers
```

Command-line tools:

```bash
python3 -I outils/doublons.py export.xlsx offres.json   # offers found, compared with the exported sheet
python3 -I outils/doublons.py --selftest                # checks the tool itself
python3 -I outils/controle_tableau.py export.xlsx       # sheet consistency: score and reason, statuses and dates, follow-ups
python3 -I outils/lettre_pdf.py lettre.txt lettre.pdf   # cover letter (Google Doc text) as a one-page PDF
```

## Principles

These are constraints, not options.

1. **Claude prepares, the candidate decides.** No application, form or follow-up goes out without
   explicit approval, given one application at a time. For an email, at most a Gmail draft.
2. **No invented facts.** Everything said about the candidate comes from `config/profil.md`. An ongoing
   project is always written in the present tense. A duration, mission or requirement missing from the
   offer is never assumed.
3. **No invented contacts.** An email address is used only if it is published on the organisation's
   official website, with the URL where it appears and a confidence level from 1 to 3.
4. **One precise fact per letter**, tied to a real strength of the candidate, in 250 to 350 words.
5. **Every offer is checked against the sheet before analysis.** An offer already recorded is neither
   analysed again nor added twice, even under another link; its history is never erased.
6. **Two follow-ups, then nothing without a reason.** D+14 and D+28, counted from the send date; a
   follow-up counts as done only when the data proves it.
7. **Respect for platforms.** LinkedIn and Indeed are used to find and read offers, never to apply
   automatically; no login to the candidate's account, no bypassing of protections.
8. **Transparency.** The agent never claims to have read an offer, sent a message or changed a file
   without actually doing it, and says exactly what remains to be done.

## Differences from the original

| | internship-agent | This repository |
|---|---|---|
| Language | English | French |
| Tracking | `tracker.csv` exported to xlsx | Google Sheets: three tabs, drop-down lists, computed follow-up column, dashboard |
| Score | out of 5, based on the target's angle | out of 4 in France, out of 3 abroad, four justified criteria |
| Follow-ups | D+7 then D+14 after each message | D+14 and D+28 from the first send, "no reply" suggested at D+42 |
| Duplicates | same company and same role | `outils/doublons.py`: normalised links, platform IDs, then company, title and location, before any analysis |
| Search | free | mandatory order LinkedIn, Indeed, career sites, independent search; companies ranked A to E |
| Pace | 5 offers and 5 unsolicited applications every 2 days | one batch of 5 per week, after the candidate's "go" |
| Sending | forms never submitted | form submitted by Claude after the candidate's OK and sign-in; emails as drafts only |

## Repository layout

```
README.md                   this file (English)
README.fr.md                French version
CLAUDE.md                   rules loaded by Claude Code in this folder (imports instructions.md)
instructions.md             the project's standing instructions (generated)
regles.md                   detailed rulebook (generated from the project's profil-et-regles.md)
config/profil.exemple.md    profile template (the real profile, config/profil.md, stays out of Git)
config/liens.exemple.md     IDs template (sheet, Drive folders, CVs)
config/pistes.exemple.md    pistes.md template
config/modele-tableau.xlsx  empty tracking sheet (Excel export)
skills/                     commands: chercher-offres, preparer-candidature, candidature-spontanee, relances
taches-planifiees/          prompts of the recurring tasks (generated)
outils/doublons.py          check for offers already recorded
outils/controle_tableau.py  sheet consistency check (reports, never fixes)
outils/lettre_pdf.py        one-page PDF cover letter
outils/exporter_depot.py    regenerates the generated files and checks that no personal data remains
docs/                       architecture and security model
```

## Keeping the repository up to date

The Claude project folder remains the reference; this repository is its versioned copy. After a change
to the rules, a tool, a scheduled task or the sheet structure:

```bash
python3 -I outils/exporter_depot.py <project folder> <repository folder> \
    [--instructions instructions.txt] [--taches taches.json] [--tableau tableau.xlsx] \
    [--neutralisation neutralisation.json]
```

The tool rewrites only the generated files and masks identifiers. With a neutralisation file, kept
out of the repository, it also anonymises the texts: the candidate's name becomes "le candidat", and
the school, projects and dated decisions are removed. It then scans the whole repository (email
addresses, phone numbers, Drive IDs, paths, and the forbidden words of the neutralisation file): it
exits with code 1 if any personal data remains. Then review the diff, commit and push.

## License

MIT, see [LICENSE](LICENSE).

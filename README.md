# bmad-template

Template de projet pour la methode **BMAD** + couche navigation **Obsidian** auto-generee.

## Contenu

```
.claude/settings.json          ← hooks Claude Code (generate_nav + log_session)
.obsidian/app.json             ← config vault Obsidian (dossiers ignores)
.obsidian/graph.json           ← groupes couleurs graph view
scripts/
  generate_nav.py              ← generateur _nav/ (PostToolUse hook)
  log_session.py               ← journal de session (PostToolUse hook)
  setup.py                     ← initialisation one-shot du projet
_bmad-output/                  ← sortie BMAD (ne pas modifier)
  planning-artifacts/
  implementation-artifacts/
    sprint-status.yaml         ← etat des stories (lu par generate_nav)
docs/                          ← documentation projet
_nav/                          ← navigation Obsidian (auto-genere, ne pas modifier)
```

## Creer un nouveau projet

### Via GitHub template (recommande)
1. Cliquer "Use this template" sur GitHub
2. Cloner le nouveau repo localement
3. `python scripts/setup.py "Mon Projet"`

### Via clone direct
```bash
git clone https://github.com/<user>/bmad-template mon-projet
cd mon-projet
rm -rf .git && git init   # detacher du template
python scripts/setup.py "Mon Projet"
```

## Prerequis

- Python 3.11+
- `uv` (recommande) ou `pip`
- Claude Code avec BMAD installe
- Obsidian

## Workflow BMAD

Apres `setup.py` :
1. Ouvrir Obsidian sur le dossier du projet
2. Dans Claude Code :
   - `/bmad-bmm-create-prd`
   - `/bmad-bmm-create-architecture`
   - `/bmad-bmm-create-epics-and-stories`
   - `/bmad-bmm-sprint-planning`
   - `/bmad-bmm-dev-story`  (repeter par story)

## Navigation Obsidian

La couche `_nav/` se regenere automatiquement apres chaque `Write`/`Edit` sur
`_bmad-output/` grace au hook `PostToolUse` dans `.claude/settings.json`.

Pour forcer la regeneration :
```bash
python scripts/generate_nav.py --force
```

Ce que contient `_nav/` apres la premiere story BMAD :
- `00-DASHBOARD.md` — tableau de bord global
- `01-PRD-MAP.md` — carte du PRD
- `02-ARCH-MAP.md` — carte architecture
- `03-ICEBOX-MAP.md` — fonctionnalites futures
- `epics/EPIC-XX-*.md` — une fiche par epic
- `canvas/project-hierarchy.canvas` — graphe PRD -> Epics (Obsidian Canvas)
- `canvas/current-sprint.canvas` — sprint actif

## Mise a jour du template

Pour recuperer une mise a jour du template dans un projet existant :
```bash
git remote add template https://github.com/<user>/bmad-template
git fetch template
git checkout template/main -- scripts/generate_nav.py scripts/log_session.py
git checkout template/main -- .claude/settings.json .obsidian/app.json .obsidian/graph.json
```

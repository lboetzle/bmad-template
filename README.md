# bmad-template

Template de projet **BMAD** (Business Method for AI-Driven Development) avec
couche de navigation **Obsidian** auto-generee et vue **Kanban** integree.

## Installation en une commande

```bash
git clone https://github.com/<toi>/bmad-template mon-projet
cd mon-projet
python install.py "Mon Projet"
```

`install.py` fait tout :
- Verifie/installe `uv` (gestionnaire Python)
- Cree le venv
- Personnalise le projet (nom, pyproject.toml, CLAUDE.md)
- Installe BMAD via `npx bmad-method install --full`
- Applique les patches BMAD (session handoff, git commit automatique)
- Telecharge et configure le plugin Kanban pour Obsidian

## Prerequis

| Outil | Requis | Installation |
|-------|--------|--------------|
| Python 3.11+ | oui | https://python.org |
| Node.js 20+ | oui | https://nodejs.org (LTS) |
| git | oui | https://git-scm.com |
| Claude Code | oui | https://claude.ai/code |
| Obsidian | recommande | https://obsidian.md |
| uv | auto | installe par `install.py` si absent |

## Contenu du template

```
install.py                           <- POINT D'ENTREE UNIQUE
scripts/
  generate_nav.py                    <- generateur _nav/ (PostToolUse hook)
  log_session.py                     <- journal de session Claude Code
  setup.py                           <- personnalisation projet (appele par install.py)
_bmad-patches/                       <- patches BMAD appliques apres install
  bmm/workflows/4-implementation/
    dev-story/instructions.xml       <- Step 10 : generation HANDOFF.md
    code-review/instructions.xml     <- Step 7 : git commit + HANDOFF.md
  _config/agents/
    bmm-dev.customize.yaml           <- lecture HANDOFF.md au demarrage
.claude/
  settings.json                      <- hooks PostToolUse (auto-declenchement)
.obsidian/
  app.json                           <- vault config (dossiers ignores)
  graph.json                         <- groupes couleurs graph view
  community-plugins.json             <- plugin Kanban active
  plugins/obsidian-kanban/
    manifest.json                    <- metadata plugin (main.js telecharge a l'install)
_bmad-output/
  planning-artifacts/                <- PRD, Architecture, Epics (genere par BMAD)
  implementation-artifacts/
    sprint-status.yaml               <- etat stories (lu par generate_nav)
docs/
  architecture/
  sessions/                          <- journaux de session Claude Code
  IceBox/                            <- fonctionnalites futures
src/                                 <- code source du projet
tests/
_nav/                                <- navigation Obsidian (auto-genere, ne pas toucher)
```

## Workflow BMAD

Apres `install.py` :

```
Dans Claude Code :
  /bmad-bmm-create-prd
  /bmad-bmm-create-architecture
  /bmad-bmm-create-epics-and-stories
  /bmad-bmm-sprint-planning
  /bmad-bmm-dev-story              <- repeter par story
  /bmad-bmm-code-review            <- apres chaque story
  /bmad-bmm-retrospective          <- en fin d'epic
```

## Patches BMAD inclus

Ce template inclut 3 patches appliques automatiquement sur les workflows BMAD :

### 1. Session Handoff (HANDOFF.md)
Genere un fichier `HANDOFF.md` a la fin de chaque session (dev-story Step 10
et code-review Step 7). Contient : story en cours, prochaine commande a lancer,
decisions cles. Lu automatiquement par l'agent au demarrage de la session suivante.

### 2. Git commit automatique (code-review Step 7)
Apres un code review accepte (story -> done), commit automatique :
`feat: Story X.Y -- titre`

### 3. Agent customization (bmm-dev.customize.yaml)
L'agent dev lis HANDOFF.md au debut de chaque session pour reprendre
le contexte sans recharger tout le projet manuellement.

## Navigation Obsidian

La couche `_nav/` se regenere automatiquement apres chaque `Write`/`Edit` BMAD
grace au hook `PostToolUse` dans `.claude/settings.json`.

**Vues disponibles dans Obsidian :**

| Vue | Fichier | Description |
|-----|---------|-------------|
| Dashboard | `_nav/00-DASHBOARD.md` | Statut global, epics actifs |
| Kanban | `_nav/kanban.md` | Stories par statut (plugin requis) |
| Hierarchie | `_nav/canvas/project-hierarchy.canvas` | PRD -> Epics (Canvas) |
| Sprint | `_nav/canvas/current-sprint.canvas` | Stories du sprint (Canvas) |
| PRD Map | `_nav/01-PRD-MAP.md` | Sections du PRD |
| Arch Map | `_nav/02-ARCH-MAP.md` | Diagrammes architecture |
| IceBox | `_nav/03-ICEBOX-MAP.md` | Fonctionnalites futures |
| Epic N | `_nav/epics/EPIC-XX-*.md` | Une fiche par epic |

Pour forcer la regeneration :
```bash
python scripts/generate_nav.py --force
```

## Options d'installation

```
python install.py "Mon Projet"              # installation complete
python install.py "Mon Projet" --no-kanban  # sans telechargement plugin
python install.py "Mon Projet" --no-bmad    # sans npx bmad-method install
python install.py                            # demande le nom interactivement
```

## Mise a jour du template

Pour recuperer les ameliorations du template dans un projet existant :
```bash
git remote add template https://github.com/<toi>/bmad-template
git fetch template
git checkout template/main -- scripts/generate_nav.py scripts/log_session.py
git checkout template/main -- .claude/settings.json .obsidian/app.json .obsidian/graph.json
git checkout template/main -- install.py scripts/setup.py
git checkout template/main -- _bmad-patches/
```

# bmad-template

> **[Francais](#francais)** | **[English](#english)**

---

<a name="francais"></a>

# Francais

Template de projet **BMAD** (Business Method for AI-Driven Development) — kit complet pour demarrer un projet Python avec Claude Code, documentation Obsidian auto-generee, pipeline qualite SonarQube integre et gestion de session inter-contexte.

## Table des matieres

- [Vue d'ensemble](#vue-densemble)
- [Prerequis](#prerequis)
- [Installation](#installation)
- [Workflow BMAD](#workflow-bmad)
- [Patches BMAD inclus](#patches-bmad-inclus)
- [Navigation Obsidian](#navigation-obsidian)
- [SonarQube local](#sonarqube-local)
- [Structure du projet](#structure-du-projet)
- [Options d'installation](#options-dinstallation)
- [Mise a jour du template](#mise-a-jour-du-template)

---

## Vue d'ensemble

Ce template configure automatiquement tout l'outillage d'un projet AI-driven :

| Composant | Ce qu'il fait |
|-----------|---------------|
| **BMAD** | Methodologie de developpement par stories avec agents Claude specialises |
| **Obsidian** | Navigation documentaire auto-generee (dashboard, kanban, canvas) |
| **SonarQube** | Analyse statique locale, quality gate, rapports ruff + mypy |
| **Patches BMAD** | Handoff de session, git commit auto, reprise de contexte |
| **Claude Code hooks** | Generation nav + journal de session apres chaque ecriture |

---

## Prerequis

| Outil | Requis | Remarque |
|-------|--------|----------|
| Python 3.11+ | **oui** | https://python.org |
| Node.js 20+ | **oui** | https://nodejs.org — pour `npx bmad-method install` |
| Git | **oui** | https://git-scm.com |
| Docker Desktop | **oui** | https://docker.com — pour SonarQube local |
| Claude Code | **oui** | https://claude.ai/code |
| Obsidian | recommande | https://obsidian.md |
| uv | auto | Installe automatiquement par `install.py` si absent |

---

## Installation

```bash
git clone https://github.com/lboetzle/bmad-template mon-projet
cd mon-projet
python install.py "Mon Projet"
```

`install.py` orchestre 9 etapes automatiquement :

| Etape | Description |
|-------|-------------|
| 1. **Prerequis** | Verifie git, node, docker, installe uv si absent |
| 2. **Venv Python** | Cree `.venv/` avec uv (ou python -m venv en secours) |
| 3. **Setup projet** | Remplace les placeholders, cree pyproject.toml + CLAUDE.md |
| 4. **BMAD** | `npx bmad-method install --full` — installe `_bmad/` + commandes Claude |
| 5. **Patches BMAD** | Applique les patches de `_bmad-patches/` sur les workflows |
| 6. **Kanban** | Telecharge le plugin Obsidian Kanban (main.js + styles.css) |
| 7. **SonarQube start** | `docker compose up -d`, attend que l'instance soit UP (~2-3 min) |
| 8. **Provision** | Cree le projet, genere un token, configure le quality gate, ecrit `.env` |
| 9. **Pipeline** | Lance pytest + ruff + mypy + sonar-scanner |

---

## Workflow BMAD

Apres l'installation, dans Claude Code :

```
/bmad-bmm-create-prd               <- Rediger le PRD avec l'agent PM
/bmad-bmm-create-architecture      <- Concevoir l'architecture avec l'agent Architect
/bmad-bmm-create-epics-and-stories <- Decouper en epics + stories
/bmad-bmm-sprint-planning          <- Planifier le sprint, initialiser sprint-status.yaml
/bmad-bmm-dev-story                <- Implementer une story (repeter par story)
/bmad-bmm-code-review              <- Review adversariale + fix + quality gate
/bmad-bmm-retrospective            <- Bilan d'epic, lecons apprises
```

Chaque commande `/bmad-*` est un workflow complet avec steps precis.
Chaque story se termine par un commit git automatique et la generation de `HANDOFF.md`.

---

## Patches BMAD inclus

Ce template applique 3 patches sur les workflows BMAD standards apres l'installation :

### 1. Handoff de session (`HANDOFF.md`)

**Probleme resolu** : BMAD recommande un contexte Claude vide par session — la memoire de travail se perd entre les sessions.

**Solution** : A la fin de chaque session (dev-story Step 10 et code-review Step 7), le workflow genere automatiquement `HANDOFF.md` a la racine du projet :

```markdown
# Session Handoff — 2026-03-02

## Complete cette session
Story 3.2 — Signal Detector
Statut : review

## Prochaine etape — NOUVELLE SESSION
-> Lancer : /bmad-bmm-code-review

## Decisions techniques cles
...
```

### 2. Git commit automatique (code-review Step 7)

**Probleme resolu** : Git commit oublie ou fait manuellement a la fin de chaque story.

**Solution** :
- Si la story passe en **done** : `git commit -m "feat: Story X.Y — titre"`
- Si la story revient en **in-progress** : `git commit -m "review: Story X.Y — N issues pending"`

### 3. Reprise de contexte agent (`bmm-dev.customize.yaml`)

**Probleme resolu** : L'agent demarre a l'aveugle dans une nouvelle session.

**Solution** : L'agent `bmm-dev` lit `HANDOFF.md` au debut de chaque session et annonce le contexte avant de continuer.

---

## Navigation Obsidian

La couche `_nav/` se regenere automatiquement apres chaque `Write`/`Edit` de fichiers BMAD, grace au hook `PostToolUse` dans `.claude/settings.json`.

**Vues disponibles :**

| Vue | Fichier | Description |
|-----|---------|-------------|
| Dashboard | `_nav/00-DASHBOARD.md` | Statut global, epics actifs |
| Kanban | `_nav/kanban.md` | Stories par statut (Backlog / In Progress / Review / Done) |
| Hierarchie | `_nav/canvas/project-hierarchy.canvas` | PRD vers epics (Canvas Obsidian) |
| Sprint actif | `_nav/canvas/current-sprint.canvas` | Stories du sprint courant |
| PRD Map | `_nav/01-PRD-MAP.md` | Sections du PRD avec liens |
| Arch Map | `_nav/02-ARCH-MAP.md` | Diagrammes d'architecture |
| IceBox | `_nav/03-ICEBOX-MAP.md` | Fonctionnalites futures |
| Epic N | `_nav/epics/EPIC-XX-*.md` | Une fiche par epic |

Les noms d'epics sont auto-detectes depuis les commentaires de `sprint-status.yaml` :

```yaml
# Epic 3: Signal Detection
3-1-ma-story: done
3-2-autre-story: in-progress
```

Pour forcer la regeneration :
```bash
python scripts/generate_nav.py --force
```

---

## SonarQube local

### Demarrage manuel

```bash
# Demarrer SonarQube (si pas fait par install.py)
docker compose -f docker-compose.sonar.yml up -d

# Attendre ~2-3 minutes, puis verifier
curl http://localhost:9000/api/system/status
```

### Provisionnement manuel (si install.py a echoue a cette etape)

```bash
python scripts/sonar_setup.py \
  --init \
  --project-key mon-projet \
  --project-name "Mon Projet" \
  --url http://localhost:9000 \
  --env-file .env
```

Cela effectue automatiquement :
1. Changement du mot de passe `admin` (admin:admin -> password securise)
2. Generation d'un token scanner
3. Creation du projet dans SonarQube
4. Configuration du Quality Gate (`new_coverage >= 80%`, `new_violations == 0`)
5. Ecriture de `SONAR_TOKEN` et `SONAR_ADMIN_PASSWORD` dans `.env`

### Lancer le pipeline

```bash
bash scripts/run_sonar_pipeline.sh
```

**Steps du pipeline :**

| Step | Outil | Sortie |
|------|-------|--------|
| 1 | `pytest --cov` | `coverage.xml` |
| 2 | `ruff check` | `ruff-sonar.json` |
| 3 | `mypy --strict` | `mypy-sonar.json` |
| 4 | `sonar-scanner` (Docker) | Upload vers `http://localhost:9000` |

Dashboard : `http://localhost:9000/dashboard?id=<project-key>`

### Quality Gate par defaut

| Metrique | Condition | Niveau |
|----------|-----------|--------|
| Couverture (nouvelles lignes) | `< 80 %` | ERROR |
| Nouvelles violations | `> 0` | ERROR |

### Arreter SonarQube

```bash
docker compose -f docker-compose.sonar.yml down
```

---

## Structure du projet

```
mon-projet/
  install.py                            <- Point d'entree unique
  sonar-project.properties              <- Config SonarQube (remplie par setup.py)
  docker-compose.sonar.yml              <- SonarQube CE + PostgreSQL 15
  .env                                  <- SONAR_TOKEN, SONAR_ADMIN_PASSWORD (gitignore)
  HANDOFF.md                            <- Contexte inter-session (genere par BMAD)
  CLAUDE.md                             <- Instructions pour l'agent Claude Code
  pyproject.toml                        <- Config Python (remplie par setup.py)

  scripts/
    setup.py                            <- Personnalisation projet (appele par install.py)
    generate_nav.py                     <- Generateur Obsidian _nav/ (hook PostToolUse)
    log_session.py                      <- Journal de session Claude Code
    run_sonar_pipeline.sh               <- Pipeline qualite complet
    sonar_setup.py                      <- Provisionnement SonarQube (first-run + quality gate)
    sonar_export.py                     <- Adaptateur ruff/mypy -> format SonarQube

  _bmad-patches/                        <- Patches appliques sur les workflows BMAD
    bmm/workflows/4-implementation/
      dev-story/instructions.xml        <- Patch Step 10 : generation HANDOFF.md
      code-review/instructions.xml      <- Patch Step 7 : git commit + HANDOFF.md
    _config/agents/
      bmm-dev.customize.yaml            <- Lecture HANDOFF.md au demarrage agent

  _bmad/                                <- Installe par npx bmad-method (non versionne)
    bmm/workflows/                      <- Workflows patched par _bmad-patches/
    _config/agents/                     <- Customization agent dev

  .claude/
    settings.json                       <- Hooks PostToolUse + UserPromptSubmit

  .obsidian/
    community-plugins.json              <- Plugin Kanban active
    plugins/obsidian-kanban/            <- Plugin (telecharge par install.py)

  _bmad-output/
    planning-artifacts/                 <- PRD, Architecture, Epics (genere par BMAD)
    implementation-artifacts/
      sprint-status.yaml                <- Etat des stories (source verite du sprint)

  _nav/                                 <- Navigation Obsidian (auto-genere, ne pas editer)
  src/<project-slug>/                   <- Code source (cree par setup.py)
  tests/                                <- Tests pytest
  docs/
    architecture/                       <- Diagrammes d'architecture
    sessions/                           <- Journaux de session Claude Code
    IceBox/                             <- Fonctionnalites futures
```

---

## Options d'installation

```bash
python install.py "Mon Projet"              # Installation complete (recommande)
python install.py "Mon Projet" --no-sonar   # Sans SonarQube
python install.py "Mon Projet" --no-bmad    # Sans npx bmad-method install
python install.py "Mon Projet" --no-kanban  # Sans telechargement plugin Kanban
python install.py                           # Demande le nom interactivement
```

---

## Mise a jour du template

Pour recuperer les ameliorations dans un projet existant :

```bash
git remote add template https://github.com/lboetzle/bmad-template
git fetch template

# Scripts
git checkout template/master -- scripts/generate_nav.py scripts/log_session.py
git checkout template/master -- scripts/sonar_setup.py scripts/sonar_export.py
git checkout template/master -- scripts/run_sonar_pipeline.sh

# Config
git checkout template/master -- .claude/settings.json
git checkout template/master -- install.py scripts/setup.py

# Patches BMAD
git checkout template/master -- _bmad-patches/

# Puis re-appliquer les patches sur _bmad/
python install.py --no-kanban --no-sonar
```

---

<a name="english"></a>

# English

**BMAD** (Business Method for AI-Driven Development) project template — a complete kit to bootstrap a Python project with Claude Code, auto-generated Obsidian documentation, an integrated SonarQube quality pipeline, and cross-session context management.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [BMAD Workflow](#bmad-workflow)
- [Included BMAD Patches](#included-bmad-patches)
- [Obsidian Navigation](#obsidian-navigation)
- [Local SonarQube](#local-sonarqube)
- [Project Structure](#project-structure)
- [Installation Options](#installation-options)
- [Updating the Template](#updating-the-template)

---

## Overview

This template automatically sets up all the tooling for an AI-driven project:

| Component | What it does |
|-----------|--------------|
| **BMAD** | Story-driven development methodology with specialized Claude agents |
| **Obsidian** | Auto-generated documentation layer (dashboard, kanban, canvas) |
| **SonarQube** | Local static analysis, quality gate, ruff + mypy reports |
| **BMAD Patches** | Session handoff, auto git commit, context resumption |
| **Claude Code hooks** | Nav regeneration + session journal after every write |

---

## Prerequisites

| Tool | Required | Note |
|------|----------|------|
| Python 3.11+ | **yes** | https://python.org |
| Node.js 20+ | **yes** | https://nodejs.org — for `npx bmad-method install` |
| Git | **yes** | https://git-scm.com |
| Docker Desktop | **yes** | https://docker.com — for local SonarQube |
| Claude Code | **yes** | https://claude.ai/code |
| Obsidian | recommended | https://obsidian.md |
| uv | auto | Installed automatically by `install.py` if missing |

---

## Installation

```bash
git clone https://github.com/lboetzle/bmad-template my-project
cd my-project
python install.py "My Project"
```

`install.py` runs 9 steps automatically:

| Step | Description |
|------|-------------|
| 1. **Prerequisites** | Checks git, node, docker; installs uv if missing |
| 2. **Python venv** | Creates `.venv/` with uv (falls back to python -m venv) |
| 3. **Project setup** | Replaces placeholders, creates pyproject.toml + CLAUDE.md |
| 4. **BMAD** | `npx bmad-method install --full` — installs `_bmad/` + Claude commands |
| 5. **BMAD patches** | Applies patches from `_bmad-patches/` onto installed workflows |
| 6. **Kanban** | Downloads the Obsidian Kanban plugin (main.js + styles.css) |
| 7. **SonarQube start** | `docker compose up -d`, waits until instance is UP (~2-3 min) |
| 8. **Provision** | Creates project, generates token, configures quality gate, writes `.env` |
| 9. **Pipeline** | Runs pytest + ruff + mypy + sonar-scanner |

---

## BMAD Workflow

After installation, inside Claude Code:

```
/bmad-bmm-create-prd               <- Write the PRD with the PM agent
/bmad-bmm-create-architecture      <- Design architecture with the Architect agent
/bmad-bmm-create-epics-and-stories <- Break down into epics + stories
/bmad-bmm-sprint-planning          <- Plan the sprint, initialize sprint-status.yaml
/bmad-bmm-dev-story                <- Implement a story (repeat per story)
/bmad-bmm-code-review              <- Adversarial review + fix + quality gate
/bmad-bmm-retrospective            <- Epic retrospective, lessons learned
```

Each `/bmad-*` command is a complete workflow with precise steps.
Every story ends with an automatic git commit and `HANDOFF.md` generation.

---

## Included BMAD Patches

This template applies 3 patches to standard BMAD workflows after installation:

### 1. Session Handoff (`HANDOFF.md`)

**Problem solved**: BMAD recommends an empty Claude context per session — working memory is lost between sessions.

**Solution**: At the end of each session (dev-story Step 10 and code-review Step 7), the workflow automatically generates `HANDOFF.md` at the project root:

```markdown
# Session Handoff — 2026-03-02

## Completed this session
Story 3.2 — Signal Detector
Status: review

## Next step — NEW SESSION (empty context)
-> Run: /bmad-bmm-code-review

## Key technical decisions
...
```

### 2. Automatic git commit (code-review Step 7)

**Problem solved**: Git commits forgotten or done manually at the end of each story.

**Solution**:
- If the story moves to **done**: `git commit -m "feat: Story X.Y — title"`
- If the story goes back to **in-progress**: `git commit -m "review: Story X.Y — N issues pending"`

### 3. Agent context resumption (`bmm-dev.customize.yaml`)

**Problem solved**: The agent starts blind in a new session.

**Solution**: The `bmm-dev` agent reads `HANDOFF.md` at the start of each session and announces the context before proceeding.

---

## Obsidian Navigation

The `_nav/` layer regenerates automatically after every `Write`/`Edit` of BMAD files, thanks to the `PostToolUse` hook in `.claude/settings.json`.

**Available views:**

| View | File | Description |
|------|------|-------------|
| Dashboard | `_nav/00-DASHBOARD.md` | Global status, active epics |
| Kanban | `_nav/kanban.md` | Stories by status (Backlog / In Progress / Review / Done) |
| Hierarchy | `_nav/canvas/project-hierarchy.canvas` | PRD to epics (Obsidian Canvas) |
| Active Sprint | `_nav/canvas/current-sprint.canvas` | Stories in current sprint |
| PRD Map | `_nav/01-PRD-MAP.md` | PRD sections with links |
| Arch Map | `_nav/02-ARCH-MAP.md` | Architecture diagrams |
| IceBox | `_nav/03-ICEBOX-MAP.md` | Future features |
| Epic N | `_nav/epics/EPIC-XX-*.md` | One page per epic |

Epic names are auto-detected from comments in `sprint-status.yaml`:

```yaml
# Epic 3: Signal Detection
3-1-my-story: done
3-2-another-story: in-progress
```

To force regeneration:
```bash
python scripts/generate_nav.py --force
```

---

## Local SonarQube

### Manual startup

```bash
# Start SonarQube (if not done by install.py)
docker compose -f docker-compose.sonar.yml up -d

# Wait ~2-3 minutes, then check
curl http://localhost:9000/api/system/status
```

### Manual provisioning (if install.py failed at that step)

```bash
python scripts/sonar_setup.py \
  --init \
  --project-key my-project \
  --project-name "My Project" \
  --url http://localhost:9000 \
  --env-file .env
```

This automatically:
1. Changes the `admin` password (admin:admin -> secure random password)
2. Generates a scanner token
3. Creates the project in SonarQube
4. Configures the Quality Gate (`new_coverage >= 80%`, `new_violations == 0`)
5. Writes `SONAR_TOKEN` and `SONAR_ADMIN_PASSWORD` to `.env`

### Running the pipeline

```bash
bash scripts/run_sonar_pipeline.sh
```

**Pipeline steps:**

| Step | Tool | Output |
|------|------|--------|
| 1 | `pytest --cov` | `coverage.xml` |
| 2 | `ruff check` | `ruff-sonar.json` |
| 3 | `mypy --strict` | `mypy-sonar.json` |
| 4 | `sonar-scanner` (Docker) | Upload to `http://localhost:9000` |

Dashboard: `http://localhost:9000/dashboard?id=<project-key>`

### Default Quality Gate

| Metric | Condition | Level |
|--------|-----------|-------|
| Coverage (new lines) | `< 80 %` | ERROR |
| New violations | `> 0` | ERROR |

### Stopping SonarQube

```bash
docker compose -f docker-compose.sonar.yml down
```

---

## Project Structure

```
my-project/
  install.py                            <- Single entry point
  sonar-project.properties              <- SonarQube config (filled by setup.py)
  docker-compose.sonar.yml              <- SonarQube CE + PostgreSQL 15
  .env                                  <- SONAR_TOKEN, SONAR_ADMIN_PASSWORD (gitignored)
  HANDOFF.md                            <- Cross-session context (generated by BMAD)
  CLAUDE.md                             <- Instructions for the Claude Code agent
  pyproject.toml                        <- Python config (filled by setup.py)

  scripts/
    setup.py                            <- Project personalization (called by install.py)
    generate_nav.py                     <- Obsidian _nav/ generator (PostToolUse hook)
    log_session.py                      <- Claude Code session journal
    run_sonar_pipeline.sh               <- Full quality pipeline
    sonar_setup.py                      <- SonarQube provisioning (first-run + quality gate)
    sonar_export.py                     <- ruff/mypy -> SonarQube format adapter

  _bmad-patches/                        <- Patches applied to BMAD workflows
    bmm/workflows/4-implementation/
      dev-story/instructions.xml        <- Patch Step 10: HANDOFF.md generation
      code-review/instructions.xml      <- Patch Step 7: git commit + HANDOFF.md
    _config/agents/
      bmm-dev.customize.yaml            <- Read HANDOFF.md on agent startup

  _bmad/                                <- Installed by npx bmad-method (not versioned)
    bmm/workflows/                      <- Workflows patched by _bmad-patches/
    _config/agents/                     <- Dev agent customization

  .claude/
    settings.json                       <- PostToolUse + UserPromptSubmit hooks

  .obsidian/
    community-plugins.json              <- Kanban plugin enabled
    plugins/obsidian-kanban/            <- Plugin (downloaded by install.py)

  _bmad-output/
    planning-artifacts/                 <- PRD, Architecture, Epics (generated by BMAD)
    implementation-artifacts/
      sprint-status.yaml                <- Story status (sprint source of truth)

  _nav/                                 <- Obsidian navigation (auto-generated, do not edit)
  src/<project-slug>/                   <- Source code (created by setup.py)
  tests/                                <- pytest tests
  docs/
    architecture/                       <- Architecture diagrams
    sessions/                           <- Claude Code session journals
    IceBox/                             <- Future features
```

---

## Installation Options

```bash
python install.py "My Project"              # Full installation (recommended)
python install.py "My Project" --no-sonar   # Without SonarQube
python install.py "My Project" --no-bmad    # Without npx bmad-method install
python install.py "My Project" --no-kanban  # Without Kanban plugin download
python install.py                           # Prompts for project name interactively
```

---

## Updating the Template

To pull improvements into an existing project:

```bash
git remote add template https://github.com/lboetzle/bmad-template
git fetch template

# Scripts
git checkout template/master -- scripts/generate_nav.py scripts/log_session.py
git checkout template/master -- scripts/sonar_setup.py scripts/sonar_export.py
git checkout template/master -- scripts/run_sonar_pipeline.sh

# Config
git checkout template/master -- .claude/settings.json
git checkout template/master -- install.py scripts/setup.py

# BMAD patches
git checkout template/master -- _bmad-patches/

# Then re-apply patches to _bmad/
python install.py --no-kanban --no-sonar
```

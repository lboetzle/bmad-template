#!/usr/bin/env python3
"""
setup.py — Personnalise ce template pour un nouveau projet.

Usage (une seule fois, après avoir cloné le template) :
  python scripts/setup.py "Mon Projet"

Ce que ca fait :
  - Remplace le placeholder {{PROJECT_NAME}} dans sprint-status.yaml
  - Cree src/<slug>/__init__.py
  - Cree un pyproject.toml minimal
  - Cree CLAUDE.md pre-rempli
  - Lance generate_nav.py --force pour initialiser _nav/
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def slugify(name: str) -> str:
    n = name.lower().replace(" ", "-").replace("_", "-")
    return re.sub(r"[^a-z0-9-]", "", n).strip("-")


def replace_in_file(path: Path, placeholder: str, value: str) -> None:
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if placeholder in text:
            path.write_text(text.replace(placeholder, value), encoding="utf-8")
            print(f"  ~ {path.relative_to(ROOT)}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/setup.py \"Mon Projet\"", file=sys.stderr)
        sys.exit(1)

    project_name = sys.argv[1].strip()
    slug = slugify(project_name)

    print(f"\n[setup] Projet : {project_name} ({slug})\n")

    # 1. Remplacer les placeholders dans les fichiers de configuration
    replace_in_file(
        ROOT / "_bmad-output" / "implementation-artifacts" / "sprint-status.yaml",
        "{{PROJECT_NAME}}",
        project_name,
    )

    sonar_props = ROOT / "sonar-project.properties"
    replace_in_file(sonar_props, "{{PROJECT_SLUG}}", slug)
    replace_in_file(sonar_props, "{{PROJECT_NAME}}", project_name)

    # 2. pyproject.toml
    pyproject = ROOT / "pyproject.toml"
    if not pyproject.exists():
        pyproject.write_text(f"""\
[project]
name = "{slug}"
version = "0.1.0"
description = "{project_name}"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[dependency-groups]
dev = [
    "pytest>=9,<10",
    "ruff>=0.14,<1",
    "mypy>=1.19,<2",
]

[tool.ruff]
target-version = "py311"
line-length = 120
src = ["src"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
""", encoding="utf-8")
        print(f"  + pyproject.toml")

    # 3. src/<slug>/__init__.py
    pkg = ROOT / "src" / slug
    pkg.mkdir(parents=True, exist_ok=True)
    init = pkg / "__init__.py"
    if not init.exists():
        init.write_text(f'"""Package {project_name}."""\n', encoding="utf-8")
        print(f"  + src/{slug}/__init__.py")

    # 4. CLAUDE.md
    claude_md = ROOT / "CLAUDE.md"
    if not claude_md.exists():
        claude_md.write_text(f"""\
# {project_name}

## Methode de travail
Ce projet utilise la methode **BMAD** (Business Method for AI-Driven Development)
avec une couche de navigation Obsidian auto-generee dans `_nav/`.

## Demarrer le projet (premiere fois)
1. `/bmad-bmm-create-prd`
2. `/bmad-bmm-create-architecture`
3. `/bmad-bmm-create-epics-and-stories`
4. `/bmad-bmm-sprint-planning`

## Session de developpement courante
1. `/bmad-bmm-sprint-status`   <- etat du sprint
2. `/bmad-bmm-dev-story`       <- implementer la prochaine story

## Navigation Obsidian
La couche `_nav/` se regenere automatiquement apres chaque Write/Edit sur
`_bmad-output/` (hook PostToolUse).
Pour forcer : `python scripts/generate_nav.py --force`
""", encoding="utf-8")
        print("  + CLAUDE.md")

    # 5. generate_nav --force
    print("\n[setup] Initialisation nav Obsidian...")
    result = subprocess.run(
        [sys.executable, "scripts/generate_nav.py", "--force"],
        cwd=ROOT,
    )
    if result.returncode != 0:
        print("  ! Echec generate_nav — lancer manuellement : python scripts/generate_nav.py --force")

    print(f"""
[setup] Termine !

Prochaines etapes :
  1. uv sync  (ou: python -m venv .venv && pip install -e .[dev])
  2. Ouvrir Obsidian -> coffre -> {ROOT}
  3. Dans Claude Code : /bmad-bmm-create-prd
""")


if __name__ == "__main__":
    main()

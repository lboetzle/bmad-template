#!/usr/bin/env python3
"""
install.py — Installation one-shot : BMAD + Obsidian nav + Kanban.

Usage (apres avoir clone le template) :
  python install.py "Mon Projet"
  python install.py "Mon Projet" --no-kanban   # sans telechargement du plugin

Ce script :
  1. Verifie et installe les prerequis (uv, git)
  2. Cree le venv Python
  3. Personnalise le projet (nom, pyproject.toml, CLAUDE.md)
  4. Genere la couche nav Obsidian (_nav/)
  5. Telecharge et configure le plugin Kanban pour Obsidian
  6. Affiche les instructions pour Claude Code + BMAD

Prerequis minimaux :
  - Python 3.11+ (pour lancer ce script)
  - Internet (pour uv si non installe + plugin Kanban)
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
IS_WINDOWS = platform.system() == "Windows"

# ─── Couleurs terminal ────────────────────────────────────────────────────────

def _c(text: str, code: str) -> str:
    """ANSI color — desactive si pas de TTY (ex: PowerShell sans ANSI)."""
    if not sys.stdout.isatty() and not os.environ.get("FORCE_COLOR"):
        return text
    return f"\033[{code}m{text}\033[0m"

OK   = lambda s: print(_c(f"  + {s}", "32"))    # vert
WARN = lambda s: print(_c(f"  ! {s}", "33"))    # jaune
ERR  = lambda s: print(_c(f"  x {s}", "31"))    # rouge
HEAD = lambda s: print(_c(f"\n{s}", "36;1"))    # cyan gras


# ─── Helpers ──────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    n = name.lower().replace(" ", "-").replace("_", "-")
    return re.sub(r"[^a-z0-9-]", "", n).strip("-")


def run(cmd: list[str], label: str, cwd: Path = ROOT, check: bool = True) -> bool:
    print(f"  » {label} ...", end=" ", flush=True)
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode == 0:
        print(_c("OK", "32"))
        return True
    print(_c("ERREUR", "31"))
    if result.stderr.strip():
        print(f"    {result.stderr.strip()[:300]}")
    return False


def download(url: str, dest: Path, label: str) -> bool:
    print(f"  » {label} ...", end=" ", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "bmad-template-install"})
        with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
            f.write(r.read())
        print(_c("OK", "32"))
        return True
    except Exception as e:
        print(_c(f"ERREUR ({e})", "31"))
        return False


def venv_python() -> Path | None:
    for p in [
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
    ]:
        if p.exists():
            return p
    return None


# ─── Etapes ───────────────────────────────────────────────────────────────────

def step_prerequisites() -> tuple[str | None, bool]:
    """Retourne (chemin_uv_ou_None, git_ok)."""
    HEAD("1. Prerequis")

    # git
    git_ok = bool(shutil.which("git"))
    if git_ok:
        OK("git")
    else:
        WARN("git non trouve")
        if IS_WINDOWS:
            print("    -> winget install --id Git.Git -e")
        else:
            print("    -> brew install git  /  apt install git")
        print("    Installe git puis relance install.py")

    # uv
    uv = shutil.which("uv")
    if uv:
        OK("uv")
    else:
        WARN("uv non trouve — installation...")
        if IS_WINDOWS:
            ps_cmd = [
                "powershell", "-ExecutionPolicy", "Bypass",
                "-Command", "irm https://astral.sh/uv/install.ps1 | iex",
            ]
            if subprocess.run(ps_cmd).returncode == 0:
                # Actualiser PATH
                new_path = os.path.expandvars("%APPDATA%\\..\\Local\\Programs\\Python\\uv")
                if os.path.isdir(new_path):
                    os.environ["PATH"] = new_path + os.pathsep + os.environ.get("PATH", "")
                uv = shutil.which("uv")
        else:
            subprocess.run(
                "curl -LsSf https://astral.sh/uv/install.sh | sh", shell=True,
            )
            uv = shutil.which("uv") or str(Path.home() / ".local" / "bin" / "uv")
        if uv and Path(uv).exists():
            OK("uv installe")
        else:
            WARN("uv toujours introuvable — utilisation de python -m venv comme secours")
            uv = None

    return uv, git_ok


def step_venv(uv: str | None) -> None:
    HEAD("2. Environnement Python")
    if (ROOT / ".venv").exists():
        OK(".venv existant")
        return
    if uv:
        run([uv, "venv", ".venv", "--quiet"], "uv venv")
    else:
        py = shutil.which("python") or shutil.which("python3") or sys.executable
        run([py, "-m", "venv", ".venv"], "python -m venv .venv")


def step_setup(project_name: str) -> None:
    HEAD("3. Configuration du projet")
    py = venv_python() or Path(sys.executable)
    run([str(py), "scripts/setup.py", project_name], f"setup.py '{project_name}'")


def step_kanban() -> None:
    HEAD("4. Plugin Kanban Obsidian")
    plugin_dir = ROOT / ".obsidian" / "plugins" / "obsidian-kanban"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    base = "https://github.com/mgmeyers/obsidian-kanban/releases/latest/download"
    success = True
    for fname in ("main.js", "styles.css", "manifest.json"):
        dest = plugin_dir / fname
        if dest.exists():
            print(f"  ~ {fname} (existant)")
            continue
        ok = download(f"{base}/{fname}", dest, f"kanban/{fname}")
        success = success and ok

    # community-plugins.json
    cp_file = ROOT / ".obsidian" / "community-plugins.json"
    if cp_file.exists():
        try:
            plugins: list[str] = json.loads(cp_file.read_text(encoding="utf-8"))
        except Exception:
            plugins = []
        if "obsidian-kanban" not in plugins:
            plugins.append("obsidian-kanban")
            cp_file.write_text(json.dumps(plugins), encoding="utf-8")
            OK("community-plugins.json mis a jour")
        else:
            print("  ~ obsidian-kanban deja dans community-plugins.json")
    else:
        cp_file.write_text('["obsidian-kanban"]', encoding="utf-8")
        OK("community-plugins.json cree")

    if not success:
        WARN("Certains fichiers du plugin n'ont pas pu etre telecharges.")
        WARN("Installe le plugin manuellement : Obsidian > Parametres > Plugins communautaires > Kanban")


def step_summary(project_name: str) -> None:
    sep = "=" * 60
    print(f"""
{_c(sep, "32")}
{_c("Installation terminee !", "32;1")}
Projet : {project_name}
Dossier : {ROOT}
{sep}

Prochaines etapes :

  A. Ouvrir Obsidian
     -> Gerer les coffres -> {ROOT}
     -> Parametres > Plugins communautaires > Activer
     -> Le plugin "Kanban" doit etre dans la liste

  B. Ouvrir Claude Code dans ce dossier
     puis lancer dans l'ordre :
       /bmad-bmm-create-prd
       /bmad-bmm-create-architecture
       /bmad-bmm-create-epics-and-stories
       /bmad-bmm-sprint-planning
       /bmad-bmm-dev-story         (repeter par story)

  C. BMAD requis dans Claude Code.
     Si les commandes /bmad-* sont absentes :
     -> https://github.com/bmad-method/bmad-method

  D. La vue Kanban est dans _nav/kanban.md
     Elle se regenere automatiquement apres chaque story BMAD.
     Pour forcer : python scripts/generate_nav.py --force

{sep}
""")


# ─── Point d'entree ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Installation one-shot BMAD + Obsidian nav + Kanban",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "name", nargs="?", default="",
        help='Nom du projet (ex: "Mon Projet"). Demande interactivement si absent.',
    )
    parser.add_argument(
        "--no-kanban", action="store_true",
        help="Ignorer le telechargement du plugin Kanban",
    )
    args = parser.parse_args()

    project_name = args.name.strip()
    if not project_name:
        try:
            project_name = input('Nom du projet (ex: "Mon Projet") : ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
    if not project_name:
        project_name = ROOT.name  # fallback: nom du dossier

    print(_c(f"\n=== BMAD Template — Installation de '{project_name}' ===", "36;1"))

    uv, _git_ok = step_prerequisites()
    step_venv(uv)
    step_setup(project_name)
    if not args.no_kanban:
        step_kanban()
    step_summary(project_name)


if __name__ == "__main__":
    main()

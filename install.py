#!/usr/bin/env python3
"""
install.py -- Installation one-shot : BMAD + Obsidian nav + Kanban + SonarQube.

Usage (apres avoir clone le template) :
  python install.py "Mon Projet"
  python install.py "Mon Projet" --no-kanban   # sans telechargement du plugin
  python install.py "Mon Projet" --no-bmad     # sans npx bmad-method install
  python install.py "Mon Projet" --no-sonar    # sans SonarQube

Ce script :
  1. Verifie et installe les prerequis (uv, git, node, docker)
  2. Cree le venv Python
  3. Personnalise le projet (nom, pyproject.toml, CLAUDE.md, sonar-project.properties)
  4. Installe BMAD via npx bmad-method install --full
  5. Applique les patches BMAD (workflows + agent customize)
  6. Telecharge et configure le plugin Kanban pour Obsidian
  7. Demarre SonarQube (docker compose up) et attend qu'il soit pret
  8. Provisionne SonarQube (projet + token + quality gate + .env)
  9. Lance le pipeline qualite complet (pytest + ruff + mypy + scanner)

Prerequis minimaux :
  - Python 3.11+ (pour lancer ce script)
  - Node.js 20+ (pour npx bmad-method install)
  - Docker Desktop (pour SonarQube)
  - Internet (pour uv si non installe + BMAD + plugin Kanban)
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
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
IS_WINDOWS = platform.system() == "Windows"

# --- Couleurs terminal --------------------------------------------------------

def _c(text: str, code: str) -> str:
    """ANSI color -- desactive si pas de TTY (ex: PowerShell sans ANSI)."""
    if not sys.stdout.isatty() and not os.environ.get("FORCE_COLOR"):
        return text
    return f"\033[{code}m{text}\033[0m"

OK   = lambda s: print(_c(f"  + {s}", "32"))    # vert
WARN = lambda s: print(_c(f"  ! {s}", "33"))    # jaune
ERR  = lambda s: print(_c(f"  x {s}", "31"))    # rouge
HEAD = lambda s: print(_c(f"\n{s}", "36;1"))    # cyan gras


# --- Helpers ------------------------------------------------------------------

def slugify(name: str) -> str:
    n = name.lower().replace(" ", "-").replace("_", "-")
    return re.sub(r"[^a-z0-9-]", "", n).strip("-")


def run(cmd: list[str], label: str, cwd: Path = ROOT, check: bool = True) -> bool:
    print(f"  >> {label} ...", end=" ", flush=True)
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode == 0:
        print(_c("OK", "32"))
        return True
    print(_c("ERREUR", "31"))
    if result.stderr.strip():
        print(f"    {result.stderr.strip()[:300]}")
    return False


def run_visible(cmd: list[str], label: str, cwd: Path = ROOT) -> bool:
    """Run a command with live output (for long-running steps)."""
    print(f"  >> {label}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode == 0:
        print(_c(f"  + {label} OK", "32"))
        return True
    print(_c(f"  x {label} ERREUR", "31"))
    return False


def download(url: str, dest: Path, label: str) -> bool:
    print(f"  >> {label} ...", end=" ", flush=True)
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


# --- Etapes -------------------------------------------------------------------

def step_prerequisites() -> tuple[str | None, bool, bool, bool]:
    """Retourne (uv_path, git_ok, node_ok, docker_ok)."""
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

    # node
    node = shutil.which("node")
    node_ok = False
    if node:
        result = subprocess.run([node, "--version"], capture_output=True, text=True)
        version_str = result.stdout.strip()
        try:
            major = int(version_str.lstrip("v").split(".")[0])
            node_ok = major >= 20
            if node_ok:
                OK(f"node {version_str}")
            else:
                WARN(f"node {version_str} trop ancien (requis >= 20) -- BMAD ignore")
        except ValueError:
            WARN("node version non lisible -- BMAD ignore")
    else:
        WARN("node non trouve -- BMAD ignore")
        print("    -> https://nodejs.org  (LTS >= 20)")

    # docker
    docker = shutil.which("docker")
    docker_ok = False
    if docker:
        result = subprocess.run(
            [docker, "info"], capture_output=True, text=True
        )
        docker_ok = result.returncode == 0
        if docker_ok:
            OK("docker (daemon running)")
        else:
            WARN("docker installe mais daemon non accessible")
            print("    -> Demarre Docker Desktop puis relance install.py")
    else:
        WARN("docker non trouve -- SonarQube ignore")
        print("    -> https://www.docker.com/products/docker-desktop")

    # uv
    uv = shutil.which("uv")
    if uv:
        OK("uv")
    else:
        WARN("uv non trouve -- installation...")
        if IS_WINDOWS:
            ps_cmd = [
                "powershell", "-ExecutionPolicy", "Bypass",
                "-Command", "irm https://astral.sh/uv/install.ps1 | iex",
            ]
            if subprocess.run(ps_cmd).returncode == 0:
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
            WARN("uv toujours introuvable -- utilisation de python -m venv comme secours")
            uv = None

    return uv, git_ok, node_ok, docker_ok


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


def step_bmad(node_ok: bool) -> None:
    HEAD("4. Installation BMAD")
    if not node_ok:
        WARN("Node.js >= 20 requis -- etape BMAD ignoree")
        return

    bmad_dir = ROOT / "_bmad"
    if bmad_dir.exists():
        OK("_bmad/ deja present -- installation ignoree")
        return

    npx = shutil.which("npx")
    if not npx:
        WARN("npx non trouve -- etape BMAD ignoree")
        return

    ok = run(
        [npx, "bmad-method", "install", "--full"],
        "npx bmad-method install --full",
    )
    if ok:
        OK("BMAD installe")
    else:
        WARN("Installation BMAD echouee -- verifie ta connexion et Node.js")


def step_bmad_patches() -> None:
    HEAD("5. Patches BMAD (workflows + agent)")
    patches_dir = ROOT / "_bmad-patches"
    bmad_dir = ROOT / "_bmad"

    if not patches_dir.exists():
        OK("Aucun patch a appliquer")
        return

    if not bmad_dir.exists():
        WARN("_bmad/ absent -- patches ignores (BMAD non installe)")
        return

    applied = 0
    for src in patches_dir.rglob("*"):
        if not src.is_file() or src.name == "README.md":
            continue
        rel = src.relative_to(patches_dir)
        dest = bmad_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        OK(f"patch: {rel}")
        applied += 1

    if applied == 0:
        OK("Aucun fichier patch trouve")
    else:
        OK(f"{applied} fichier(s) patch(s) applique(s)")


def step_kanban() -> None:
    HEAD("6. Plugin Kanban Obsidian")
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


# ---------------------------------------------------------------------------
# SonarQube steps
# ---------------------------------------------------------------------------

SONAR_URL = "http://localhost:9000"
SONAR_COMPOSE = "docker-compose.sonar.yml"
_SONAR_TIMEOUT = 300  # 5 minutes max wait


def _sonar_is_up() -> bool:
    """Check if SonarQube is ready (status=UP)."""
    try:
        with urllib.request.urlopen(
            f"{SONAR_URL}/api/system/status", timeout=5
        ) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("status") == "UP"
    except Exception:
        return False


def _env_has_token() -> bool:
    """Return True if .env already contains a non-empty SONAR_TOKEN."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return False
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("SONAR_TOKEN="):
            token = line.partition("=")[2].strip()
            return bool(token)
    return False


def step_sonar_start(docker_ok: bool) -> bool:
    """Start SonarQube via docker compose and wait for it to be ready.

    Returns True if SonarQube is up and ready, False otherwise.
    """
    HEAD("7. SonarQube -- demarrage")

    if not docker_ok:
        WARN("Docker non disponible -- etape SonarQube ignoree")
        return False

    compose_file = ROOT / SONAR_COMPOSE
    if not compose_file.exists():
        WARN(f"{SONAR_COMPOSE} non trouve -- etape SonarQube ignoree")
        return False

    # Already up?
    if _sonar_is_up():
        OK("SonarQube deja pret")
        return True

    print("  >> docker compose up -d ...", end=" ", flush=True)
    result = subprocess.run(
        ["docker", "compose", "-f", SONAR_COMPOSE, "up", "-d"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(_c("ERREUR", "31"))
        if result.stderr.strip():
            print(f"    {result.stderr.strip()[:300]}")
        return False
    print(_c("OK", "32"))

    # Wait for UP (can take 2-3 minutes on first run)
    print(f"  >> Attente SonarQube (jusqu'a {_SONAR_TIMEOUT}s)...", end=" ", flush=True)
    start = time.time()
    dots = 0
    while time.time() - start < _SONAR_TIMEOUT:
        if _sonar_is_up():
            elapsed = int(time.time() - start)
            print(_c(f" UP ({elapsed}s)", "32"))
            OK(f"SonarQube pret en {elapsed}s")
            return True
        time.sleep(10)
        dots += 1
        if dots % 6 == 0:
            print(".", end="", flush=True)

    print(_c(" TIMEOUT", "31"))
    WARN(f"SonarQube n'a pas demarre en {_SONAR_TIMEOUT}s")
    WARN("Verifie : docker compose -f docker-compose.sonar.yml logs sonarqube")
    return False


def step_sonar_provision(project_slug: str, project_name: str) -> bool:
    """Provision SonarQube: create project + token + quality gate + write .env.

    Idempotent: skips if .env already has SONAR_TOKEN.

    Returns True on success.
    """
    HEAD("8. SonarQube -- provisionnement")

    if _env_has_token():
        OK(".env contient deja SONAR_TOKEN -- provisionnement ignore")
        return True

    py = venv_python() or Path(sys.executable)
    result = subprocess.run(
        [
            str(py), "scripts/sonar_setup.py",
            "--init",
            "--url", SONAR_URL,
            "--project-key", project_slug,
            "--project-name", project_name,
            "--env-file", ".env",
        ],
        cwd=ROOT,
    )
    if result.returncode == 0:
        OK("SonarQube provisionne avec succes")
        return True
    else:
        WARN("Provisionnement SonarQube echoue")
        WARN("Lance manuellement : python scripts/sonar_setup.py --init "
             f"--project-key {project_slug} --project-name \"{project_name}\"")
        return False


def step_sonar_pipeline() -> bool:
    """Run the full quality pipeline (pytest + ruff + mypy + sonar-scanner).

    Returns True if all steps passed.
    """
    HEAD("9. SonarQube -- pipeline qualite")

    pipeline = ROOT / "scripts" / "run_sonar_pipeline.sh"
    if not pipeline.exists():
        WARN("run_sonar_pipeline.sh non trouve")
        return False

    bash = shutil.which("bash")
    if not bash:
        WARN("bash non trouve -- pipeline ignore")
        WARN("Lance manuellement : bash scripts/run_sonar_pipeline.sh")
        return False

    result = subprocess.run([bash, str(pipeline)], cwd=ROOT)
    if result.returncode == 0:
        OK("Pipeline qualite reussi")
        return True
    else:
        WARN("Une ou plusieurs etapes du pipeline ont echoue")
        WARN(f"Dashboard : {SONAR_URL}/dashboard")
        return False


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def step_summary(project_name: str, project_slug: str, sonar_ok: bool) -> None:
    sep = "=" * 60
    sonar_note = (
        f"  D. SonarQube : {SONAR_URL}/dashboard?id={project_slug}\n"
        f"     Pipeline   : bash scripts/run_sonar_pipeline.sh"
    ) if sonar_ok else (
        "  D. SonarQube non configure.\n"
        "     Pour l'activer : docker compose -f docker-compose.sonar.yml up -d\n"
        "     Puis            : python scripts/sonar_setup.py --init "
        f"--project-key {project_slug} --project-name \"{project_name}\""
    )

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

{sonar_note}

{sep}
""")


# --- Point d'entree -----------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Installation one-shot BMAD + Obsidian nav + Kanban + SonarQube",
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
    parser.add_argument(
        "--no-bmad", action="store_true",
        help="Ignorer l'installation BMAD (npx bmad-method install)",
    )
    parser.add_argument(
        "--no-sonar", action="store_true",
        help="Ignorer SonarQube (docker compose + provisionnement + pipeline)",
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
        project_name = ROOT.name

    project_slug = slugify(project_name)

    print(_c(f"\n=== BMAD Template -- Installation de '{project_name}' ===", "36;1"))

    uv, _git_ok, node_ok, docker_ok = step_prerequisites()
    step_venv(uv)
    step_setup(project_name)
    if not args.no_bmad:
        step_bmad(node_ok)
        step_bmad_patches()
    if not args.no_kanban:
        step_kanban()

    sonar_ok = False
    if not args.no_sonar:
        sonar_started = step_sonar_start(docker_ok)
        if sonar_started:
            provisioned = step_sonar_provision(project_slug, project_name)
            if provisioned:
                step_sonar_pipeline()
                sonar_ok = True

    step_summary(project_name, project_slug, sonar_ok)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
generate_nav.py — Auto-génère la couche de navigation Obsidian (_nav/).

Déclenchement :
  • Claude Code PostToolUse hook  → après chaque Write/Edit sur _bmad-output/
  • Direct                        → python scripts/generate_nav.py --force

Sources (lecture seule) :
  _bmad-output/implementation-artifacts/sprint-status.yaml
  _bmad-output/implementation-artifacts/*.md   (stories)
  _bmad-output/planning-artifacts/*.md         (PRD, arch, epics)
  docs/IceBox/*.md                             (icebox)
  docs/architecture/*.md

Sorties dans _nav/ :
  00-DASHBOARD.md
  01-PRD-MAP.md
  02-ARCH-MAP.md
  03-ICEBOX-MAP.md
  epics/EPIC-XX-<slug>.md    (un par épic)
  canvas/project-hierarchy.canvas   ← PRD → Épics avec edges
  canvas/current-sprint.canvas      ← sprint actif détaillé

RÈGLE TABLEAUX : ne jamais mettre [[path|label]] dans une cellule de tableau
markdown — le "|" casse le parseur de tableau. Utiliser [[path]] sans label.
Les listes à puces peuvent utiliser [[path|label]] sans problème.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

# ─── Chemins ──────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
ARTIFACTS = ROOT / "_bmad-output" / "implementation-artifacts"
PLANNING = ROOT / "_bmad-output" / "planning-artifacts"
DOCS = ROOT / "docs"
ICEBOX = DOCS / "IceBox"
ARCH_DOCS = DOCS / "architecture"
SPRINT_YAML = ARTIFACTS / "sprint-status.yaml"
NAV = ROOT / "_nav"

# ─── Constantes ───────────────────────────────────────────────────────────────

EPIC_NAMES: dict[int, str] = {
    1: "Fondation & Déploiement",
    2: "Vision Marché & Chronos",
    3: "Détection Signal & Darwin Score",
    4: "Exécution des Trades",
    5: "Protection Capital & Risque",
    6: "Communication Opérateur",
    7: "Audit Trail & Reporting",
    8: "Résilience & Auto-Healing",
    9: "Darwinism — Reporting Intelligence",
    10: "Critical Path — Grand Câblage",
    11: "Testing Infra-Hardening",
    12: "Async Cleanup",
    13: "Real-World Validation",
    14: "Chaos Engineering",
    15: "Feedback Loop",
    16: "SonarQube Integration",
    17: "The Great Decoupling",
    18: "Production Readiness",
    19: "Darwin Formation Alignment",
}

ICEBOX_CATEGORIES: dict[int, str] = {
    1: "Infrastructure & Résilience",
    2: "Intelligence Marché",
    3: "Excellence Exécution",
    4: "Moteur Stratégie",
    5: "Analyse & Tests",
    6: "Recherche Avancée",
    7: "Opérations",
}

STATUS_EMOJI: dict[str, str] = {
    "done": "✅",
    "in-progress": "🔄",
    "review": "👁️",
    "ready-for-dev": "📋",
    "backlog": "📦",
    "optional": "💤",
    "unknown": "❓",
}

CANVAS_COLOR: dict[str, str] = {
    "done": "4",          # vert
    "in-progress": "2",   # orange
    "review": "3",        # jaune
    "ready-for-dev": "5", # cyan
    "backlog": "",        # défaut
    "optional": "",
}

# ─── Hook filter ──────────────────────────────────────────────────────────────

def _is_bmad_write_or_edit(data: dict) -> bool:
    tool = data.get("tool_name", "")
    if tool not in ("Write", "Edit"):
        return False
    fp = str(data.get("tool_input", {}).get("file_path", ""))
    return "_bmad-output" in fp


def needs_regen() -> bool:
    """Vérifie si un fichier BMAD est plus récent que le dashboard généré."""
    dashboard = NAV / "00-DASHBOARD.md"
    if not dashboard.exists():
        return True
    nav_mtime = dashboard.stat().st_mtime
    if SPRINT_YAML.exists() and SPRINT_YAML.stat().st_mtime > nav_mtime:
        return True
    for f in ARTIFACTS.glob("*.md"):
        if f.stat().st_mtime > nav_mtime:
            return True
    return False


# ─── YAML parser minimal ──────────────────────────────────────────────────────

def parse_sprint_status(path: Path) -> dict[str, str]:
    """Retourne {clé: statut} depuis sprint-status.yaml."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    in_dev = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "development_status:":
            in_dev = True
            continue
        if in_dev:
            if line.startswith("  ") or line.startswith("\t"):
                no_comment = stripped.split("#")[0].strip()
                parts = no_comment.split(":", 1)
                if len(parts) == 2:
                    k, v = parts[0].strip(), parts[1].strip()
                    if k and v:
                        result[k] = v
            else:
                in_dev = False
    return result


# ─── Story file parser ────────────────────────────────────────────────────────

def parse_story(path: Path) -> dict:
    """Extrait métadonnées d'un fichier story BMAD."""
    meta: dict = {"path": path, "stem": path.stem}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return meta

    for line in lines[:5]:
        if line.startswith("# "):
            meta["h1"] = line[2:].strip()
            m = re.match(r"Story\s+(\d+)\.(\w+):\s*(.+)", meta["h1"])
            if m:
                meta["epic_num"] = int(m.group(1))
                meta["story_sub"] = m.group(2)
                meta["story_id"] = f"{m.group(1)}.{m.group(2)}"
                full = m.group(3).strip()
                if "—" in full:
                    meta["title_en"] = full.split("—")[0].strip()
                    meta["title_fr"] = full.split("—", 1)[1].strip()
                elif " - " in full:
                    meta["title_en"] = full.split(" - ")[0].strip()
                else:
                    meta["title_en"] = full
            break

    for line in lines[:12]:
        s = line.strip()
        if s.lower().startswith("status:"):
            meta["status"] = s.split(":", 1)[1].strip()
            break
    meta.setdefault("status", "unknown")
    meta.setdefault("epic_num", 0)
    meta.setdefault("title_en", path.stem)
    return meta


# ─── IceBox scanner ───────────────────────────────────────────────────────────

def _icebox_title(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:3]:
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return path.stem.replace("-", " ").title()


def scan_icebox() -> dict[int, list[tuple[Path, str]]]:
    """Retourne {catégorie: [(path, titre)]}."""
    cats: dict[int, list[tuple[Path, str]]] = {}
    if not ICEBOX.exists():
        return cats
    for f in sorted(ICEBOX.glob("*.md")):
        m = re.match(r"^(\d+)-\d+", f.stem)
        if not m:
            continue
        cat = int(m.group(1))
        if cat not in cats:
            cats[cat] = []
        cats[cat].append((f, _icebox_title(f)))
    return cats


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    n = name.lower()
    for s, r in [("à", "a"), ("â", "a"), ("é", "e"), ("è", "e"), ("ê", "e"),
                 ("ë", "e"), ("î", "i"), ("ô", "o"), ("ù", "u"), ("û", "u"),
                 ("ç", "c"), ("&", ""), ("—", ""), ("'", "")]:
        n = n.replace(s, r)
    return re.sub(r"[^a-z0-9]+", "-", n).strip("-")


def _normalize_epic_name(raw: str) -> str:
    """Normalise un nom d'épic extrait des commentaires YAML BMAD.

    - Supprime les annotations entre parenthèses : (+ Darwin Doctrine: RSI…)
    - Garde uniquement le titre principal avant " — "
    - Met en title-case si le nom est entièrement en MAJUSCULES
    """
    clean = re.sub(r"\s*\([^)]+\)", "", raw).strip()
    if " — " in clean:
        clean = clean.split(" — ")[0].strip()
    if clean == clean.upper() and len(clean) > 1:
        clean = clean.title()
    return clean or raw


def _extract_epic_names_from_yaml(path: Path) -> dict[int, str]:
    """Lit les noms d'épics depuis les commentaires de sprint-status.yaml.

    Le format BMAD est :  # Epic N: Nom complet — sous-titre (annotations)
    Exemple :
        # Epic 1: Fondation Projet & Déploiement Sécurisé
        # Epic 17: THE GREAT DECOUPLING — daemon.py Decomposition
        # Epic 19: DARWIN FORMATION ALIGNMENT — La Mise en Conformité
    """
    names: dict[int, str] = {}
    if not path.exists():
        return names
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*#\s*Epic\s+(\d+)\s*:\s*(.+)", line)
        if m:
            names[int(m.group(1))] = _normalize_epic_name(m.group(2).strip())
    return names


def _wikilink(path: Path, label: str = "") -> str:
    """
    Wikilink Obsidian depuis la racine du vault.

    ATTENTION : ne jamais passer label= quand le lien est dans une cellule
    de tableau markdown — le "|" brise le tableau. Dans les tableaux, appeler
    _wikilink(path) sans label.
    """
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        rel = path
    link = str(rel).replace("\\", "/").removesuffix(".md")
    return f"[[{link}|{label}]]" if label else f"[[{link}]]"


def _epic_moc_path(epic_num: int) -> Path:
    name = EPIC_NAMES.get(epic_num, f"epic-{epic_num}")
    return NAV / "epics" / f"EPIC-{epic_num:02d}-{_slugify(name)}.md"


# ─── Générateurs ──────────────────────────────────────────────────────────────

def gen_epic_moc(
    epic_num: int,
    epic_status: str,
    stories: list[dict],
    retro: Path | None,
    now: str,
) -> None:
    name = EPIC_NAMES.get(epic_num, f"Epic {epic_num}")
    done = sum(1 for s in stories if s["status"] == "done")
    total = len(stories)
    emoji = STATUS_EMOJI.get(epic_status, "❓")

    # Navigation : [[PRD]] = seul wikilink "montant" (hub du graphe)
    # [[Dashboard]] aussi pour navigation mais en dehors du tableau = pas de problème
    prd_link = _wikilink(PLANNING / "prd.md", "PRD")
    dash_link = _wikilink(NAV / "00-DASHBOARD.md", "Dashboard")

    lines = [
        "---",
        f'nav_type: "epic-map"',
        f"epic: {epic_num}",
        f'epic_name: "{name}"',
        f"status: {epic_status}",
        f'generated: "{now}"',
        "---",
        "",
        f"# Epic {epic_num:02d} — {name}",
        "",
        f"> {emoji} **{epic_status.upper()}** · {done}/{total} stories complétées",
        "",
        # Liens de navigation hors tableau → labels autorisés
        f"← {dash_link} · {prd_link}",
        "",
        "## Stories",
        "",
        # TABLEAUX : wikilinks SANS label pour éviter le bug "|" du parseur markdown
        "| # | Titre | Statut | Lien |",
        "|---|-------|--------|------|",
    ]

    for s in stories:
        sid = s.get("story_id", "?")
        title = s.get("title_en", s["stem"])
        st = s.get("status", "unknown")
        em = STATUS_EMOJI.get(st, "❓")
        # Pas de label dans le tableau → [[path]] sans "|"
        link = _wikilink(s["path"])
        lines.append(f"| {sid} | {title} | {em} {st} | {link} |")

    lines += [""]

    if retro:
        lines += [
            "## Rétrospective",
            "",
            # Hors tableau → label autorisé
            _wikilink(retro, f"Rétro Epic {epic_num}"),
            "",
        ]

    lines += [
        "---",
        "_Généré automatiquement par generate\\_nav.py — ne pas modifier_",
    ]

    out = _epic_moc_path(epic_num)
    out.write_text("\n".join(lines), encoding="utf-8")


def gen_dashboard(
    stories_by_epic: dict[int, list[dict]],
    epic_statuses: dict[int, str],
    now: str,
) -> None:
    all_s = [s for ss in stories_by_epic.values() for s in ss]
    done = sum(1 for s in all_s if s["status"] == "done")
    wip = sum(1 for s in all_s if s["status"] == "in-progress")
    review = sum(1 for s in all_s if s["status"] == "review")
    total = len(all_s)
    pct = int(done / total * 100) if total else 0

    current_epics = sorted(e for e, st in epic_statuses.items() if st == "in-progress")

    lines = [
        "---",
        'nav_type: "dashboard"',
        f'generated: "{now}"',
        "---",
        "",
        "# LaurianBot — Dashboard Projet",
        "",
        f"> Généré automatiquement le {now}",
        "",
        "## Statut Global",
        "",
        "| Métrique | Valeur |",
        "|----------|--------|",
        f"| Stories totales | {total} |",
        f"| Done | {done} ({pct}%) |",
        f"| Review | {review} |",
        f"| In-progress | {wip} |",
        f"| Backlog | {total - done - wip - review} |",
        "",
    ]

    if current_epics:
        lines += ["## Epic(s) Actif(s)", ""]
        for e in current_epics:
            name = EPIC_NAMES.get(e, f"Epic {e}")
            stories = stories_by_epic.get(e, [])
            # Hors tableau → label autorisé
            lines += [
                f"### {_wikilink(_epic_moc_path(e), f'Epic {e:02d} — {name}')}",
                "",
            ]
            for s in stories:
                em = STATUS_EMOJI.get(s["status"], "❓")
                title = s.get("title_en", s["stem"])
                # Hors tableau → label autorisé
                lines.append(f"- {em} {_wikilink(s['path'], title)}")
            lines.append("")

    lines += [
        "## Tous les Epics",
        "",
        "| # | Nom | Statut | Stories | MOC |",
        "|---|-----|--------|---------|-----|",
    ]

    for en in sorted(stories_by_epic):
        name = EPIC_NAMES.get(en, f"Epic {en}")
        est = epic_statuses.get(en, "unknown")
        em = STATUS_EMOJI.get(est, "❓")
        ss = stories_by_epic.get(en, [])
        dc = sum(1 for s in ss if s["status"] == "done")
        # TABLEAU → pas de label dans le wikilink
        moc = _wikilink(_epic_moc_path(en))
        lines.append(f"| {en:02d} | {name} | {em} {est} | {dc}/{len(ss)} | {moc} |")

    lines += [
        "",
        "## Documents Cles",
        "",
        # Liste à puces hors tableau → labels autorisés
        f"- {_wikilink(PLANNING / 'prd.md', 'PRD complet')}",
        f"- {_wikilink(PLANNING / 'architecture.md', 'Architecture')}",
        f"- {_wikilink(PLANNING / 'epics.md', 'Breakdown Epics')}",
        f"- {_wikilink(DOCS / 'DARWIN_STRATEGY v17.md', 'Darwin Strategy v17')}",
        f"- {_wikilink(DOCS / 'OPERATOR_RUNBOOK.md', 'Operator Runbook')}",
        f"- {_wikilink(ARCH_DOCS / '00-index.md', 'Architecture Diagrams')}",
        f"- {_wikilink(NAV / '03-ICEBOX-MAP.md', 'IceBox')}",
        "",
        "## Vues Obsidian",
        "",
        f"- {_wikilink(NAV / '01-PRD-MAP.md', 'PRD Map')}",
        f"- {_wikilink(NAV / '02-ARCH-MAP.md', 'Architecture Map')}",
        f"- {_wikilink(NAV / '03-ICEBOX-MAP.md', 'IceBox Map')}",
        f"- [[_nav/canvas/project-hierarchy|Canvas — Hierarchie PRD -> Epics]]",
        f"- [[_nav/canvas/current-sprint|Canvas — Sprint Actif]]",
        "",
        "---",
        "_Genere automatiquement par generate\\_nav.py — ne pas modifier_",
    ]

    (NAV / "00-DASHBOARD.md").write_text("\n".join(lines), encoding="utf-8")


def gen_prd_map(now: str) -> None:
    prd = PLANNING / "prd.md"
    sections: list[str] = []
    if prd.exists():
        for line in prd.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("## "):
                sections.append(line[3:].strip())

    lines = [
        "---",
        'nav_type: "prd-map"',
        f'generated: "{now}"',
        "---",
        "",
        "# PRD — Map des Exigences",
        "",
        f"> Source : {_wikilink(prd, 'Product Requirements Document')}",
        "",
        "## Sections PRD",
        "",
    ]
    if sections:
        for s in sections:
            lines.append(f"- {_wikilink(prd, s)}")
    else:
        lines.append(f"- {_wikilink(prd, 'Ouvrir le PRD complet')}")

    lines += [
        "",
        "## Documents Lies",
        "",
        f"- {_wikilink(PLANNING / 'product-brief-LaurianBot-2026-02-01.md', 'Product Brief')}",
        f"- {_wikilink(PLANNING / 'implementation-readiness-report-2026-02-02.md', 'Readiness Report')}",
        f"- {_wikilink(PLANNING / 'architecture.md', 'Architecture')}",
        "",
        f"← {_wikilink(NAV / '00-DASHBOARD.md', 'Dashboard')}",
        "",
        "---",
        "_Genere automatiquement par generate\\_nav.py — ne pas modifier_",
    ]
    (NAV / "01-PRD-MAP.md").write_text("\n".join(lines), encoding="utf-8")


def gen_arch_map(now: str) -> None:
    arch_files = sorted(ARCH_DOCS.glob("*.md")) if ARCH_DOCS.exists() else []
    darwin_docs = (
        sorted((DOCS / "strategies" / "darwin").glob("*.md"))
        if (DOCS / "strategies" / "darwin").exists() else []
    )
    spike_docs = sorted(DOCS.glob("spike-*.md"))

    lines = [
        "---",
        'nav_type: "arch-map"',
        f'generated: "{now}"',
        "---",
        "",
        "# Architecture — Map des Decisions",
        "",
        f"> Source : {_wikilink(PLANNING / 'architecture.md', 'Architecture Decision Document')}",
        "",
        "## Diagrammes",
        "",
    ]
    for f in arch_files:
        title = f.stem.replace("-", " ").title()
        lines.append(f"- {_wikilink(f, title)}")

    if darwin_docs:
        lines += ["", "## Darwin Strategy Docs", ""]
        for f in darwin_docs:
            title = f.stem.replace("-", " ").title()
            lines.append(f"- {_wikilink(f, title)}")

    if spike_docs:
        lines += ["", "## Spikes & Recherche", ""]
        for f in spike_docs:
            title = f.stem.replace("-", " ").replace("spike ", "").title()
            lines.append(f"- {_wikilink(f, f'Spike: {title}')}")

    lines += [
        "",
        f"← {_wikilink(NAV / '00-DASHBOARD.md', 'Dashboard')}",
        "",
        "---",
        "_Genere automatiquement par generate\\_nav.py — ne pas modifier_",
    ]
    (NAV / "02-ARCH-MAP.md").write_text("\n".join(lines), encoding="utf-8")


def gen_icebox_map(icebox_data: dict[int, list[tuple[Path, str]]], now: str) -> None:
    total = sum(len(v) for v in icebox_data.values())

    lines = [
        "---",
        'nav_type: "icebox-map"',
        f'generated: "{now}"',
        f"total_items: {total}",
        "---",
        "",
        "# IceBox — Fonctionnalites Futures",
        "",
        f"> {total} idees · "
        f"{_wikilink(ICEBOX / '00-MASTER-PRIORITIES.md', 'Master Priorities')}",
        "",
    ]

    for cat_num in sorted(icebox_data):
        cat_name = ICEBOX_CATEGORIES.get(cat_num, f"Categorie {cat_num}")
        items = icebox_data[cat_num]
        lines += [f"## {cat_num}. {cat_name}", ""]
        for path, title in items:
            lines.append(f"- {_wikilink(path, title)}")
        lines.append("")

    lines += [
        f"← {_wikilink(NAV / '00-DASHBOARD.md', 'Dashboard')}",
        "",
        "---",
        "_Genere automatiquement par generate\\_nav.py — ne pas modifier_",
    ]
    (NAV / "03-ICEBOX-MAP.md").write_text("\n".join(lines), encoding="utf-8")


# ─── Canvas helpers ────────────────────────────────────────────────────────────

def _canvas_file_node(
    node_id: str, file_path: Path,
    x: int, y: int, w: int = 300, h: int = 120, color: str = "",
) -> dict:
    try:
        rel = str(file_path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        rel = str(file_path)
    node: dict = {"id": node_id, "type": "file", "file": rel,
                  "x": x, "y": y, "width": w, "height": h}
    if color:
        node["color"] = color
    return node


def _canvas_text_node(
    node_id: str, text: str,
    x: int, y: int, w: int = 260, h: int = 80, color: str = "",
) -> dict:
    node: dict = {"id": node_id, "type": "text", "text": text,
                  "x": x, "y": y, "width": w, "height": h}
    if color:
        node["color"] = color
    return node


def _canvas_group_node(
    node_id: str, label: str,
    x: int, y: int, w: int, h: int, color: str = "",
) -> dict:
    node: dict = {"id": node_id, "type": "group", "label": label,
                  "x": x, "y": y, "width": w, "height": h}
    if color:
        node["color"] = color
    return node


def _edge(eid: str, from_id: str, to_id: str,
          from_side: str = "bottom", to_side: str = "top",
          label: str = "") -> dict:
    e: dict = {"id": eid, "fromNode": from_id, "fromSide": from_side,
               "toNode": to_id, "toSide": to_side}
    if label:
        e["label"] = label
    return e


# ─── Canvas : Hiérarchie PRD → Épics ─────────────────────────────────────────

def gen_hierarchy_canvas(
    stories_by_epic: dict[int, list[dict]],
    epic_statuses: dict[int, str],
    now: str,
) -> None:
    """
    Canvas arbre : PRD au centre haut → 19 épics en 2 rangées → edges explicites.

    Layout :
      y = -380 : Dashboard  |  PRD (centre)  |  Architecture
      y =    0 : Epics 01-10 (rangée 1, centrée)
      y =  210 : Epics 11-19 (rangée 2, centrée)
    """
    nodes: list[dict] = []
    edges: list[dict] = []

    # ── Rangée 0 : documents piliers ────────────────────────────────────────
    nodes.append(_canvas_file_node(
        "dashboard", NAV / "00-DASHBOARD.md",
        x=-540, y=-380, w=240, h=75, color="6",
    ))
    nodes.append(_canvas_file_node(
        "prd", PLANNING / "prd.md",
        x=-120, y=-380, w=240, h=75, color="5",
    ))
    nodes.append(_canvas_file_node(
        "arch", PLANNING / "architecture.md",
        x=200, y=-380, w=260, h=75, color="5",
    ))

    # Edges piliers
    edges.append(_edge("e-dash-prd", "dashboard", "prd", "right", "left"))
    edges.append(_edge("e-prd-arch", "prd", "arch", "right", "left"))

    # ── Rangée 1 : Épics 01-10 ──────────────────────────────────────────────
    epic_nums = sorted(stories_by_epic.keys())
    row1 = epic_nums[:10]
    row2 = epic_nums[10:]

    EW, EH = 220, 85
    E_STEP = EW + 20  # 240

    # Centrer row1 horizontalement autour de x=0
    row1_total_w = len(row1) * E_STEP - 20
    x1_start = -(row1_total_w // 2)

    for i, en in enumerate(row1):
        x = x1_start + i * E_STEP
        y = 0
        status = epic_statuses.get(en, "unknown")
        color = CANVAS_COLOR.get(status, "")
        nid = f"epic-{en}"
        nodes.append(_canvas_file_node(nid, _epic_moc_path(en),
                                       x=x, y=y, w=EW, h=EH, color=color))
        edges.append(_edge(f"e-prd-{en}", "prd", nid))

    # ── Rangée 2 : Épics 11-19 ──────────────────────────────────────────────
    if row2:
        row2_total_w = len(row2) * E_STEP - 20
        x2_start = -(row2_total_w // 2)
        y2 = EH + 125  # 210

        for i, en in enumerate(row2):
            x = x2_start + i * E_STEP
            status = epic_statuses.get(en, "unknown")
            color = CANVAS_COLOR.get(status, "")
            nid = f"epic-{en}"
            nodes.append(_canvas_file_node(nid, _epic_moc_path(en),
                                           x=x, y=y2, w=EW, h=EH, color=color))
            edges.append(_edge(f"e-prd-{en}", "prd", nid))

    canvas = {"nodes": nodes, "edges": edges}
    out = NAV / "canvas" / "project-hierarchy.canvas"
    out.write_text(json.dumps(canvas, indent=2, ensure_ascii=False), encoding="utf-8")


# ─── Canvas : Sprint actif ────────────────────────────────────────────────────

def gen_sprint_canvas(
    stories_by_epic: dict[int, list[dict]],
    epic_statuses: dict[int, str],
    now: str,
) -> None:
    """Canvas sprint : épics en cours + leurs stories avec edges."""
    nodes: list[dict] = []
    edges: list[dict] = []

    current_epics = sorted(e for e, st in epic_statuses.items() if st == "in-progress")
    if not current_epics:
        current_epics = [max(stories_by_epic.keys())]

    # Docs de référence à gauche
    ref_docs = [
        ("ref-prd",  PLANNING / "prd.md",         "5"),
        ("ref-arch", PLANNING / "architecture.md", "5"),
        ("ref-dash", NAV / "00-DASHBOARD.md",      "6"),
    ]
    for i, (nid, p, color) in enumerate(ref_docs):
        nodes.append(_canvas_file_node(nid, p, x=-420, y=i * 140,
                                       w=260, h=110, color=color))

    # Pour chaque épic actif : header + stories + edges
    x_offset = 0
    for en in current_epics:
        name = EPIC_NAMES.get(en, f"Epic {en}")
        epic_status = epic_statuses.get(en, "in-progress")
        epic_color = CANVAS_COLOR.get(epic_status, "2")

        # Node épic MOC (header cliquable)
        epic_nid = f"ehdr-{en}"
        nodes.append(_canvas_file_node(
            epic_nid, _epic_moc_path(en),
            x=x_offset, y=-170, w=320, h=100, color=epic_color,
        ))

        # Edge PRD → Epic header
        edges.append(_edge(f"e-ref-{en}", "ref-prd", epic_nid, "right", "left"))

        # Stories avec edges depuis le header
        stories = stories_by_epic.get(en, [])
        for row, s in enumerate(stories):
            status = s.get("status", "unknown")
            color = CANVAS_COLOR.get(status, "")
            story_nid = f"s-{en}-{row}"
            nodes.append(_canvas_file_node(
                story_nid, s["path"],
                x=x_offset, y=row * 140,
                w=320, h=115, color=color,
            ))
            edges.append(_edge(f"e-{en}-s{row}", epic_nid, story_nid,
                               "bottom", "top"))

        x_offset += 380

    canvas = {"nodes": nodes, "edges": edges}
    out = NAV / "canvas" / "current-sprint.canvas"
    out.write_text(json.dumps(canvas, indent=2, ensure_ascii=False), encoding="utf-8")


# ─── Orchestrateur ────────────────────────────────────────────────────────────

def generate_all() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Auto-découverte des noms d'épics depuis les commentaires YAML BMAD.
    # Les noms extraits prennent le dessus sur les valeurs hardcodées ci-dessus.
    discovered = _extract_epic_names_from_yaml(SPRINT_YAML)
    EPIC_NAMES.update(discovered)

    NAV.mkdir(exist_ok=True)
    (NAV / "epics").mkdir(exist_ok=True)
    (NAV / "canvas").mkdir(exist_ok=True)

    statuses = parse_sprint_status(SPRINT_YAML)

    epic_statuses: dict[int, str] = {}
    for k, v in statuses.items():
        m = re.match(r"^epic-(\d+)$", k)
        if m:
            epic_statuses[int(m.group(1))] = v

    stories_by_epic: dict[int, list[dict]] = {}
    retros: dict[int, Path] = {}

    for f in sorted(ARTIFACTS.glob("*.md")):
        stem = f.stem
        m = re.match(r"^(\d+)-", stem)
        if not m:
            continue
        epic_num = int(m.group(1))
        if "retro" in stem:
            retros[epic_num] = f
            continue
        meta = parse_story(f)
        if stem in statuses:
            meta["status"] = statuses[stem]
        meta.setdefault("epic_num", epic_num)
        if epic_num not in stories_by_epic:
            stories_by_epic[epic_num] = []
        stories_by_epic[epic_num].append(meta)

    for en in stories_by_epic:
        stories_by_epic[en].sort(key=lambda s: s.get("story_sub", "0"))

    for en in sorted(stories_by_epic):
        gen_epic_moc(
            en,
            epic_statuses.get(en, "unknown"),
            stories_by_epic[en],
            retros.get(en),
            now,
        )

    icebox_data = scan_icebox()

    gen_dashboard(stories_by_epic, epic_statuses, now)
    gen_prd_map(now)
    gen_arch_map(now)
    gen_icebox_map(icebox_data, now)
    gen_hierarchy_canvas(stories_by_epic, epic_statuses, now)
    gen_sprint_canvas(stories_by_epic, epic_statuses, now)

    n_epics = len(stories_by_epic)
    n_stories = sum(len(v) for v in stories_by_epic.values())
    n_icebox = sum(len(v) for v in icebox_data.values())
    print(
        f"[generate_nav] OK {n_epics} epics / {n_stories} stories / "
        f"{n_icebox} icebox -- {now}",
        flush=True,
    )


# ─── Point d'entrée ───────────────────────────────────────────────────────────

def main() -> None:
    force = "--force" in sys.argv

    if force:
        generate_all()
        return

    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    if data and not _is_bmad_write_or_edit(data):
        sys.exit(0)

    if not needs_regen():
        sys.exit(0)

    generate_all()


if __name__ == "__main__":
    main()

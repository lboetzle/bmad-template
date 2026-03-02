#!/usr/bin/env python3
"""
Claude Code session logger — capture la conversation complète + les transactions.

Hooks utilisés :
  UserPromptSubmit  → message utilisateur
  PostToolUse       → appel outil (Bash, Read, Write, Edit, Grep, Glob, …)
  Stop              → réponse texte finale de Claude (depuis transcript)

Fichiers produits :
  docs/sessions/YYYY-MM-DD_HHMMSS_<session8>.md  — log de session
  docs/sessions/.state.json                       — état de suivi (gitignore)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

SESSIONS_DIR = Path(__file__).parent.parent / "docs" / "sessions"
STATE_FILE = SESSIONS_DIR / ".state.json"

MAX_OUTPUT_LINES = 100

# ─── Icônes markdown ──────────────────────────────────────────────────────────

TOOL_ICONS: dict[str, str] = {
    "Bash": "🖥️",
    "Read": "📖",
    "Write": "✏️",
    "Edit": "🔧",
    "Grep": "🔍",
    "Glob": "🗂️",
    "WebFetch": "🌐",
    "WebSearch": "🌐",
    "Agent": "🤖",
}


# ─── State helpers ────────────────────────────────────────────────────────────

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


# ─── Session file ──────────────────────────────────────────────────────────────

def _get_or_create_session(session_id: str) -> tuple[Path, dict]:
    """Return (filepath, state). Creates file + state entry on first call."""
    state = _load_state()

    if session_id in state:
        filepath = SESSIONS_DIR / state[session_id]["filename"]
        return filepath, state

    # Premier appel pour cette session
    ts = datetime.now()
    filename = f"{ts.strftime('%Y-%m-%d_%H%M%S')}_{session_id[:8]}.md"
    filepath = SESSIONS_DIR / filename
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    filepath.write_text(
        f"# Session `{session_id[:8]}`\n\n"
        f"| Champ | Valeur |\n"
        f"|-------|--------|\n"
        f"| Démarrée le | {ts.strftime('%Y-%m-%d %H:%M:%S')} |\n"
        f"| Session ID  | `{session_id}` |\n"
        f"| Fichier     | `{filename}` |\n\n"
        "---\n",
        encoding="utf-8",
    )

    state[session_id] = {
        "filename": filename,
        "transcript_line": 0,   # prochain index à lire dans le JSONL
        "last_assistant_idx": -1,
    }
    _save_state(state)
    return filepath, state


def _append(filepath: Path, text: str) -> None:
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(text)


# ─── Transcript reader ─────────────────────────────────────────────────────────

def _read_new_assistant_texts(
    transcript_path: str, from_line: int
) -> tuple[list[str], int]:
    """
    Lit les nouvelles lignes du JSONL depuis from_line.
    Retourne les textes des blocs assistant non-tool, et le nouvel index de ligne.
    """
    path = Path(transcript_path)
    if not path.exists():
        return [], from_line

    texts: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    new_line = from_line

    for raw in lines[from_line:]:
        new_line += 1
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue

        # Supporte format direct {role, content} et format enveloppé {message: {...}}
        if "message" in entry:
            msg = entry["message"]
        else:
            msg = entry

        role = msg.get("role", "")
        if role != "assistant":
            continue

        content = msg.get("content", "")
        if isinstance(content, str) and content.strip():
            texts.append(content.strip())
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    txt = block.get("text", "").strip()
                    if txt:
                        texts.append(txt)

    return texts, new_line


def _flush_assistant_texts(
    filepath: Path, transcript_path: str | None, state: dict, session_id: str
) -> None:
    """Lit et logue les nouveaux textes assistant depuis le transcript."""
    if not transcript_path:
        return

    from_line = state[session_id].get("transcript_line", 0)
    texts, new_line = _read_new_assistant_texts(transcript_path, from_line)

    if new_line != from_line:
        state[session_id]["transcript_line"] = new_line
        _save_state(state)

    for text in texts:
        ts = datetime.now().strftime("%H:%M:%S")
        _append(
            filepath,
            f"\n## 🤖 Claude — {ts}\n\n{text}\n\n---\n",
        )


# ─── Formatage ────────────────────────────────────────────────────────────────

def _truncate(output: str) -> str:
    lines = output.splitlines()
    if len(lines) <= MAX_OUTPUT_LINES:
        return output
    skipped = len(lines) - MAX_OUTPUT_LINES
    return "\n".join(lines[:MAX_OUTPUT_LINES]) + f"\n\n_… {skipped} ligne(s) supprimée(s)_"


def _format_tool_input(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Bash":
        cmd = tool_input.get("command", "").strip()
        desc = tool_input.get("description", "").strip()
        block = f"```bash\n{cmd}\n```"
        return (f"> {desc}\n\n" + block) if desc else block

    if tool_name in ("Read", "Write", "Edit"):
        path = (
            tool_input.get("file_path")
            or tool_input.get("path")
            or ""
        )
        label = f"`{path}`" if path else ""
        rest = {k: v for k, v in tool_input.items() if k not in ("file_path", "path", "content", "new_string", "old_string")}
        out = label
        if rest:
            out += f"\n\n```json\n{json.dumps(rest, indent=2, ensure_ascii=False)}\n```"
        return out or "_aucun paramètre_"

    if tool_name in ("Grep", "Glob"):
        pattern = tool_input.get("pattern", "")
        search_path = tool_input.get("path", "")
        return f"Pattern : `{pattern}`" + (f"  |  Path : `{search_path}`" if search_path else "")

    # Fallback générique
    try:
        return f"```json\n{json.dumps(tool_input, indent=2, ensure_ascii=False)}\n```"
    except Exception:
        return str(tool_input)


def _format_tool_response(tool_name: str, tool_response: object) -> str:
    if isinstance(tool_response, dict):
        output = tool_response.get("output") or tool_response.get("result") or ""
        if not output:
            output = json.dumps(tool_response, ensure_ascii=False)
    else:
        output = str(tool_response) if tool_response is not None else ""

    output = output.strip()
    if not output:
        return "_pas de sortie_"
    return f"```\n{_truncate(output)}\n```"


# ─── Handlers ─────────────────────────────────────────────────────────────────

def handle_user_prompt(data: dict) -> None:
    session_id = data.get("session_id", "unknown")
    filepath, _ = _get_or_create_session(session_id)

    # Le contenu peut être une chaîne ou une liste de blocs
    prompt = data.get("prompt", "") or ""
    if isinstance(prompt, list):
        parts = [
            b.get("text", "")
            for b in prompt
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        prompt = "\n".join(parts)

    prompt = prompt.strip()
    if not prompt:
        return

    ts = datetime.now().strftime("%H:%M:%S")
    _append(filepath, f"\n## 👤 Utilisateur — {ts}\n\n{prompt}\n\n---\n")


def handle_post_tool_use(data: dict) -> None:
    session_id = data.get("session_id", "unknown")
    filepath, state = _get_or_create_session(session_id)

    # 1. Éventuels textes assistant précédant cet appel outil
    _flush_assistant_texts(filepath, data.get("transcript_path"), state, session_id)

    tool_name = data.get("tool_name", "?")
    tool_input = data.get("tool_input") or {}
    tool_response = data.get("tool_response")

    icon = TOOL_ICONS.get(tool_name, "⚙️")
    ts = datetime.now().strftime("%H:%M:%S")

    input_block = _format_tool_input(tool_name, tool_input)
    response_block = _format_tool_response(tool_name, tool_response)

    _append(
        filepath,
        f"\n### {icon} `{tool_name}` — {ts}\n\n"
        f"{input_block}\n\n"
        f"**Résultat :**\n\n{response_block}\n\n---\n",
    )


def handle_stop(data: dict) -> None:
    session_id = data.get("session_id", "unknown")
    filepath, state = _get_or_create_session(session_id)

    # Vider le reste du transcript (réponse finale de Claude)
    _flush_assistant_texts(filepath, data.get("transcript_path"), state, session_id)

    ts = datetime.now().strftime("%H:%M:%S")
    _append(filepath, f"\n_— Fin du tour · {ts} —_\n\n---\n")


# ─── Point d'entrée ───────────────────────────────────────────────────────────

def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # Nom de l'événement (plusieurs noms possibles selon la version de Claude Code)
    event = (
        data.get("hook_event_name")
        or data.get("event")
        or data.get("hook_type")
        or ""
    )

    # Inférence de secours à partir de la forme du payload
    if not event:
        if "tool_name" in data and "tool_response" in data:
            event = "PostToolUse"
        elif "prompt" in data:
            event = "UserPromptSubmit"
        elif data.get("stop_hook_active") is not None or "stop_reason" in data:
            event = "Stop"

    if event == "UserPromptSubmit":
        handle_user_prompt(data)
    elif event == "PostToolUse":
        handle_post_tool_use(data)
    elif event == "Stop":
        handle_stop(data)

    sys.exit(0)


if __name__ == "__main__":
    main()

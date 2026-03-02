"""sonar_setup.py -- SonarQube first-run setup + Quality Gate configuration.

Two modes:

  --init mode (first install):
    Performs full first-run setup using admin:admin credentials:
      1. Change admin password to a generated secure password
      2. Generate a scanner token
      3. Create the project
      4. Configure the Quality Gate
      5. Write SONAR_TOKEN and SONAR_ADMIN_PASSWORD to .env

  Standard mode (ongoing use):
    Updates Quality Gate conditions only (requires --token).

Usage:
    # First-run (called by install.py):
    python scripts/sonar_setup.py --init \\
        --project-key myproject --project-name "My Project" \\
        --url http://localhost:9000 --env-file .env

    # Ongoing / CI (update quality gate only):
    python scripts/sonar_setup.py \\
        --url http://localhost:9000 --token <token> \\
        --gate-name "My Project Fortress" --project-key myproject

Exit codes:
    0 -- Success
    1 -- Error (connection failed, auth failure, etc.)
"""

from __future__ import annotations

import argparse
import base64
import json
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Quality Gate desired conditions (SSOT)
# ---------------------------------------------------------------------------

QUALITY_GATE_CONDITIONS: list[dict[str, str]] = [
    {"metric": "new_coverage", "op": "LT", "error": "80"},
    {"metric": "new_violations", "op": "GT", "error": "0"},
]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _make_request(
    base_url: str,
    token: str,
    method: str,
    path: str,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Authenticated API call using Bearer token."""
    url = f"{base_url.rstrip('/')}{path}"
    data: bytes | None = None

    if method == "GET" and params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    elif method == "POST" and params:
        data = urllib.parse.urlencode(params).encode("utf-8")

    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8").strip()
        return json.loads(body) if body else {}


def _make_request_basic(
    base_url: str,
    username: str,
    password: str,
    method: str,
    path: str,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Authenticated API call using Basic auth (for first-run with admin:admin)."""
    url = f"{base_url.rstrip('/')}{path}"
    data: bytes | None = None

    if method == "GET" and params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    elif method == "POST" and params:
        data = urllib.parse.urlencode(params).encode("utf-8")

    req = urllib.request.Request(url, data=data, method=method)
    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    req.add_header("Authorization", f"Basic {credentials}")
    if data:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8").strip()
        return json.loads(body) if body else {}


# ---------------------------------------------------------------------------
# Quality Gate operations
# ---------------------------------------------------------------------------

def _create_or_get_gate(base_url: str, token: str, gate_name: str) -> int:
    try:
        response = _make_request(
            base_url, token, "POST", "/api/qualitygates/create", {"name": gate_name}
        )
        gate_id: int = response["id"]
        print(f"  + Quality Gate '{gate_name}' created (id={gate_id})")
        return gate_id
    except urllib.error.HTTPError as exc:
        if exc.code == 400:
            gate_id = _get_gate_id(base_url, token, gate_name)
            print(f"  ~ Quality Gate '{gate_name}' already exists (id={gate_id})")
            return gate_id
        raise


def _get_gate_id(base_url: str, token: str, gate_name: str) -> int:
    response = _make_request(base_url, token, "GET", "/api/qualitygates/list")
    for gate in response.get("qualitygates", []):
        if gate["name"] == gate_name:
            return int(gate["id"])
    raise RuntimeError(f"Quality Gate '{gate_name}' not found")


def _apply_conditions(
    base_url: str,
    token: str,
    gate_name: str,
) -> tuple[int, int]:
    response = _make_request(
        base_url, token, "GET", "/api/qualitygates/show", {"name": gate_name}
    )
    existing = list(response.get("conditions", []))

    created = 0
    updated = 0
    for condition in QUALITY_GATE_CONDITIONS:
        metric = condition["metric"]
        op = condition["op"]
        error = condition["error"]

        existing_match = next(
            (c for c in existing if c.get("metric") == metric and c.get("op") == op),
            None,
        )

        if existing_match is not None:
            if existing_match.get("error") == error:
                print(f"  ~ Condition {metric} {op} {error} already correct")
                continue
            _make_request(
                base_url, token, "POST",
                "/api/qualitygates/delete_condition",
                {"id": str(existing_match["id"])},
            )
            updated += 1
        else:
            created += 1

        _make_request(
            base_url, token, "POST",
            "/api/qualitygates/create_condition",
            {"gateName": gate_name, "metric": metric, "op": op, "error": error},
        )
        verb = "Updated" if existing_match is not None else "Created"
        print(f"  + {verb} condition: {metric} {op} {error}")

    return created, updated


def setup_quality_gate(
    base_url: str,
    token: str,
    gate_name: str,
    project_key: str,
) -> dict[str, Any]:
    gate_id = _create_or_get_gate(base_url, token, gate_name)
    created, updated = _apply_conditions(base_url, token, gate_name)

    _make_request(
        base_url, token, "POST",
        "/api/qualitygates/select",
        {"projectKey": project_key, "gateName": gate_name},
    )
    print(f"  + Quality Gate '{gate_name}' associated with '{project_key}'")

    return {
        "gate_name": gate_name,
        "gate_id": gate_id,
        "conditions_created": created,
        "conditions_updated": updated,
    }


# ---------------------------------------------------------------------------
# First-run initialization
# ---------------------------------------------------------------------------

def _generate_password() -> str:
    """Generate a secure random password acceptable by SonarQube (min 12 chars, mixed)."""
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    # Ensure at least one uppercase, one digit, one special char
    core = "".join(secrets.choice(alphabet) for _ in range(14))
    return f"Sq@{core}"


def first_run_init(
    base_url: str,
    project_key: str,
    project_name: str,
    env_file: Path,
) -> str:
    """Full first-run setup using admin:admin.

    Steps:
      1. Change admin password
      2. Generate scanner token
      3. Create project
      4. Configure quality gate
      5. Write .env

    Returns:
        The generated SONAR_TOKEN value.
    """
    gate_name = f"{project_name} Fortress"

    print("  >> Changing admin password...")
    new_password = _generate_password()
    _make_request_basic(
        base_url, "admin", "admin", "POST",
        "/api/users/change_password",
        {"login": "admin", "previousPassword": "admin", "password": new_password},
    )
    print("  + Admin password changed")

    print("  >> Generating scanner token...")
    response = _make_request_basic(
        base_url, "admin", new_password, "POST",
        "/api/user_tokens/generate",
        {"name": "scanner", "login": "admin"},
    )
    token: str = response["token"]
    print(f"  + Token 'scanner' generated")

    print(f"  >> Creating project '{project_key}'...")
    try:
        _make_request(
            base_url, token, "POST",
            "/api/projects/create",
            {"name": project_name, "project": project_key},
        )
        print(f"  + Project '{project_key}' created")
    except urllib.error.HTTPError as exc:
        if exc.code == 400:
            print(f"  ~ Project '{project_key}' already exists")
        else:
            raise

    print(f"  >> Configuring Quality Gate '{gate_name}'...")
    setup_quality_gate(base_url, token, gate_name, project_key)

    # Write .env
    _write_env(env_file, token, new_password, base_url)

    return token


def _write_env(env_file: Path, token: str, admin_password: str, base_url: str) -> None:
    """Write (or update) SONAR_TOKEN and SONAR_ADMIN_PASSWORD in .env."""
    existing: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()

    existing["SONAR_HOST_URL"] = base_url
    existing["SONAR_TOKEN"] = token
    existing["SONAR_ADMIN_PASSWORD"] = admin_password

    lines = [f"{k}={v}" for k, v in existing.items()]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  + .env written ({env_file})")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SonarQube setup: first-run init or quality gate update",
    )
    parser.add_argument(
        "--url", default="http://localhost:9000",
        help="SonarQube base URL (default: http://localhost:9000)",
    )
    parser.add_argument("--token", help="Bearer token (required unless --init)")
    parser.add_argument(
        "--init", action="store_true",
        help="First-run mode: change admin password + generate token + create project",
    )
    parser.add_argument("--project-key", required=True, help="SonarQube project key")
    parser.add_argument("--project-name", help="Project display name (required with --init)")
    parser.add_argument(
        "--gate-name", help="Quality Gate name (default: '<project-name> Fortress')",
    )
    parser.add_argument(
        "--env-file", type=Path, default=Path(".env"),
        help="Path to .env file (default: .env, used with --init)",
    )
    args = parser.parse_args(argv)

    project_name = args.project_name or args.project_key
    gate_name = args.gate_name or f"{project_name} Fortress"

    try:
        if args.init:
            token = first_run_init(
                base_url=args.url,
                project_key=args.project_key,
                project_name=project_name,
                env_file=args.env_file,
            )
            print(f"\nSonarQube ready: {args.url}/dashboard?id={args.project_key}")
            _ = token  # already written to .env
        else:
            if not args.token:
                print("ERROR: --token required unless --init", file=sys.stderr)
                return 1
            result = setup_quality_gate(
                base_url=args.url,
                token=args.token,
                gate_name=gate_name,
                project_key=args.project_key,
            )
            print(
                f"\nQuality Gate '{result['gate_name']}' configured"
                f" (created={result['conditions_created']},"
                f" updated={result['conditions_updated']})"
            )
        return 0

    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        if exc.code == 401:
            print(
                "ERROR: Authentication failed (401) -- check credentials or token",
                file=sys.stderr,
            )
        elif exc.code == 403:
            print("ERROR: Forbidden (403) -- insufficient permissions", file=sys.stderr)
        else:
            print(f"ERROR: HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        if body:
            print(f"       {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"ERROR: Connection failed -- {exc.reason}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

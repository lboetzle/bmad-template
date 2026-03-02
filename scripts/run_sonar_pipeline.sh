#!/usr/bin/env bash
# run_sonar_pipeline.sh -- Local SonarQube pipeline runner
#
# Runs the full quality pipeline and uploads results to a local SonarQube instance.
# Project key and source path are read automatically from sonar-project.properties.
#
# Prerequisites:
#   - Docker running with SonarQube: docker compose -f docker-compose.sonar.yml up -d
#   - SONAR_TOKEN set in .env (written by install.py) or environment
#
# Usage:
#   bash scripts/run_sonar_pipeline.sh
#
# Exit codes:
#   0 -- All steps passed
#   1 -- One or more steps failed

set -e

# ---------------------------------------------------------------------------
# Environment setup
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load .env if present
if [ -f "${PROJECT_ROOT}/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.env"
    set +a
fi

SONAR_HOST_URL="${SONAR_HOST_URL:-http://localhost:9000}"

if [ -z "${SONAR_TOKEN}" ]; then
    echo "ERROR: SONAR_TOKEN is not set. Add it to .env or export it." >&2
    exit 1
fi

# Read project key and source path from sonar-project.properties
PROPS_FILE="${PROJECT_ROOT}/sonar-project.properties"
if [ ! -f "${PROPS_FILE}" ]; then
    echo "ERROR: sonar-project.properties not found at ${PROPS_FILE}" >&2
    exit 1
fi

PROJECT_KEY="$(grep '^sonar.projectKey=' "${PROPS_FILE}" | cut -d= -f2 | tr -d '[:space:]')"
SOURCE_PATH="$(grep '^sonar.sources=' "${PROPS_FILE}" | cut -d= -f2 | tr -d '[:space:]')"

if [ -z "${PROJECT_KEY}" ]; then
    echo "ERROR: sonar.projectKey not found in sonar-project.properties" >&2
    exit 1
fi

if [ -z "${SOURCE_PATH}" ]; then
    SOURCE_PATH="src/${PROJECT_KEY}"
fi

# ---------------------------------------------------------------------------
# Step tracking
# ---------------------------------------------------------------------------

FAILED_STEPS=()

run_step() {
    local step_name="$1"
    shift
    echo ""
    echo ">> ${step_name}"
    if "$@"; then
        echo "  PASS: ${step_name}"
    else
        echo "  FAIL: ${step_name}"
        FAILED_STEPS+=("${step_name}")
    fi
}

set +e

cd "${PROJECT_ROOT}"

# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

echo "======================================================================"
echo " SonarQube Local Pipeline -- ${PROJECT_KEY}"
echo " SonarQube: ${SONAR_HOST_URL}"
echo "======================================================================"

# Step 1: Tests + coverage
run_step "pytest + coverage" \
    uv run pytest "--cov=${SOURCE_PATH}" --cov-report=xml -p no:cacheprovider

# Step 2a: Ruff lint export
run_step "ruff lint export" \
    bash -c 'uv run ruff check src/ --output-format json > ruff-report-raw.json 2>/dev/null'

# Step 2b: Ruff -> SonarQube format
run_step "ruff -> sonar format" \
    uv run python scripts/sonar_export.py ruff ruff-report-raw.json ruff-sonar.json

# Step 3a: Mypy type check export
run_step "mypy type check export" \
    bash -c 'uv run mypy --strict src/ --output json > mypy-report-raw.json 2>&1'

# Step 3b: Mypy -> SonarQube format
run_step "mypy -> sonar format" \
    uv run python scripts/sonar_export.py mypy mypy-report-raw.json mypy-sonar.json

# Step 4: SonarQube scan (Docker-based scanner)
SONAR_VOLUME_PATH="${PROJECT_ROOT//\\//}"

run_step "sonar-scanner upload" \
    env MSYS_NO_PATHCONV=1 docker run --rm --network host \
        -e "SONAR_HOST_URL=${SONAR_HOST_URL}" \
        -e "SONAR_TOKEN=${SONAR_TOKEN}" \
        -v "${SONAR_VOLUME_PATH}:/usr/src" \
        -w /usr/src \
        sonarsource/sonar-scanner-cli \
        -Dproject.settings=/usr/src/sonar-project.properties

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "======================================================================"
echo " Pipeline Summary"
echo "======================================================================"

if [ ${#FAILED_STEPS[@]} -eq 0 ]; then
    echo " All steps PASSED"
    echo " -> Dashboard: ${SONAR_HOST_URL}/dashboard?id=${PROJECT_KEY}"
    exit 0
else
    echo " Failed steps:"
    for step in "${FAILED_STEPS[@]}"; do
        echo "    - ${step}"
    done
    exit 1
fi

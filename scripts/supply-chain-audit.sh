#!/usr/bin/env bash
# vibepost - social media scheduling and posting tool
# Copyright (C) 2026  Travis West
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Audits every dependency (Python and npm) against known-vulnerability
# databases. Exits non-zero if anything is found, so it can gate CI.
#
# Run locally:   ./scripts/supply-chain-audit.sh
# Runs in CI:    .github/workflows/supply-chain.yml (every PR + weekly)

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAILED=0

echo "==> Python dependencies (pip-audit)"
if command -v pip-audit >/dev/null 2>&1; then
  PIP_AUDIT=pip-audit
elif [ -x "$ROOT/backend/.venv/bin/pip-audit" ]; then
  PIP_AUDIT="$ROOT/backend/.venv/bin/pip-audit"
elif command -v uvx >/dev/null 2>&1; then
  PIP_AUDIT="uvx pip-audit"
else
  echo "pip-audit not found. Install with: pip install pip-audit (or use uvx)"
  exit 2
fi
if ! $PIP_AUDIT -r "$ROOT/backend/requirements.txt" --no-deps --disable-pip; then
  FAILED=1
fi

echo
echo "==> npm dependencies (npm audit)"
# The frontend is compiled to a static bundle, so even dev-tool advisories
# matter only insofar as they affect the build or the dev server — but we
# hold everything to the same bar: zero known vulnerabilities.
if ! (cd "$ROOT/frontend" && npm audit); then
  FAILED=1
fi

echo
if [ "$FAILED" -ne 0 ]; then
  echo "✗ Supply-chain audit FAILED — fix or consciously pin before deploying."
  exit 1
fi
echo "✓ Supply chain is boring. Keep it that way."

#!/usr/bin/env bash
# H0A Git-only proof: copy only tracked files plus the current working-tree
# versions of the H0A implementation/test files into a fresh snapshot, then
# run the H0A evidence subset there with the original interpreter.
# No outputs/, .venv, caches, or user files are copied.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../../.." && pwd)"
SNAP="$(mktemp -d "${TMPDIR:-/tmp}/h0a-gitonly.XXXXXX")"
trap 'rm -rf "$SNAP"' EXIT

cd "$REPO"
git ls-files -z | while IFS= read -r -d '' f; do
  mkdir -p "$SNAP/$(dirname "$f")"
  cp -p "$f" "$SNAP/$f"
done

# The reviewed repair diff is uncommitted: overlay its files, plus the new
# H0A test/evidence files that are not tracked yet.
for f in \
  src/hsm_lab/evidence/schemas.py \
  src/hsm_lab/evidence/loader.py \
  src/hsm_lab/evidence/provenance.py \
  src/hsm_lab/evidence/adapter.py \
  src/hsm_lab/evidence/run_adapter.py \
  tests/test_hist_identity_guards.py \
  tests/test_evidence_schemas.py \
  tests/test_evidence_run_adapter.py \
  tests/test_evidence_manifest_verification.py \
  docs/phases/HIST_VNEXT/H0A/PLAN.md \
  docs/phases/HIST_VNEXT/H0A/REPORT.md \
  docs/phases/HIST_VNEXT/H0A/REVIEW.md
do
  if [ -f "$f" ]; then
    mkdir -p "$SNAP/$(dirname "$f")"
    cp -p "$f" "$SNAP/$f"
  fi
done

cd "$SNAP"
# The snapshot is its own clean Git repository: guard tests that compare
# against HEAD must see an unchanged tree, not the parent checkout's diff.
git init -q
git add -A
git -c user.name="H0A snapshot" -c user.email="h0a@example.invalid" \
  commit -q -m "H0A Git-only snapshot"

PYTHONPATH="$SNAP/src" \
PYTHONDONTWRITEBYTECODE=1 \
"$REPO/.venv/bin/python" -m pytest -q -p no:cacheprovider \
  tests/test_hist_identity_guards.py \
  tests/test_evidence_schemas.py \
  tests/test_evidence_run_adapter.py \
  tests/test_evidence_manifest_verification.py

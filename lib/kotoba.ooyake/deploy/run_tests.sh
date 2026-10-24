#!/usr/bin/env bash
# ooyake 公 — run all offline self-tests for the gov-atlas toolchain (ADR-2606021600).
#
# Pure offline verification — no network, no kotoba node, no deploy. Each suite is
# run only if present (robust across merge states). Exits non-zero if any fails.
#
#   bash deploy/run_tests.sh
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTOR="$(cd "$HERE/.." && pwd)"
fail=0
run() {
  local label="$1"; shift
  if [ ! -f "$1" ]; then echo "skip  $label (absent)"; return; fi
  if python3 "$@" >/tmp/ooyake_test.out 2>&1; then
    echo "PASS  $label"
  else
    echo "FAIL  $label"; sed 's/^/        /' /tmp/ooyake_test.out | tail -8; fail=1
  fi
}

echo "ooyake gov-atlas offline test suite"
# real-data gates FIRST: registry integrity (QID-fabrication class + addresses) +
# integrity-guard self-tests + G20 real-data coverage
run "registry integrity"    "$ACTOR/scripts/check_seed_integrity.py" --quiet
run "integrity guard tests" "$ACTOR/cells/reconcile/test_seed_integrity.py"
run "G20 real-data coverage" "$ACTOR/scripts/g20_coverage.py"
run "world country coverage" "$ACTOR/scripts/world_coverage.py"
run "atlas summary"         "$ACTOR/scripts/atlas_summary.py"
run "coverage matrix"       "$ACTOR/scripts/coverage_matrix.py"
run "quality audit"         "$ACTOR/scripts/quality_audit.py"
run "geojson export"        "$ACTOR/scripts/export_geojson.py" --check
run "reconcile cell"        "$ACTOR/cells/reconcile/test_reconcile_cell.py"
run "gov_atlas_client"      "$ACTOR/deploy/test_gov_atlas_client.py"
run "resolve_for_toritsugi" "$ACTOR/deploy/resolve_for_toritsugi.py"
run "consumers_example"     "$ACTOR/deploy/consumers_example.py"
run "validate_atlas"        "$ACTOR/deploy/validate_atlas.py"
# dry-run projections (no token => no writes): assert they parse + count without error
run "ingest_records (dry)"  "$ACTOR/deploy/ingest_records.py"
run "ingest_jp_local (dry)" "$ACTOR/deploy/ingest_jp_local.py"
run "promote_auth (dry)"    "$ACTOR/deploy/promote_authoritative.py"
# cross-actor world-model reconcile (ooyake↔tsumugi) — cell tests + dry report
run "world_model cell"      "$ACTOR/cells/world_model/test_world_model_cell.py"
run "world_model drift-lock" "$ACTOR/cells/world_model/test_consistency.py"
run "world_model coverage"  "$ACTOR/scripts/world_model_coverage.py" --quiet
run "world_model (dry)"     "$ACTOR/scripts/world_model.py"
run "world_model ingest (dry)" "$ACTOR/deploy/ingest_world_model.py"

if [ "$fail" -eq 0 ]; then echo "ALL GREEN"; else echo "SOME FAILED"; fi
exit "$fail"

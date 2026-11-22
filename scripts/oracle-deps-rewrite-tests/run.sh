#!/bin/bash
# run.sh — fixture tests for ../oracle-deps-rewrite.py (Dev review item 3).
# Fails non-zero on the first mismatch. No network; uses tests/fake-kotoba
# as the monorepo (--kotoba-repo accepts a plain dir tree).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../oracle-deps-rewrite.py"
KOTO="$HERE/fake-kotoba"
SHA='ee75001ee44a9b793602d1549e5e977c4562a5fe'
TMP="$(mktemp -d "${TMPDIR:-/tmp}/odr-tests.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
fail() { echo "FAIL: $1"; exit 1; }

run_case() { # <case> [extra args...]
  local case="$1"; shift
  cp "$HERE/cases/$case/deps.edn" "$TMP/$case.edn"
  python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$@" "$TMP/$case.edn" \
    > "$TMP/$case.stdout" 2> "$TMP/$case.stderr"
  echo "$?"
}

expect_ok() { # <case> [extra args...]
  local case="$1"; shift
  local code
  code=$(run_case "$case" "$@")
  [ "$code" = 0 ] || { echo "--- stdout:"; cat "$TMP/$case.stdout"; echo "--- stderr:"; cat "$TMP/$case.stderr"; fail "$case: exit $code, want 0"; }
  diff -u "$HERE/cases/$case/expected.edn" "$TMP/$case.edn" \
    || fail "$case: output differs from expected.edn"
  echo "ok: $case (rewrote, matches expected)"
}

# 1-5, 9: rewrite cases with frozen expected outputs
expect_ok 01-direct
expect_ok 02-bare-sha
expect_ok 03-replace-alias
expect_ok 04-amu-extra
expect_ok 05-existing-override
expect_ok 09-local-root --rewrite-local-roots pprint

# 6: idempotent re-run exits 2 and changes nothing
cp "$HERE/cases/01-direct/expected.edn" "$TMP/06.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/06.edn" \
  > "$TMP/06.stdout" 2>&1
[ "$?" = 2 ] || fail "06-idempotent: exit $?, want 2"
diff -q "$HERE/cases/01-direct/expected.edn" "$TMP/06.edn" > /dev/null \
  || fail "06-idempotent: file changed on re-run"
echo "ok: 06-idempotent (exit 2, unchanged)"

# 7: malformed EDN errors without writing
cp "$HERE/cases/07-malformed/deps.edn" "$TMP/07.edn"
md5_before=$(md5 -q "$TMP/07.edn" 2>/dev/null || md5sum "$TMP/07.edn" | cut -d' ' -f1)
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/07.edn" \
  > "$TMP/07.stdout" 2>&1
code=$?
[ "$code" != 0 ] || fail "07-malformed: exit 0, want non-zero"
md5_after=$(md5 -q "$TMP/07.edn" 2>/dev/null || md5sum "$TMP/07.edn" | cut -d' ' -f1)
[ "$md5_before" = "$md5_after" ] || fail "07-malformed: file was modified"
echo "ok: 07-malformed (exit $code, untouched)"

# 10: unknown artifact (no catalog path) errors loudly without writing
cp "$HERE/cases/10-unknown-artifact/deps.edn" "$TMP/10.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/10.edn" \
  > "$TMP/10.stdout" 2>&1
[ "$?" != 0 ] || fail "10-unknown-artifact: exit 0, want non-zero"
grep -q "no monorepo path" "$TMP/10.stdout" || fail "10-unknown-artifact: no loud error"
diff -q "$HERE/cases/10-unknown-artifact/deps.edn" "$TMP/10.edn" > /dev/null \
  || fail "10-unknown-artifact: file was modified"
echo "ok: 10-unknown-artifact (loud error, untouched)"

# 11-extra-upgrade (extern-sha upgrade applies cleanly)
cp "$HERE/cases/11-extra-upgrade/deps.edn" "$TMP/11.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/11.edn" \
  > /tmp/x11 2>&1
[ "$?" = 0 ] || { cat /tmp/x11; fail "11-extra-upgrade: want exit 0"; }
diff -q "$HERE/cases/11-extra-upgrade/expected.edn" "$TMP/11.edn" > /dev/null \
  || fail "11-extra-upgrade: output differs from expected.edn"
echo "ok: 11-extra-upgrade (extern upgrade applied)"

# 12-extra-drift (extern case changed -> loud error, untouched)
cp "$HERE/cases/12-extra-drift/deps.edn" "$TMP/12.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$HERE/fake-kotoba-drift" "$TMP/12.edn" \
  > "$TMP/12.stdout" 2>&1
[ "$?" != 0 ] || fail "12-extra-drift: exit 0, want non-zero"
grep -q "extern case changed" "$TMP/12.stdout" || fail "12-extra-drift: no loud error"
diff -q "$HERE/cases/12-extra-drift/deps.edn" "$TMP/12.edn" > /dev/null \
  || fail "12-extra-drift: file was modified"
echo "ok: 12-extra-drift (loud error, untouched)"

# 8: --check mode (dirty -> 1, clean -> 0, never writes)
python3 "$SCRIPT" --check "$HERE/cases/02-bare-sha/deps.edn" > /tmp/chk1 2>&1
[ "$?" = 1 ] || fail "08-check dirty: want exit 1"
python3 "$SCRIPT" --check "$HERE/cases/01-direct/expected.edn" > /tmp/chk2 2>&1
[ "$?" = 0 ] || { cat /tmp/chk2; fail "08-check clean: want exit 0"; }
echo "ok: 08-check (dirty 1, clean 0)"

echo "ALL FIXTURE TESTS PASSED"

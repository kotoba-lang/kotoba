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
  > "$TMP/11.stdout" 2>&1
[ "$?" = 0 ] || { cat "$TMP/11.stdout"; fail "11-extra-upgrade: want exit 0"; }
diff -q "$HERE/cases/11-extra-upgrade/expected.edn" "$TMP/11.edn" > /dev/null \
  || fail "11-extra-upgrade: output differs from expected.edn"
echo "ok: 11-extra-upgrade (extern upgrade applied)"

# 12-extra-drift (extern case changed -> loud error, untouched)
cp "$HERE/cases/12-extra-drift/deps.edn" "$TMP/12.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$HERE/fake-kotoba-drift" "$TMP/12.edn" \
  > "$TMP/12.stdout" 2>&1
[ "$?" != 0 ] || fail "12-extra-drift: exit 0, want non-zero"
grep -q "extern osaho pin changed" "$TMP/12.stdout" || fail "12-extra-drift: no loud error"
diff -q "$HERE/cases/12-extra-drift/deps.edn" "$TMP/12.edn" > /dev/null \
  || fail "12-extra-drift: file was modified"
echo "ok: 12-extra-drift (loud error, untouched)"

# 8: --check mode (dirty -> 1, clean -> 0, never writes)
python3 "$SCRIPT" --check "$HERE/cases/02-bare-sha/deps.edn" > "$TMP/chk1" 2>&1
[ "$?" = 1 ] || fail "08-check dirty: want exit 1"
python3 "$SCRIPT" --check "$HERE/cases/01-direct/expected.edn" > "$TMP/chk2" 2>&1
[ "$?" = 0 ] || { cat "$TMP/chk2"; fail "08-check clean: want exit 0"; }
echo "ok: 08-check (dirty 1, clean 0)"

# 13: --check flags a dead URL whose value starts on the next line
python3 "$SCRIPT" --check "$HERE/cases/13-check-multiline/deps.edn" > "$TMP/13.stdout" 2>&1
[ "$?" = 1 ] || fail "13-check-multiline: want exit 1"
grep -q "dead repo URL" "$TMP/13.stdout" || fail "13-check-multiline: no dead-URL report"
echo "ok: 13-check-multiline (exit 1)"

# 14: --check ignores dead URLs that appear only in ;-comments
python3 "$SCRIPT" --check "$HERE/cases/14-check-comment-url/deps.edn" > "$TMP/14.stdout" 2>&1
[ "$?" = 0 ] || { cat "$TMP/14.stdout"; fail "14-check-comment-url: want exit 0"; }
echo "ok: 14-check-comment-url (exit 0)"

# 15: comment-only :deps pins are left byte-identical by default mode
cp "$HERE/cases/15-comment-only-deps/deps.edn" "$TMP/15.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/15.edn" \
  > "$TMP/15.stdout" 2>&1
[ "$?" = 2 ] || { cat "$TMP/15.stdout"; fail "15-comment-only-deps: want exit 2"; }
cmp -s "$HERE/cases/15-comment-only-deps/deps.edn" "$TMP/15.edn" \
  || fail "15-comment-only-deps: file was modified"
echo "ok: 15-comment-only-deps (exit 2, byte-identical)"

# 16: comment-only :override-deps pin for a wanted lib is added as an
# effective entry; ;-comment lines stay byte-identical
cp "$HERE/cases/16-override-comment/deps.edn" "$TMP/16.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/16.edn" \
  > "$TMP/16.stdout" 2>&1
[ "$?" = 0 ] || { cat "$TMP/16.stdout"; fail "16-override-comment: want exit 0"; }
diff -u "$HERE/cases/16-override-comment/expected.edn" "$TMP/16.edn" \
  || fail "16-override-comment: output differs from expected.edn"
grep ';' "$HERE/cases/16-override-comment/deps.edn" > "$TMP/16.want-comments"
grep ';' "$TMP/16.edn" > "$TMP/16.got-comments"
diff -q "$TMP/16.want-comments" "$TMP/16.got-comments" > /dev/null \
  || fail "16-override-comment: ;-comment lines not preserved"
echo "ok: 16-override-comment (rewrote, comments byte-identical)"

# 17: --check flags an effective :git/sha whose :git/url lives only in a ;-comment
python3 "$SCRIPT" --check "$HERE/cases/17-check-comment-sha/deps.edn" > "$TMP/17.stdout" 2>&1
[ "$?" = 1 ] || fail "17-check-comment-sha: want exit 1"
grep -q "bare git sha" "$TMP/17.stdout" || fail "17-check-comment-sha: no bare-sha report"
echo "ok: 17-check-comment-sha (exit 1)"

echo "ALL FIXTURE TESTS PASSED"

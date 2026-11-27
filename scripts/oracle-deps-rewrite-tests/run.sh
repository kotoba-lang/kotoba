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

# 18: EDN commas are whitespace (:deps, / lib,, / :git/url, / :git/sha, / :sha, /
# comma+newline). --check 1 -> rewrite 0 (valid EDN) -> re-run 2 -> --check 0.
# Commas inside strings and ;-comments stay byte-identical.
python3 "$SCRIPT" --check "$HERE/cases/18-comma-gaps/deps.edn" > "$TMP/18c1" 2>&1
[ "$?" = 1 ] || { cat "$TMP/18c1"; fail "18-comma-gaps check dirty: want exit 1"; }
grep -q "dead repo URL" "$TMP/18c1" || fail "18-comma-gaps: no dead-URL report"
grep -q "bare git sha" "$TMP/18c1" || fail "18-comma-gaps: no bare-sha report"
cp "$HERE/cases/18-comma-gaps/deps.edn" "$TMP/18.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/18.edn" \
  > "$TMP/18.stdout" 2>&1
[ "$?" = 0 ] || { cat "$TMP/18.stdout"; fail "18-comma-gaps: want exit 0"; }
diff -u "$HERE/cases/18-comma-gaps/expected.edn" "$TMP/18.edn" \
  || fail "18-comma-gaps: output differs from expected.edn"
grep -F '1.12.0, still one version' "$TMP/18.edn" > /dev/null \
  || fail "18-comma-gaps: comma inside string was changed"
grep -F ':git/url, "https://github.com/kotoba-lang/evil"' "$TMP/18.edn" > /dev/null \
  || fail "18-comma-gaps: ;-comment was changed"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/18.edn" \
  > "$TMP/18b.stdout" 2>&1
[ "$?" = 2 ] || fail "18-comma-gaps re-run: want exit 2"
diff -q "$HERE/cases/18-comma-gaps/expected.edn" "$TMP/18.edn" > /dev/null \
  || fail "18-comma-gaps re-run: file changed"
python3 "$SCRIPT" --check "$TMP/18.edn" > "$TMP/18c2" 2>&1
[ "$?" = 0 ] || { cat "$TMP/18c2"; fail "18-comma-gaps check clean: want exit 0"; }
echo "ok: 18-comma-gaps (check 1, rewrite 0, idempotent 2, check 0)"

# 19: commas at alias level (:aliases, / :override-deps, / lib, / :git/url,).
# Stale override pin is replaced, closure members merged, gaps stay valid EDN.
python3 "$SCRIPT" --check "$HERE/cases/19-comma-alias/deps.edn" > "$TMP/19c1" 2>&1
[ "$?" = 1 ] || { cat "$TMP/19c1"; fail "19-comma-alias check dirty: want exit 1"; }
cp "$HERE/cases/19-comma-alias/deps.edn" "$TMP/19.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/19.edn" \
  > "$TMP/19.stdout" 2>&1
[ "$?" = 0 ] || { cat "$TMP/19.stdout"; fail "19-comma-alias: want exit 0"; }
diff -u "$HERE/cases/19-comma-alias/expected.edn" "$TMP/19.edn" \
  || fail "19-comma-alias: output differs from expected.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/19.edn" \
  > "$TMP/19b.stdout" 2>&1
[ "$?" = 2 ] || fail "19-comma-alias re-run: want exit 2"
python3 "$SCRIPT" --check "$TMP/19.edn" > "$TMP/19c2" 2>&1
[ "$?" = 0 ] || { cat "$TMP/19c2"; fail "19-comma-alias check clean: want exit 0"; }
echo "ok: 19-comma-alias (check 1, rewrite 0, idempotent 2, check 0)"

# 20: Kougi re-review case (:git/url, ; comment + next-line URL + :git/sha,).
# --check 1 -> rewrite 0 -> re-run 2 -> --check 0.
python3 "$SCRIPT" --check "$HERE/cases/20-kougi-comment/deps.edn" > "$TMP/20c1" 2>&1
[ "$?" = 1 ] || { cat "$TMP/20c1"; fail "20-kougi-comment check dirty: want exit 1"; }
grep -q "dead repo URL" "$TMP/20c1" || fail "20-kougi-comment: no dead-URL report"
cp "$HERE/cases/20-kougi-comment/deps.edn" "$TMP/20.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/20.edn" \
  > "$TMP/20.stdout" 2>&1
[ "$?" = 0 ] || { cat "$TMP/20.stdout"; fail "20-kougi-comment: want exit 0"; }
diff -u "$HERE/cases/20-kougi-comment/expected.edn" "$TMP/20.edn" \
  || fail "20-kougi-comment: output differs from expected.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/20.edn" \
  > "$TMP/20b.stdout" 2>&1
[ "$?" = 2 ] || fail "20-kougi-comment re-run: want exit 2"
diff -q "$HERE/cases/20-kougi-comment/expected.edn" "$TMP/20.edn" > /dev/null \
  || fail "20-kougi-comment re-run: file changed"
python3 "$SCRIPT" --check "$TMP/20.edn" > "$TMP/20c2" 2>&1
[ "$?" = 0 ] || { cat "$TMP/20c2"; fail "20-kougi-comment check clean: want exit 0"; }
echo "ok: 20-kougi-comment (check 1, rewrite 0, idempotent 2, check 0)"

# 21: comment+comma gaps at every token position, with byte-preservation of
# rewrite-exempt comments. --check 1 -> rewrite 0 -> re-run 2 -> --check 0.
# Preserved: leading/fake-pin/:deps-gap/text-floor/fake-url comments, the string
# holding ";" and ",", :aliases/:override-deps gap comments, ghost comment.
python3 "$SCRIPT" --check "$HERE/cases/21-gap-preserve/deps.edn" > "$TMP/21c1" 2>&1
[ "$?" = 1 ] || { cat "$TMP/21c1"; fail "21-gap-preserve check dirty: want exit 1"; }
grep -q "dead repo URL" "$TMP/21c1" || fail "21-gap-preserve: no dead-URL report"
cp "$HERE/cases/21-gap-preserve/deps.edn" "$TMP/21.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/21.edn" \
  > "$TMP/21.stdout" 2>&1
[ "$?" = 0 ] || { cat "$TMP/21.stdout"; fail "21-gap-preserve: want exit 0"; }
diff -u "$HERE/cases/21-gap-preserve/expected.edn" "$TMP/21.edn" \
  || fail "21-gap-preserve: output differs from expected.edn"
for line in ';; leading comment stays byte-identical' \
            ' ;; fake pin in comment is ignored: io.github.kotoba-lang/evil {:git/url "https://github.com/kotoba-lang/evil" :git/sha "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}' \
            ' :deps ; comment after :deps' \
            '  ;; comment for the text lib stays.' \
            '  ;; :git/url "https://github.com/kotoba-lang/fake" is a fake.' \
            '  org.clojure/clojure {:mvn/version "1.12.0, still one version; not a comment"}}' \
            ' :aliases ; comment after :aliases' \
            '         :override-deps ; comment after :override-deps' \
            '         {;; fake: io.github.kotoba-lang/ghost {:git/sha "cccccccccccccccccccccccccccccccccccccccc"}'; do
  grep -F -x -- "$line" "$TMP/21.edn" > /dev/null \
    || fail "21-gap-preserve: comment/string line not preserved: $line"
done
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/21.edn" \
  > "$TMP/21b.stdout" 2>&1
[ "$?" = 2 ] || fail "21-gap-preserve re-run: want exit 2"
diff -q "$HERE/cases/21-gap-preserve/expected.edn" "$TMP/21.edn" > /dev/null \
  || fail "21-gap-preserve re-run: file changed"
python3 "$SCRIPT" --check "$TMP/21.edn" > "$TMP/21c2" 2>&1
[ "$?" = 0 ] || { cat "$TMP/21c2"; fail "21-gap-preserve check clean: want exit 0"; }
echo "ok: 21-gap-preserve (check 1, rewrite 0, idempotent 2, check 0, comments kept)"

# 22: Kougi P1 case 1 — `:git/url"..."` with no gap after the keyword.
# --check 1 -> rewrite 0 -> re-run 2 -> --check 0.
python3 "$SCRIPT" --check "$HERE/cases/22-kougi-nospace-url/deps.edn" > "$TMP/22c1" 2>&1
[ "$?" = 1 ] || { cat "$TMP/22c1"; fail "22-kougi-nospace-url check dirty: want exit 1"; }
grep -q "dead repo URL" "$TMP/22c1" || fail "22-kougi-nospace-url: no dead-URL report"
cp "$HERE/cases/22-kougi-nospace-url/deps.edn" "$TMP/22.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/22.edn" \
  > "$TMP/22.stdout" 2>&1
[ "$?" = 0 ] || { cat "$TMP/22.stdout"; fail "22-kougi-nospace-url: want exit 0"; }
diff -u "$HERE/cases/22-kougi-nospace-url/expected.edn" "$TMP/22.edn" \
  || fail "22-kougi-nospace-url: output differs from expected.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/22.edn" \
  > "$TMP/22b.stdout" 2>&1
[ "$?" = 2 ] || fail "22-kougi-nospace-url re-run: want exit 2"
python3 "$SCRIPT" --check "$TMP/22.edn" > "$TMP/22c2" 2>&1
[ "$?" = 0 ] || { cat "$TMP/22c2"; fail "22-kougi-nospace-url check clean: want exit 0"; }
echo "ok: 22-kougi-nospace-url (check 1, rewrite 0, idempotent 2, check 0)"

# 23: Kougi P1 case 2 — `:git/sha"..."` with no gap after the keyword.
# --check 1 -> rewrite 0 -> re-run 2 -> --check 0.
python3 "$SCRIPT" --check "$HERE/cases/23-kougi-nospace-sha/deps.edn" > "$TMP/23c1" 2>&1
[ "$?" = 1 ] || { cat "$TMP/23c1"; fail "23-kougi-nospace-sha check dirty: want exit 1"; }
grep -q "bare git sha" "$TMP/23c1" || fail "23-kougi-nospace-sha: no bare-sha report"
cp "$HERE/cases/23-kougi-nospace-sha/deps.edn" "$TMP/23.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/23.edn" \
  > "$TMP/23.stdout" 2>&1
[ "$?" = 0 ] || { cat "$TMP/23.stdout"; fail "23-kougi-nospace-sha: want exit 0"; }
diff -u "$HERE/cases/23-kougi-nospace-sha/expected.edn" "$TMP/23.edn" \
  || fail "23-kougi-nospace-sha: output differs from expected.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/23.edn" \
  > "$TMP/23b.stdout" 2>&1
[ "$?" = 2 ] || fail "23-kougi-nospace-sha re-run: want exit 2"
python3 "$SCRIPT" --check "$TMP/23.edn" > "$TMP/23c2" 2>&1
[ "$?" = 0 ] || { cat "$TMP/23c2"; fail "23-kougi-nospace-sha check clean: want exit 0"; }
echo "ok: 23-kougi-nospace-sha (check 1, rewrite 0, idempotent 2, check 0)"

# 24: zero-gap adjacent delimiters everywhere (`:deps{`, `{:git/url"...`,
# `:git/sha"..."`, `...}lib`, `:local/root"..."`). --check 1 -> rewrite 0
# (with --rewrite-local-roots pprint) -> re-run 2 -> --check 0.
python3 "$SCRIPT" --check "$HERE/cases/24-adjacent-delims/deps.edn" > "$TMP/24c1" 2>&1
[ "$?" = 1 ] || { cat "$TMP/24c1"; fail "24-adjacent-delims check dirty: want exit 1"; }
grep -q "dead repo URL" "$TMP/24c1" || fail "24-adjacent-delims: no dead-URL report"
cp "$HERE/cases/24-adjacent-delims/deps.edn" "$TMP/24.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" --rewrite-local-roots pprint "$TMP/24.edn" \
  > "$TMP/24.stdout" 2>&1
[ "$?" = 0 ] || { cat "$TMP/24.stdout"; fail "24-adjacent-delims: want exit 0"; }
diff -u "$HERE/cases/24-adjacent-delims/expected.edn" "$TMP/24.edn" \
  || fail "24-adjacent-delims: output differs from expected.edn"
grep -F ':deps/root "lib/kotoba.pprint"' "$TMP/24.edn" > /dev/null \
  || fail "24-adjacent-delims: :local/root pin was not rewritten"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" --rewrite-local-roots pprint "$TMP/24.edn" \
  > "$TMP/24b.stdout" 2>&1
[ "$?" = 2 ] || fail "24-adjacent-delims re-run: want exit 2"
diff -q "$HERE/cases/24-adjacent-delims/expected.edn" "$TMP/24.edn" > /dev/null \
  || fail "24-adjacent-delims re-run: file changed"
python3 "$SCRIPT" --check "$TMP/24.edn" > "$TMP/24c2" 2>&1
[ "$?" = 0 ] || { cat "$TMP/24c2"; fail "24-adjacent-delims check clean: want exit 0"; }
echo "ok: 24-adjacent-delims (check 1, rewrite 0, idempotent 2, check 0)"

# 25: `#_` discards (top-level pin, in-map key/value, chained `#_ #_`,
# set, tagged literal, char literal) are invisible to --check (exit 0) and
# to rewrite (exit 2, byte-identical).
python3 "$SCRIPT" --check "$HERE/cases/25-discard-clean/deps.edn" > "$TMP/25c" 2>&1
[ "$?" = 0 ] || { cat "$TMP/25c"; fail "25-discard-clean check: want exit 0"; }
cp "$HERE/cases/25-discard-clean/deps.edn" "$TMP/25.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/25.edn" \
  > "$TMP/25.stdout" 2>&1
[ "$?" = 2 ] || { cat "$TMP/25.stdout"; fail "25-discard-clean: want exit 2"; }
cmp -s "$HERE/cases/25-discard-clean/deps.edn" "$TMP/25.edn" \
  || fail "25-discard-clean: file was modified"
echo "ok: 25-discard-clean (check 0, rewrite exit 2, byte-identical)"

# 26: unterminated string is malformed: rewrite exits non-zero without
# writing, and --check exits non-zero too.
cp "$HERE/cases/26-malformed-string/deps.edn" "$TMP/26.edn"
md5_before=$(md5 -q "$TMP/26.edn" 2>/dev/null || md5sum "$TMP/26.edn" | cut -d' ' -f1)
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/26.edn" \
  > "$TMP/26.stdout" 2>&1
[ "$?" != 0 ] || fail "26-malformed-string: exit 0, want non-zero"
md5_after=$(md5 -q "$TMP/26.edn" 2>/dev/null || md5sum "$TMP/26.edn" | cut -d' ' -f1)
[ "$md5_before" = "$md5_after" ] || fail "26-malformed-string: file was modified"
python3 "$SCRIPT" --check "$HERE/cases/26-malformed-string/deps.edn" > "$TMP/26c" 2>&1
[ "$?" != 0 ] || fail "26-malformed-string check: exit 0, want non-zero"
echo "ok: 26-malformed-string (rewrite and check both non-zero, untouched)"

# 27: odd map (after a `#_` discard) is malformed: rewrite exits non-zero
# without writing, and --check exits non-zero too.
cp "$HERE/cases/27-malformed-oddmap/deps.edn" "$TMP/27.edn"
md5_before=$(md5 -q "$TMP/27.edn" 2>/dev/null || md5sum "$TMP/27.edn" | cut -d' ' -f1)
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/27.edn" \
  > "$TMP/27.stdout" 2>&1
[ "$?" != 0 ] || fail "27-malformed-oddmap: exit 0, want non-zero"
md5_after=$(md5 -q "$TMP/27.edn" 2>/dev/null || md5sum "$TMP/27.edn" | cut -d' ' -f1)
[ "$md5_before" = "$md5_after" ] || fail "27-malformed-oddmap: file was modified"
python3 "$SCRIPT" --check "$HERE/cases/27-malformed-oddmap/deps.edn" > "$TMP/27c" 2>&1
[ "$?" != 0 ] || fail "27-malformed-oddmap check: exit 0, want non-zero"
echo "ok: 27-malformed-oddmap (rewrite and check both non-zero, untouched)"

# 28: namespaced coordinate map (`#:git{:url ... :sha ...}`) is detected,
# and the whole `#:git{...}` span is replaced (no bare `#:git` left behind).
# --check 1 -> rewrite 0 -> re-run 2 -> --check 0.
python3 "$SCRIPT" --check "$HERE/cases/28-ns-coord/deps.edn" > "$TMP/28c1" 2>&1
[ "$?" = 1 ] || { cat "$TMP/28c1"; fail "28-ns-coord check dirty: want exit 1"; }
grep -q "dead repo URL" "$TMP/28c1" || fail "28-ns-coord: no dead-URL report"
cp "$HERE/cases/28-ns-coord/deps.edn" "$TMP/28.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/28.edn" \
  > "$TMP/28.stdout" 2>&1
[ "$?" = 0 ] || { cat "$TMP/28.stdout"; fail "28-ns-coord: want exit 0"; }
diff -u "$HERE/cases/28-ns-coord/expected.edn" "$TMP/28.edn" \
  || fail "28-ns-coord: output differs from expected.edn"
grep -q "#:git" "$TMP/28.edn" && fail "28-ns-coord: bare #:git left behind"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/28.edn" \
  > "$TMP/28b.stdout" 2>&1
[ "$?" = 2 ] || fail "28-ns-coord re-run: want exit 2"
python3 "$SCRIPT" --check "$TMP/28.edn" > "$TMP/28c2" 2>&1
[ "$?" = 0 ] || { cat "$TMP/28c2"; fail "28-ns-coord check clean: want exit 0"; }
echo "ok: 28-ns-coord (check 1, rewrite 0, idempotent 2, check 0)"

# 29: namespaced dependency maps (`#:io.github.kotoba-lang{...}`) under
# :deps, :override-deps and an alias :extra-deps are all detected and
# rewritten (bare lib keys keep their enclosing namespace).
# --check 1 -> rewrite 0 -> re-run 2 -> --check 0.
python3 "$SCRIPT" --check "$HERE/cases/29-ns-depmaps/deps.edn" > "$TMP/29c1" 2>&1
[ "$?" = 1 ] || { cat "$TMP/29c1"; fail "29-ns-depmaps check dirty: want exit 1"; }
grep -q "dead repo URL" "$TMP/29c1" || fail "29-ns-depmaps: no dead-URL report"
cp "$HERE/cases/29-ns-depmaps/deps.edn" "$TMP/29.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/29.edn" \
  > "$TMP/29.stdout" 2>&1
[ "$?" = 0 ] || { cat "$TMP/29.stdout"; fail "29-ns-depmaps: want exit 0"; }
diff -u "$HERE/cases/29-ns-depmaps/expected.edn" "$TMP/29.edn" \
  || fail "29-ns-depmaps: output differs from expected.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/29.edn" \
  > "$TMP/29b.stdout" 2>&1
[ "$?" = 2 ] || fail "29-ns-depmaps re-run: want exit 2"
python3 "$SCRIPT" --check "$TMP/29.edn" > "$TMP/29c2" 2>&1
[ "$?" = 0 ] || { cat "$TMP/29c2"; fail "29-ns-depmaps check clean: want exit 0"; }
echo "ok: 29-ns-depmaps (check 1, rewrite 0, idempotent 2, check 0)"

# 30: duplicate :git/sha keys in one coordinate map: rewrite exits non-zero
# without writing, and --check exits non-zero too.
cp "$HERE/cases/30-dup-key/deps.edn" "$TMP/30.edn"
md5_before=$(md5 -q "$TMP/30.edn" 2>/dev/null || md5sum "$TMP/30.edn" | cut -d' ' -f1)
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/30.edn" \
  > "$TMP/30.stdout" 2>&1
[ "$?" != 0 ] || fail "30-dup-key: exit 0, want non-zero"
grep -q "duplicate map key" "$TMP/30.stdout" || fail "30-dup-key: no duplicate report"
md5_after=$(md5 -q "$TMP/30.edn" 2>/dev/null || md5sum "$TMP/30.edn" | cut -d' ' -f1)
[ "$md5_before" = "$md5_after" ] || fail "30-dup-key: file was modified"
python3 "$SCRIPT" --check "$HERE/cases/30-dup-key/deps.edn" > "$TMP/30c" 2>&1
[ "$?" != 0 ] || fail "30-dup-key check: exit 0, want non-zero"
echo "ok: 30-dup-key (rewrite and check both non-zero, untouched)"

# 31: duplicate keys via namespace expansion (`#:git{:sha "a" :git/sha "b"}`
# both expand to :git/sha): rejected before any write in both modes.
cp "$HERE/cases/31-dup-expanded/deps.edn" "$TMP/31.edn"
md5_before=$(md5 -q "$TMP/31.edn" 2>/dev/null || md5sum "$TMP/31.edn" | cut -d' ' -f1)
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/31.edn" \
  > "$TMP/31.stdout" 2>&1
[ "$?" != 0 ] || fail "31-dup-expanded: exit 0, want non-zero"
grep -q "duplicate map key" "$TMP/31.stdout" || fail "31-dup-expanded: no duplicate report"
md5_after=$(md5 -q "$TMP/31.edn" 2>/dev/null || md5sum "$TMP/31.edn" | cut -d' ' -f1)
[ "$md5_before" = "$md5_after" ] || fail "31-dup-expanded: file was modified"
python3 "$SCRIPT" --check "$HERE/cases/31-dup-expanded/deps.edn" > "$TMP/31c" 2>&1
[ "$?" != 0 ] || fail "31-dup-expanded check: exit 0, want non-zero"
echo "ok: 31-dup-expanded (rewrite and check both non-zero, untouched)"

# 32: duplicate set elements: rejected before any write in both modes.
cp "$HERE/cases/32-dup-set/deps.edn" "$TMP/32.edn"
md5_before=$(md5 -q "$TMP/32.edn" 2>/dev/null || md5sum "$TMP/32.edn" | cut -d' ' -f1)
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/32.edn" \
  > "$TMP/32.stdout" 2>&1
[ "$?" != 0 ] || fail "32-dup-set: exit 0, want non-zero"
grep -q "duplicate set element" "$TMP/32.stdout" || fail "32-dup-set: no duplicate report"
md5_after=$(md5 -q "$TMP/32.edn" 2>/dev/null || md5sum "$TMP/32.edn" | cut -d' ' -f1)
[ "$md5_before" = "$md5_after" ] || fail "32-dup-set: file was modified"
python3 "$SCRIPT" --check "$HERE/cases/32-dup-set/deps.edn" > "$TMP/32c" 2>&1
[ "$?" != 0 ] || fail "32-dup-set check: exit 0, want non-zero"
echo "ok: 32-dup-set (rewrite and check both non-zero, untouched)"

# 33: `true`, `1` and `1.0` are distinct keys (no false duplicate), so the
# dead pin is rewritten normally. --check 1 -> rewrite 0 -> re-run 2 -> --check 0.
python3 "$SCRIPT" --check "$HERE/cases/33-distinct-keys/deps.edn" > "$TMP/33c1" 2>&1
[ "$?" = 1 ] || { cat "$TMP/33c1"; fail "33-distinct-keys check dirty: want exit 1"; }
cp "$HERE/cases/33-distinct-keys/deps.edn" "$TMP/33.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/33.edn" \
  > "$TMP/33.stdout" 2>&1
[ "$?" = 0 ] || { cat "$TMP/33.stdout"; fail "33-distinct-keys: want exit 0"; }
diff -u "$HERE/cases/33-distinct-keys/expected.edn" "$TMP/33.edn" \
  || fail "33-distinct-keys: output differs from expected.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/33.edn" \
  > "$TMP/33b.stdout" 2>&1
[ "$?" = 2 ] || fail "33-distinct-keys re-run: want exit 2"
python3 "$SCRIPT" --check "$TMP/33.edn" > "$TMP/33c2" 2>&1
[ "$?" = 0 ] || { cat "$TMP/33c2"; fail "33-distinct-keys check clean: want exit 0"; }
echo "ok: 33-distinct-keys (check 1, rewrite 0, idempotent 2, check 0)"

# 34: chained `#_ #_` and `#_ #_ #_` discards (empty :deps map, bb reads it
# as {:paths ["src"] :deps {}}): --check 0 and rewrite exit 2, byte-identical.
python3 "$SCRIPT" --check "$HERE/cases/34-nested-discard/deps.edn" > "$TMP/34c" 2>&1
[ "$?" = 0 ] || { cat "$TMP/34c"; fail "34-nested-discard check: want exit 0"; }
cp "$HERE/cases/34-nested-discard/deps.edn" "$TMP/34.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/34.edn" \
  > "$TMP/34.stdout" 2>&1
[ "$?" = 2 ] || { cat "$TMP/34.stdout"; fail "34-nested-discard: want exit 2"; }
cmp -s "$HERE/cases/34-nested-discard/deps.edn" "$TMP/34.edn" \
  || fail "34-nested-discard: file was modified"
echo "ok: 34-nested-discard (check 0, rewrite exit 2, byte-identical)"

# 35: CRLF input with surrounding comments: --check 1 -> rewrite 0 with
# every out-of-span CRLF byte preserved (no bare LF) -> re-run 2 -> --check 0.
python3 "$SCRIPT" --check "$HERE/cases/35-crlf/deps.edn" > "$TMP/35c1" 2>&1
[ "$?" = 1 ] || { cat "$TMP/35c1"; fail "35-crlf check dirty: want exit 1"; }
grep -q "dead repo URL" "$TMP/35c1" || fail "35-crlf: no dead-URL report"
cp "$HERE/cases/35-crlf/deps.edn" "$TMP/35.edn"
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/35.edn" \
  > "$TMP/35.stdout" 2>&1
[ "$?" = 0 ] || { cat "$TMP/35.stdout"; fail "35-crlf: want exit 0"; }
diff -u "$HERE/cases/35-crlf/expected.edn" "$TMP/35.edn" \
  || fail "35-crlf: output differs from expected.edn"
python3 - "$TMP/35.edn" <<'PYEOF' || fail "35-crlf: CRLF bytes not preserved"
import sys
raw = open(sys.argv[1], 'rb').read()
assert b'\r\n' in raw, "no CRLF left"
for i, line in enumerate(raw.split(b'\n')):
    if i < len(raw.split(b'\n')) - 1 and not line.endswith(b'\r'):
        raise SystemExit("bare LF on line %d: %r" % (i + 1, line))
for want in (b';; leading comment stays\r',
             b'  ;; text pin comment\r',
             b';; trailing comment\r'):
    assert want in raw, "comment lost CRLF: %r" % want
PYEOF
python3 "$SCRIPT" --sha "$SHA" --kotoba-repo "$KOTO" "$TMP/35.edn" \
  > "$TMP/35b.stdout" 2>&1
[ "$?" = 2 ] || fail "35-crlf re-run: want exit 2"
python3 "$SCRIPT" --check "$TMP/35.edn" > "$TMP/35c2" 2>&1
[ "$?" = 0 ] || { cat "$TMP/35c2"; fail "35-crlf check clean: want exit 0"; }
echo "ok: 35-crlf (check 1, rewrite 0, idempotent 2, check 0, CRLF kept)"

# bb oracle: every new valid EDN file reads cleanly under Babashka.
for f in 28-ns-coord/deps.edn 28-ns-coord/expected.edn \
         29-ns-depmaps/deps.edn 29-ns-depmaps/expected.edn \
         33-distinct-keys/deps.edn 33-distinct-keys/expected.edn \
         34-nested-discard/deps.edn 35-crlf/deps.edn 35-crlf/expected.edn; do
  bb -e "(clojure.edn/read-string (slurp \"$HERE/cases/$f\"))" \
    > /dev/null 2>&1 || fail "bb cannot read new valid fixture $f"
done
echo "ok: bb reads all new valid fixtures"

# bb oracle: duplicate keys, duplicate set elements, odd maps and broken
# discards are rejected by Babashka too (exit non-zero, like the script).
for f in 07-malformed/deps.edn 26-malformed-string/deps.edn \
         27-malformed-oddmap/deps.edn 30-dup-key/deps.edn \
         31-dup-expanded/deps.edn 32-dup-set/deps.edn; do
  bb -e "(clojure.edn/read-string (slurp \"$HERE/cases/$f\"))" \
    > /dev/null 2>&1 && fail "bb unexpectedly reads invalid fixture $f"
done
echo "ok: bb rejects all invalid fixtures"

echo "ALL FIXTURE TESTS PASSED"

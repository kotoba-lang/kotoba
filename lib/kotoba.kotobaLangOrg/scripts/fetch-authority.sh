#!/bin/sh
# Copy the language authority files site/generate.cljk reads from the
# kotoba-lang commit pinned in authority.lock into this checkout, at the paths
# the build expects (root ADR-2610100100). They are .gitignore'd: the commit in
# authority.lock is the record, not a copy. KOTOBA_LANG_DIR may name a local
# checkout to read instead of cloning (it is checked out at the pinned commit).
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
REPO=$(sed -n 's/^ *{:repository "\([^"]*\)".*/\1/p' authority.lock)
COMMIT=$(sed -n 's/^ *:commit "\([0-9a-f]\{40\}\)".*/\1/p' authority.lock)
[ -n "$REPO" ] && [ -n "$COMMIT" ] || { echo "fetch-authority: authority.lock has no repository / commit" >&2; exit 65; }
SRC=$(mktemp -d)
trap 'rm -rf "$SRC"' EXIT
if [ -n "${KOTOBA_LANG_DIR:-}" ]; then
  git -C "$KOTOBA_LANG_DIR" archive "$COMMIT" | tar -x -C "$SRC"
else
  git init -q "$SRC/.repo"
  git -C "$SRC/.repo" fetch -q --depth 1 "$REPO" "$COMMIT"
  git -C "$SRC/.repo" archive FETCH_HEAD | tar -x -C "$SRC"
fi
# The kotoba-lang paths the site build reads: whole directories for lang/,
# docs/, security/ and bench/ (site/generate.cljk and site/src read files
# across them), and the four scripts it runs. resources/jp_go_dds comes from
# jp-go-digital-design-system, which site/build.cljk fetches itself into
# .site-deps/. Anything else the build reads fails it, or the byte comparison
# of site/dist against kotoba-lang's own build.
for p in \
  lang docs security bench \
  scripts/benchmark-public-compile.mjs scripts/benchmark-public-domains.mjs \
  scripts/benchmark-public-end-to-end.mjs scripts/project-runtime-comparison.cljk
do
  [ -e "$SRC/$p" ] || { echo "fetch-authority: $p is not in $COMMIT" >&2; exit 66; }
  mkdir -p "$(dirname "$p")"
  rm -rf "$p"
  cp -R "$SRC/$p" "$p"
done
echo "fetch-authority: kotoba-lang $COMMIT"

#!/usr/bin/env bash
set -euo pipefail

generator="$(cd "$(dirname "$0")/.." && pwd)/scripts/project-edn-lexicons.cljk"
fixtures="$(cd "$(dirname "$0")" && pwd)/fixtures"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

# Vector datoms: derive the target leaf from the sole distinct namespaced */id.
mkdir -p "$tmp/vector/lex"
cp "$fixtures/datom-valid.edn" "$tmp/vector/lex/not-the-document-id.edn"
bb "$generator" --repo "$tmp/vector" >/dev/null
test -f "$tmp/vector/lexicons/com/etzhayyim/fixture/example.json" || fail "vector target"
bb "$generator" --repo "$tmp/vector" --check >/dev/null || fail "vector check"

# Existing map lookup and source/output precedence remain unchanged.
mkdir -p "$tmp/map/data/lex" "$tmp/map/lex" "$tmp/map/contracts/lexicons" "$tmp/map/wire/lexicons"
printf '{:id "com.etzhayyim.fixture.data" :lexicon 1}\n' > "$tmp/map/data/lex/data.edn"
printf '{:id "com.etzhayyim.fixture.lex" :lexicon 1}\n' > "$tmp/map/lex/lex.edn"
printf '{:id "com.etzhayyim.fixture.contract" :lexicon 1}\n' > "$tmp/map/contracts/lexicons/contract.edn"
bb "$generator" --repo "$tmp/map" >/dev/null
test -f "$tmp/map/wire/lexicons/data.json" || fail "map target/output precedence"
test ! -e "$tmp/map/wire/lexicons/lex.json" || fail "lex improperly outranked data/lex"
test ! -e "$tmp/map/wire/contracts/lexicons/contract.json" || fail "contract improperly outranked data/lex"
bb "$generator" --repo "$tmp/map" --check >/dev/null || fail "map check"

# schema/lex is a legitimate fallback boundary, but never outranks established
# canonical source locations. With no wire directory it uses the NSID path.
mkdir -p "$tmp/schema-only/schema/lex"
printf '{:id "com.etzhayyim.fixture.schema" :lexicon 1}\n' > "$tmp/schema-only/schema/lex/schema.edn"
bb "$generator" --repo "$tmp/schema-only" >/dev/null
test -f "$tmp/schema-only/lexicons/com/etzhayyim/fixture/schema.json" || fail "schema/lex target"
bb "$generator" --repo "$tmp/schema-only" --check >/dev/null || fail "schema/lex check"

mkdir -p "$tmp/schema-precedence/contracts/lexicons" "$tmp/schema-precedence/schema/lex"
printf '{:id "com.etzhayyim.fixture.contract-first" :lexicon 1}\n' > "$tmp/schema-precedence/contracts/lexicons/contract.edn"
printf '{:id "com.etzhayyim.fixture.schema-second" :lexicon 1}\n' > "$tmp/schema-precedence/schema/lex/schema.edn"
bb "$generator" --repo "$tmp/schema-precedence" >/dev/null
test -f "$tmp/schema-precedence/wire/contracts/lexicons/contract-first.json" || fail "contract precedence over schema/lex"
test ! -e "$tmp/schema-precedence/lexicons/com/etzhayyim/fixture/schema-second.json" || fail "schema/lex improperly outranked contracts"

# A .wire.edn source outranks ordinary data/lex EDN.
printf '{"id" "com.etzhayyim.fixture.wire" "lexicon" 1}\n' > "$tmp/map/data/lex/wire.wire.edn"
bb "$generator" --repo "$tmp/map" >/dev/null
test -f "$tmp/map/wire/lexicons/wire.json" || fail "wire source precedence"

# Ambiguous and missing IDs fail before writing an output.
for case_name in ambiguous missing-id; do
  mkdir -p "$tmp/$case_name/lex"
  cp "$fixtures/datom-$case_name.edn" "$tmp/$case_name/lex/input.edn"
  if bb "$generator" --repo "$tmp/$case_name" >"$tmp/$case_name.out" 2>"$tmp/$case_name.err"; then
    fail "$case_name unexpectedly succeeded"
  fi
done
grep -q 'ambiguous namespaced \*/id string values' "$tmp/ambiguous.err" || fail "ambiguity diagnostic"
grep -q 'no namespaced \*/id string value' "$tmp/missing-id.err" || fail "missing-ID diagnostic"

echo "project-edn-lexicons tests passed"

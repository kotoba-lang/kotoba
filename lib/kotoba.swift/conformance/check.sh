#!/usr/bin/env bash
# ISO 20022 XSD conformance check for kotoba.swift and kotoba.kotobaIso20022
# (AWAI-3153, ADR 0042 level L1).
#
# Usage, from the repository root:
#   lib/kotoba.swift/conformance/check.sh [OUTPUT_DIR]
#
# Steps:
#   1. Download the XSDs pinned in xsd-pins.edn and stop if a digest differs.
#   2. Build sample documents with kotoba.swift (kbb, SCI backend) and check
#      that each parses back to the same tree.
#   3. Run the kotoba.kotobaIso20022 pytest suite with dump_plugin.py, which
#      records every XML document the codec builds.
#   4. Validate all of them with xmllint against the pinned XSDs.
#
# This is a local evidence run, not a CI gate. It needs network access for
# step 1, and kbb, python3 with pytest, xmllint, curl and shasum on PATH.
# The XSD files are not stored in the repository.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
out="${1:-$repo/.agent-output/iso20022-conformance}"
mkdir -p "$out/xsd" "$out/xml"
# Absolute, because kbb runs from a temporary directory below.
out="$(cd "$out" && pwd)"

echo "# 1. pinned XSDs"
grep -o '{:message "[^"]*" :url "[^"]*" :sha256 "[^"]*"}' "$here/xsd-pins.edn" |
  sed 's/{:message "\([^"]*\)" :url "\([^"]*\)" :sha256 "\([^"]*\)"}/\1 \2 \3/' |
  while read -r message url sha; do
    curl -fsS -o "$out/xsd/$message.xsd" "$url"
    got="$(shasum -a 256 "$out/xsd/$message.xsd" | cut -c1-64)"
    if [ "$got" != "$sha" ]; then
      echo "digest mismatch for $message: expected $sha, got $got" >&2
      exit 1
    fi
    echo "$message $sha ok"
  done

echo "# 2. kotoba.swift samples"
# kbb resolves the repository's deps.edn whenever it starts anywhere inside
# the repository, and that file names libraries a sparse checkout may lack.
# So it runs from an empty temporary directory outside the repository, with
# an explicit classpath.
kbb_dir="$(mktemp -d)"
trap 'rm -rf "$kbb_dir"' EXIT
echo '{:paths []}' > "$kbb_dir/deps.edn"
cp "$here/samples.cljk" "$kbb_dir/samples.cljk"
cp_dirs=""
for lib in swift securities xml html css text test spec error io coll; do
  cp_dirs="$cp_dirs$repo/lib/kotoba.$lib/src:"
done
(cd "$kbb_dir" && kbb --backend sci --classpath "${cp_dirs%:}" samples.cljk "$out/xml")

echo "# 3. kotoba.kotobaIso20022 documents built by its test suite"
(cd "$repo/lib/kotoba.kotobaIso20022" &&
  ISO_DUMP_DIR="$out/xml" PYTHONPATH=".:$here" \
    pytest -q -p dump_plugin -p no:cacheprovider tests | tail -1)

echo "# 4. XSD validation"
python3 -I "$here/summarize.py" "$out/xml" "$out/xsd" "$out/summary.json"
echo "summary: $out/summary.json"

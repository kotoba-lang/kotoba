#!/bin/sh
# Source-identity preflight only; no compiler or hosted language runtime.
set -eu
fail() { printf 'SOURCE_PIN_AUDIT_REFUSED: %s\n' "$*" >&2; exit 1; }
root= manifest=
while [ "$#" -gt 0 ]; do
 case "$1" in
  --root) [ "$#" -ge 2 ] || fail 'missing root'; root=$2; shift 2;;
  --manifest) [ "$#" -ge 2 ] || fail 'missing manifest'; manifest=$2; shift 2;;
  *) fail 'unknown argument';;
 esac
done
[ -n "$root" ] && [ -d "$root" ] || fail 'root is not a directory'
root=$(CDPATH= cd -- "$root" && pwd -P) || fail 'cannot resolve root'
[ -n "$manifest" ] || manifest="$root/local-changes.json"
[ -f "$manifest" ] && [ ! -L "$manifest" ] || fail 'manifest is not a regular unlinked file'
command -v jq >/dev/null 2>&1 || fail 'jq unavailable'
if command -v sha256sum >/dev/null 2>&1; then hash=sha256sum
elif command -v shasum >/dev/null 2>&1; then hash=shasum
else fail 'SHA-256 tool unavailable'; fi
# Constrain paths to a portable alphabet; reject every symlink component, even
# if it would resolve inside the tree. This is stricter than the old auditor.
jq -e '
  .schema == "kotoba.library-local-changes.v1" and
  (.files | type == "object") and (.added | type == "object") and
  ([.files,.added] | map(to_entries[]) | all(.[];
     (.key | type == "string" and test("^[A-Za-z0-9_+./-]+$") and
      (startswith("/") | not) and (endswith("/") | not) and
      (split("/") | all(. != "" and . != "." and . != ".."))) and
     (.value | type == "object" and (.sha256 | type == "string" and test("^[0-9a-f]{64}$"))))) and
  ([.files,.added] | map(to_entries[]) | group_by(.key) | all((map(.value.sha256) | unique | length) == 1))
' "$manifest" >/dev/null || fail 'invalid schema, entry, path, hash or conflicting pin'
# jq validation above guarantees that tabs/newlines cannot occur in paths.
entries=$(jq -er '[.files,.added] | map(to_entries[]) | unique_by(.key) | map([.key,.value.sha256] | @tsv) | join("\n")' "$manifest") || fail 'cannot enumerate entries'
printf '%s\n' "$entries" |
while IFS="$(printf '\t')" read -r name expected; do
 [ -n "$name" ] || continue
 path=$root
 old_ifs=$IFS; IFS=/; set -f; set -- $name; IFS=$old_ifs
 for part do
  path=$path/$part
  [ ! -L "$path" ] || fail "linked source: $name"
 done
 [ -f "$path" ] || fail "missing source: $name"
 if [ "$hash" = sha256sum ]; then actual=$(sha256sum "$path")
 else actual=$(shasum -a 256 "$path"); fi
 actual=${actual%% *}
 [ "$actual" = "$expected" ] || fail "stale pin: $name"
done
jq -cn --slurpfile m "$manifest" '$m[0] | {status:"PASS_SOURCE_PIN_AUDIT", files:(.files|length), added:(.added|length), uniquePaths:([.files,.added] | map(keys[]) | unique | length)}'

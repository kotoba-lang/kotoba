#!/usr/bin/env bash
set -euo pipefail
runtime="${RUNNER_TEMP:?}/kotoba-clj-ci-runtime"
mkdir -p "$runtime"
amu_revision=$(node -e 'const fs=require("fs");const text=fs.readFileSync("deps.edn","utf8");const match=text.match(/io.github.kotoba-lang\/amu\s*\{[^}]*:git\/sha\s*"([0-9a-f]{40})"/);if(!match)throw Error("immutable Amu pin missing");process.stdout.write(match[1]);')
for entry in "amu $amu_revision" 'org-babashka-nbb 829f0ba11016e925001d80e51f12848c4ad58112'; do
  read -r repo revision <<< "$entry"
  git init -q "$runtime/$repo"
  git -C "$runtime/$repo" fetch --depth 1 "https://github.com/kotoba-lang/$repo.git" "$revision"
  git -C "$runtime/$repo" checkout --detach -q FETCH_HEAD
done
# The pinned old Amu launcher owns and loads this exact npm runtime. Missing
# dependencies used to make every --jvm-free compiler invocation refuse.
npm ci --prefix "$runtime/amu" --ignore-scripts --no-audit --no-fund
cat > "$runtime/nbb" <<'NBB'
#!/bin/sh
set -eu
runtime="${RUNNER_TEMP:?}/kotoba-clj-ci-runtime"
exec node "$runtime/org-babashka-nbb/cli.js" "$@"
NBB
chmod +x "$runtime/nbb"
{
  echo "AMU_HOME=$runtime/amu"
  echo "KBB_ENGINE=$runtime/org-babashka-nbb/cli.js"
  echo "NBB=$runtime/nbb"
} >> "${GITHUB_ENV:?}"

# Subprocess tests probe nbb and kbb by name; expose the exact prepared hosts.
printf "%s\n%s\n" "$runtime" "$PWD/bin" >> "${GITHUB_PATH:?}"

#!/usr/bin/env bash
# Build public/js/app.js with shadow-cljs, from .cljk sources.
#
# shadow-cljs (and the ClojureScript compiler under it) reads .cljs/.cljc and
# not .cljk, and amu does not yet compile browser code that touches the DOM.
# So this copies every source directory on the deps.edn classpath into
# .build/src with .cljk renamed to .cljc — the content is unchanged, reader
# conditionals and all — and runs shadow-cljs from the jars tools.deps already
# resolved. No npm package is executed; no network beyond tools.deps' own
# git/maven resolution.
#
#   script/build_js.sh            # release build into public/js/app.js
set -euo pipefail
cd "$(dirname "$0")/.."

CP=$(clojure -Spath)
rm -rf .build && mkdir -p .build/src
IFS=: read -ra entries <<< "$CP"
jars=()
for e in "${entries[@]}"; do
  if [ -d "$e" ]; then
    (cd "$e" && find . -type f \( -name '*.cljk' -o -name '*.cljc' -o -name '*.cljs' -o -name '*.js' \) -print0) |
      while IFS= read -r -d '' f; do
        dst=".build/src/${f#./}"
        dst="${dst%.cljk}"; [ "$dst" != ".build/src/${f#./}" ] && dst="$dst.cljc"
        mkdir -p "$(dirname "$dst")"
        # Two classpath entries providing one path: identical copies are
        # fine, different ones are a build error — which one won used to
        # depend on find order.
        if [ -e "$dst" ]; then
          if ! cmp -s "$e/$f" "$dst"; then
            echo "build_js: conflicting $dst from $e" >&2; exit 1
          fi
          continue
        fi
        cp "$e/$f" "$dst"
      done
  elif [[ "$e" == *.jar ]]; then
    jars+=("$e")
  fi
done

cat > .build/shadow-cljs.edn <<'EDN'
{:source-paths ["src"]
 :builds
 {:client {:target :esm
           :output-dir "../public/js"
           :modules {:app {:init-fn torihiki-terminal.client/start}}}}}
EDN

JCP=$(IFS=:; echo "src:${jars[*]}")
cd .build
java -cp "$JCP" clojure.main -m shadow.cljs.devtools.cli release client

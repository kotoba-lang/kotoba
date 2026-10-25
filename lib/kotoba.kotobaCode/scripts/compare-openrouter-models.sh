#!/usr/bin/env bash
# Leftover OpenRouter harness. Not operator start. :run is gone.
# Leftover library invocation is kbb -M -m kotoba-code.main.
set -euo pipefail

export OR_KEY="${OR_KEY:-${OPENROUTER_API_KEY:-}}"

if [[ -z "$OR_KEY" ]]; then
  echo "OR_KEY or OPENROUTER_API_KEY is required for OpenRouter chat completions." >&2
  exit 2
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${KC_COMPARE_OUT:-$ROOT/.compare-openrouter}"
TASK="${KC_COMPARE_TASK:-Design and implement a small EDN-backed durable agent loop model. Make the failing tests pass with minimal, idiomatic Clojure.}"
ROUNDS="${KC_GATE_ROUNDS:-2}"
RLIM="${KC_RECURSION_LIMIT:-18}"
MAX_TOKENS="${KC_MAX_TOKENS:-12000}"

MODELS=(
  "z-ai/glm-5.2"
  "tencent/hy3-preview"
  "moonshotai/kimi-k2.7-code"
  "qwen/qwen3.7-max"
)

rm -rf "$OUT"
mkdir -p "$OUT"

make_fixture() {
  local dir="$1"
  mkdir -p "$dir/src/durable" "$dir/test/durable"
  cat > "$dir/deps.edn" <<'EOF'
{:paths ["src"]
 :aliases
 {:test {:extra-paths ["test"]
         :extra-deps {io.github.cognitect-labs/test-runner
                      {:git/tag "v0.5.1" :git/sha "dfb30dd"}}
         :exec-fn cognitect.test-runner.api/test}}}
EOF
  cat > "$dir/src/durable/loop.clj" <<'EOF'
(ns durable.loop)

(defn new-loop [id]
  {:agent.loop/id id
   :agent.loop/status :active})

(defn next-tick [loop-state]
  {:agent.tick/loop (:agent.loop/id loop-state)
   :agent.tick/seq 0})

(defn acquire-lease [loop-state owner now-ms ttl-ms]
  (assoc loop-state
         :agent.lease/owner owner
         :agent.lease/expires-at (+ now-ms ttl-ms)))

(defn continue? [loop-state]
  (= :active (:agent.loop/status loop-state)))
EOF
  cat > "$dir/test/durable/loop_test.clj" <<'EOF'
(ns durable.loop-test
  (:require [clojure.test :refer [deftest is testing]]
            [durable.loop :as loop]))

(deftest loop-has-stable-edn-shape
  (is (= {:agent.loop/id "loop-1"
          :agent.loop/status :active
          :agent.loop/tick-seq 0
          :agent.loop/budget {:tokens 1000 :tool-calls 8}}
         (loop/new-loop "loop-1" {:tokens 1000 :tool-calls 8}))))

(deftest tick-sequence-is-monotonic
  (let [l0 (loop/new-loop "loop-1" {:tokens 1000 :tool-calls 8})
        t1 (loop/next-tick l0)
        l1 (loop/apply-tick l0 t1 {:tokens 125 :tool-calls 1})
        t2 (loop/next-tick l1)]
    (is (= 1 (:agent.tick/seq t1)))
    (is (= 2 (:agent.tick/seq t2)))
    (is (= {:tokens 875 :tool-calls 7} (:agent.loop/budget l1)))))

(deftest lease-respects-expiry
  (let [l0 (loop/new-loop "loop-1" {:tokens 1000 :tool-calls 8})
        l1 (loop/acquire-lease l0 "worker-a" 1000 5000)]
    (is (= "worker-a" (:agent.lease/owner l1)))
    (is (loop/lease-valid? l1 5999))
    (is (not (loop/lease-valid? l1 6000)))))

(deftest governor-decides-from-status-and-budget
  (is (= :continue (loop/governor-decision (loop/new-loop "loop-1" {:tokens 10 :tool-calls 1}))))
  (is (= :hold (loop/governor-decision (loop/new-loop "loop-1" {:tokens 0 :tool-calls 1}))))
  (is (= :stop (loop/governor-decision (assoc (loop/new-loop "loop-1" {:tokens 10 :tool-calls 1})
                                              :agent.loop/status :stopped)))))
EOF
  (cd "$dir" &&
    git init -q &&
    git add . &&
    git -c user.name=kotoba-code-compare \
        -c user.email=kotoba-code-compare@example.invalid \
        commit -q -m fixture)
}

printf "model,status,seconds,rounds,summary_dir\n" > "$OUT/results.csv"

for model in "${MODELS[@]}"; do
  slug="$(echo "$model" | tr '/:' '__')"
  work="$OUT/$slug/work"
  mkdir -p "$(dirname "$work")"
  make_fixture "$work"
  log="$OUT/$slug/kotoba-code.log"
  start="$(date +%s)"
  set +e
  (
    cd "$ROOT"
    KC_GATE_ROUNDS="$ROUNDS" \
    KC_RECURSION_LIMIT="$RLIM" \
    KC_MAX_TOKENS="$MAX_TOKENS" \
    KC_SESSION="compare-$slug" \
    # leftover JVM library (not operator start; :run is gone)
    kbb -M -m kotoba-code.main "$TASK" "$work" "$model"
  ) > "$log" 2>&1
  code="$?"
  set -e
  end="$(date +%s)"
  seconds="$((end - start))"
  rounds_seen="$(grep -Eo '\[[0-9]+/[0-9]+ rounds\]' "$log" | tail -1 | tr -dc '0-9/' || true)"
  git -C "$work" diff > "$OUT/$slug/diff.patch"
  (cd "$work" && kbb -X:test) > "$OUT/$slug/final-test.log" 2>&1 || true
  status="fail"
  if [[ "$code" == "0" ]] && grep -q "0 failures, 0 errors" "$OUT/$slug/final-test.log"; then
    status="pass"
  fi
  printf "%s,%s,%s,%s,%s\n" "$model" "$status" "$seconds" "${rounds_seen:-}" "$OUT/$slug" >> "$OUT/results.csv"
done

cat "$OUT/results.csv"
echo
echo "Artifacts: $OUT"

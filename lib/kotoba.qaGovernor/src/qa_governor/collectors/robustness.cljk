(ns qa-governor.collectors.robustness
  "kotoba-lang/qa-governor — deterministic (non-LLM) robustness check
  (ADR-2607031100): does the test suite exercise error paths and have
  tests explicitly named around guards/boundaries/exploits? Pure text
  analysis over test source; the host adapter supplies the concatenated
  test-source string.

  Error paths are recognized in two idioms, since both are legitimate
  Clojure style and a codebase may use either (or both): `(is (thrown?
  ...))` (exceptions), and structured Result-type assertions like `:ok?
  false` / `:problem` / `:error` in an `is` form (return-value-based error
  handling, common in this org's kotoba/qa-governor code — see
  kotoba.runtime's `{:kotoba.wasm/ok? false ...}` shape). Counting only
  `thrown?` under-counts robustness for repos that use the latter idiom.

  Limitation (honest): a naive proxy — counting patterns and keyword
  matches in `deftest` names doesn't verify the tests are meaningful, only
  that the *shape* of edge-case testing exists.")

(defn count-error-path-assertions
  "test-source中の、例外ベース(`(is (thrown? ...`)と構造化Result型ベース
   (`ok? false`や`:problem`/`ns/problem`キーワード——名前空間付き
   キーワードも拾う）の両方のerror-path痕跡を数える。厳密に`is`フォームの
   境界にスコープしようとすると入れ子の括弧で壊れるため、test-source全体
   からのキーワード出現数で近似する（テストファイル内でこれらのキーワードが
   出てくるのはほぼ常にアサーションの一部、という前提の簡易ヒューリスティック）。"
  [test-source]
  (+ (count (re-seq #"\(is\s+\(thrown\?" test-source))
     (count (re-seq #"ok\?\s+false" test-source))
     (count (re-seq #"[:/]problem\b" test-source))))

(def ^:private guard-keyword-pattern
  #"(?i)deftest[^\n]*(guard|mash|boundary|edge|invalid|exploit|once)[^\n]*")

(defn count-guard-tests
  "deftest名にguard/mash/boundary/edge/invalid/exploit/onceのいずれかを
   含むテストの数（対マッシュガードや境界値ガードのような、悪用/異常系を
   狙い撃ちしたテストが存在するかの目印）。"
  [test-source]
  (count (re-seq guard-keyword-pattern test-source)))

(defn robustness-entry
  [{:keys [test-source]}]
  (let [error-paths (count-error-path-assertions test-source)
        guard-tests (count-guard-tests test-source)
        score (min 100 (+ (* 20 (min error-paths 3))
                           (* 20 (min guard-tests 2))))]
    {:category :robustness
     :score score
     :evidence (str error-paths " thrown? assertion(s), " guard-tests
                     " guard/boundary-named deftest(s) found in test source")}))

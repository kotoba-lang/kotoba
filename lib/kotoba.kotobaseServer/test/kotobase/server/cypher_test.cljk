(ns kotobase.server.cypher-test
  "この ns の docstring は「every unsupported form is rejected loudly ...
  never silently misread」と約束している。それを実際に検査するテストが無かった
  ため、openCypher TCK の 1,644 クエリを流したときに **2 件の silent misread**
  が見つかった(2026-08-04)。ここはその再発防止。

  silent misread とは「エラーにならず、違う質問の答えを返す」こと。
  拒否されるのは正しい挙動で、テストしたいのは『黙って通ってしまわないこと』。"
  (:require #?(:clj  [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing] :include-macros true])
            [kotoba.lang.text :as str]
            [kotobase.server.cypher :as cy]))

(defn- parse-or-reason
  "パースできたら {:parsed ...}、subset 外なら {:rejected <理由>}。"
  [q]
  (try {:parsed (cy/parse q)}
       (catch #?(:clj Exception :cljs :default) e
         {:rejected (-> #?(:clj (.getMessage e) :cljs (.-message e))
                        (str/split #" \(near:") first)})))

(defn- rejected? [q] (contains? (parse-or-reason q) :rejected))
(defn- parsed [q] (:parsed (parse-or-reason q)))

;; ---------------------------------------------------------------- 回帰: silent misread

(deftest variable-length-relationship-is-not-silently-a-single-hop
  ;; 2026-08-13: 可変長パスは **実装された**。この deftest が守る不変条件は
  ;; 「拒否すること」ではなく元から「1 ホップとして黙って受理しないこと」なので、
  ;; 主張を「別の compiled 形になる」に置き換える。拒否のままにすると、実装済みの
  ;; 機能を検査しない死んだテストになる。
  (testing "`-[:r*]->` は 1 ホップの `-[:r]->` と同じ compiled 形にならない"
    ;; 実測(2026-08-04 修正前): tokenizer が `*` を捨て、[:r*] と [:r] が同じ
    ;; トークン列になり、「1 ホップだけの答え」をエラー無しで返していた。
    (let [one-hop (parsed "MATCH (a {x: 1})-[:r]->(b {y: 2}) RETURN b")
          star    (parsed "MATCH (a {x: 1})-[:r*]->(b {y: 2}) RETURN b")
          ranged  (parsed "MATCH (a {x: 1})-[:r*1..3]->(b {y: 2}) RETURN b")]
      (is (some? one-hop))
      (is (empty? (:paths one-hop)) "1 ホップは BGP のまま(engine push-down を失わない)")
      (is (not= one-hop star))
      (is (= [{:min 1 :max nil}] (mapv #(select-keys % [:min :max]) (:paths star))))
      (is (= [{:min 1 :max 3}] (mapv #(select-keys % [:min :max]) (:paths ranged))))))
  (testing "境界の形も取り違えない"
    (is (= [{:min 0 :max nil}]
           (mapv #(select-keys % [:min :max])
                 (:paths (parsed "MATCH (a {x: 1})-[:r*0..]->(b {y: 2}) RETURN b")))))
    (is (= [{:min 2 :max 2}]
           (mapv #(select-keys % [:min :max])
                 (:paths (parsed "MATCH (a {x: 1})-[:r*2]->(b {y: 2}) RETURN b")))))))

(deftest regex-match-is-not-silently-equality
  (testing "`=~` は正規表現マッチ。`=` として受理してはいけない"
    ;; 実測(修正前): `~` が捨てられ `WHERE a.n = \"foo\"` になっていた。
    ;; 部分一致を求めた呼び出しが完全一致の結果を受け取る = 静かに誤った答え。
    (is (rejected? "MATCH (a {x: 1}) WHERE a.n =~ \"foo\" RETURN a"))
    (testing "等値比較そのものは従来どおり通る"
      (is (some? (parsed "MATCH (a {x: 1}) WHERE a.n = \"foo\" RETURN a"))))))

(deftest unknown-characters-are-rejected-not-dropped
  (testing "subset の語彙に無い文字は、捨てずに loud reject する"
    ;; 個別の文字を列挙して塞ぐのではなく、tokenizer が catch-all で拾って
    ;; 落とす構造になっていること自体を検査する。
    (doseq [q ["MATCH (a {x: 1}) RETURN a + 1"
               "MATCH (a {x: 1}) WHERE a.n % 2 = 0 RETURN a"
               "MATCH (a {x: 1})-[:r|s]->(b {y: 2}) RETURN b"
               "MATCH (a {x: 1}) RETURN a$"
               "MATCH (a {x: 1}) RETURN a!"]]
      (is (rejected? q) (str "黙って通ってはいけない: " q)))))

(deftest trailing-semicolon-is-accepted
  (testing "末尾のセミコロンは Cypher の慣用で、意味を変えないので許す"
    ;; unknown-character 拒否を入れたことで巻き込み事故にならないことの確認。
    (is (= (parsed "MATCH (a {sp/name: \"x\"}) RETURN a")
           (parsed "MATCH (a {sp/name: \"x\"}) RETURN a;")))))

;; ---------------------------------------------------------------- subset の正の面

(deftest documented-subset-parses
  (testing "docstring が supported と書いている形は実際に通る"
    (is (= {:find '[?a] :where [['?a ":sp/name" "x"]]}
           (parsed "MATCH (a {sp/name: \"x\"}) RETURN a")))
    (is (= {:find '[?a ?b] :where [['?a ":sp/knows" '?b]]}
           (parsed "MATCH (a)-[:sp/knows]->(b) RETURN a, b")))
    (is (= 5 (:limit (parsed "MATCH (a {x: 1}) RETURN a LIMIT 5"))))))

(deftest documented-exclusions-are-loud
  (testing "docstring が「rejected」と書いている形は、実際にエラーになる"
    ;; 2026-08-13: ラベルと右→左は実装したのでこの一覧から外した。両方が
    ;; 「受理され、かつ正しく実行される」ことは cypher-ldbc-test が実測する。
    (doseq [q ["MATCH (n) RETURN n"                                    ; 暗黙の全走査はしない
               "OPTIONAL MATCH (a {x: 1}) RETURN a"                    ; MATCH で始まらない
               "MATCH (a {x: 1})-[:r]->(b) WITH b RETURN b"            ; WITH 後の MATCH が無い
               "MATCH (a {x: 1}) RETURN upper(a.x)"                    ; whitelist 外の関数
               "RETURN 1"]]
      (is (rejected? q) (str "loud reject されるべき: " q))))
  (testing "実装した形は受理される(過剰拒否になっていない)"
    (doseq [q ["MATCH (n:Person {x: 1}) RETURN n"
               "MATCH (a {x: 1})<-[:r]-(b {y: 2}) RETURN b"
               "MATCH (:Person {x: 1})-[:r]->(b) RETURN b"
               "MATCH (a {x: 1}) OPTIONAL MATCH (a)-[:r]->(b) RETURN a, b"
               "MATCH (a {x: 1}) OPTIONAL MATCH (a)-[:r*1..3]-(b) RETURN a, b"
               "MATCH (a {x: 1}) RETURN coalesce(a.x, a.y)"]]
      (is (some? (parsed q)) (str "受理されるべき: " q)))))

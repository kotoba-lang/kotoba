(ns qa-governor.rubric
  "kotoba-lang/qa-governor — 「Nintendoクオリティ」を項目化した既定QAルーブリック
  (ADR-2607031100)。カテゴリ×重みの加重平均で0-100の総合スコアを出す。

  ドメイン非依存の既定カテゴリのみを定義する。consumer（ghosthacker-flow等）
  固有の観点（例: game-feel）は `extend-rubric` で追加するデータとして扱い、
  このnamespace自体はゲーム/リポジトリ固有の知識を持たない。")

(def default-rubric
  "既定カテゴリ。すべてのweightの合計が1である必要は無い——weighted-scoreが
  正規化する。"
  {:stability     {:weight 0.25 :label "Stability (crash/hang-free)"}
   :correctness   {:weight 0.25 :label "Correctness (test/lint green)"}
   :robustness    {:weight 0.20 :label "Robustness (exploit-resistance)"}
   :documentation {:weight 0.15 :label "Documentation"}
   :consistency   {:weight 0.15 :label "Consistency"}})

(defn extend-rubric
  "default-rubric（または任意のrubric）にconsumer固有のカテゴリを足す。
   同名キーはextra-categories側で上書きされる。"
  [rubric extra-categories]
  (merge rubric extra-categories))

(defn- normalize-weights [rubric]
  (let [total (reduce + (map :weight (vals rubric)))]
    (into {} (for [[k v] rubric] [k (assoc v :weight (/ (:weight v) total))]))))

(defn weighted-score
  "scores: {category-key score(0-100)} からrubricの重みで加重平均(0-100)を
   計算する。rubricに定義の無いcategory-keyのscoreは無視する。rubricに
   あってscoresに無いカテゴリは0点として扱う（未採点を高評価にしない）。"
  [rubric scores]
  (let [normalized (normalize-weights rubric)]
    (reduce +
            (for [[k {:keys [weight]}] normalized]
              (* weight (double (get scores k 0)))))))

(defn grade
  "0-100の総合スコアから文字グレードを返す。"
  [total]
  (cond
    (>= total 95) :s
    (>= total 85) :a
    (>= total 70) :b
    (>= total 50) :c
    :else :d))

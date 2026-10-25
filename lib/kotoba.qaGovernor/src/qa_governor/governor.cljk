(ns qa-governor.governor
  "kotoba-lang/qa-governor — 採点提案(proposal)を検証するgovernor
  (ADR-2607031100)。既存Actorsパターンの単一不変条件『governorが拒否する
  commitをactorは決して行わない』をQAに適用する: 知能ノード(LLM)が返す
  カテゴリごとの採点を、evidenceなしに、または主張と矛盾するevidenceのまま
  無条件で信用しない。"
  (:require [kotoba.lang.text :as str]))

(defn- has-evidence? [{:keys [evidence]}]
  (and (some? evidence) (not (str/blank? (str evidence)))))

(def ^:private contradiction-patterns
  "カテゴリごとに『evidenceの文言がこのパターンにマッチしたら、高スコアの
   主張と矛盾する』という簡易ルール。実運用ではCI/テスト実行ログの構造化
   パースに置き換える必要がある(ADR Open Questions参照、今回はscaffold)。"
  {:stability   #"(?i)\bhang|\bhung|crash|deadlock|timeout"
   ;; `\bfail` (word-boundary at the START only) so it matches fail/failed/
   ;; failing/fails/failure -- `fail\b` (boundary at the END) matched only
   ;; the bare word "fail" and silently missed the far more common past/
   ;; present-participle phrasing a real evidence string uses ("3 tests
   ;; failed", "all tests failing").
   :correctness #"(?i)failure|error|\bfail"})

(def ^:private high-score-threshold
  "この値以上の自己申告scoreは、矛盾evidenceが無いか厳しめに確認する。"
  70)

(defn- contradicts? [category score evidence]
  (when-let [pattern (get contradiction-patterns category)]
    (and (>= score high-score-threshold)
         (re-find pattern (str evidence)))))

(defn evaluate-entry
  "1カテゴリぶんの提案{:category :score :evidence}を検証し、
   {:category :score :verdict (:approved|:rejected) :reason}を返す。"
  [{:keys [category score evidence] :as entry}]
  (cond
    (not (has-evidence? entry))
    {:category category :score score :verdict :rejected :reason :missing-evidence}

    (contradicts? category score evidence)
    {:category category :score score :verdict :rejected :reason :evidence-contradicts-score}

    :else
    {:category category :score score :verdict :approved :reason nil}))

(defn evaluate-proposal
  "proposal(1カテゴリぶんのマップのcoll)を検証し、
   {:approved [...] :rejected [...] :all-approved? bool}を返す。
   1件でもrejectedがあれば:all-approved?はfalse——台帳へのcommitは
   呼び出し側の責務だが、この不変条件を守るゲートとして使う。"
  [proposal]
  (let [results (map evaluate-entry proposal)
        grouped (group-by :verdict results)]
    {:approved (get grouped :approved [])
     :rejected (get grouped :rejected [])
     :all-approved? (empty? (get grouped :rejected []))}))

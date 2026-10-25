(ns qa-governor.ledger
  "kotoba-lang/qa-governor — QA採点結果のappend-only監査台帳
  (ADR-2607031100)。governorで承認された結果のみをここに積む想定
  （governor自体は台帳を知らない——単一責任を保つ）。

  pureに保つため、timestamp-msは呼び出し側が渡す（内部でSystem/currentTimeMillis
  やDate.now相当は使わない）。")

(def empty-ledger
  "台帳の初期値。単なるvector。"
  [])

(defn record
  "1件の台帳レコードをledgerに追記する。既存レコードは変更しない
   （append-only）。"
  [ledger entry]
  (conj ledger (select-keys entry [:repo :timestamp-ms :scores :total :grade :verdict])))

(defn history
  "指定repoぶんのレコードだけを、記録された順のまま返す。"
  [ledger repo]
  (filterv #(= repo (:repo %)) ledger))

(defn latest
  "指定repoの最新レコード（無ければnil）。"
  [ledger repo]
  (last (history ledger repo)))

(defn trend
  "指定repoの直近n件のtotalスコアを、古い順のvectorで返す
   （品質推移をグラフ化する時などに使う）。"
  [ledger repo n]
  (->> (history ledger repo)
       (take-last n)
       (mapv :total)))

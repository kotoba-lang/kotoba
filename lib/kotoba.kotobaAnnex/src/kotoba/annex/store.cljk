(ns kotoba.annex.store
  "git-annex external special remote の **store 契約**（注入可能 seam）と、
   純テスト用の in-memory 実装。kotobase-server が store map を注入する設計
   （get-fn/put!/head-get/head-put!、ADR-2607051000）と同じ思想 — プロトコル
   エンジンは store 契約だけに依存し、実体（directory / kotobase.net / B2）は差し替える。

   store 契約（1 引数 map の関数群、いずれも同期でよい）:
     :store!    (fn [key bytes]) -> truthy   ; key（annex key 文字列）で bytes を保存
     :retrieve  (fn [key])       -> bytes|nil ; 無ければ nil
     :present?  (fn [key])       -> :yes|:no|:unknown
     :remove!   (fn [key])       -> truthy
     :init!     (fn [])          -> truthy    ; INITREMOTE 時（冪等）
     :prepare!  (fn [config])    -> truthy    ; PREPARE 時（config = GETCONFIG 済み map）

   key は git-annex の annex key（例 \"SHA256E-s1234--abcd...\"）で content-address。
   kotobase の block store は content-address なので、key をそのまま block cid に
   使える（衝突しない — key 自体が内容ハッシュを含む）。")

(defn in-memory-store
  "atom backed の in-memory store（テスト用）。init/prepare は no-op。"
  ([] (in-memory-store (atom {})))
  ([a]
   {:backing a
    :store!   (fn [key bytes] (swap! a assoc key bytes) true)
    :retrieve (fn [key] (get @a key))
    :present? (fn [key] (if (contains? @a key) :yes :no))
    :remove!  (fn [key] (swap! a dissoc key) true)
    :init!    (fn [] true)
    :prepare! (fn [_config] true)}))

(defn roundtrip-ok?
  "store 契約の store→present?→retrieve→remove→present? が整合するか（テスト補助）。"
  [store key bytes]
  (and ((:store! store) key bytes)
       (= :yes ((:present? store) key))
       (= bytes ((:retrieve store) key))
       ((:remove! store) key)
       (= :no ((:present? store) key))))

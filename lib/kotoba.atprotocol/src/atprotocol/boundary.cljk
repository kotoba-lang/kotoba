(ns atprotocol.boundary
  "atprotocol = kotoba-protocol の上に立つ投影層 — 責務境界の正本
  (ADR-2607071500)。

  atproto 互換 (lexicon / record / XRPC / handle / repo-commit wire) は
  『kotoba graph の別 encoding』であり、真実 (鍵・datom・CID/IPNS・配布) は
  常に kotoba-protocol 側にある。この表がその宣言で、テストが検証する。")

(def boundary
  [;; atprotocol が所有するもの (wire / 互換形)
   {:concern :handle-resolution :owner :atprotocol
    :note "handle ↔ DID。fail-open の did:web 導出や registry 検索を含む"}
   {:concern :lexicon :owner :atprotocol
    :note "NSID / record スキーマ。atproto 流に record として公開・DNS _lexicon 解決"}
   {:concern :record-codec :owner :atprotocol
    :note "record ⇄ datom の双方向投影 (atprotocol.projection)"}
   {:concern :xrpc :owner :atprotocol
    :note "com.atproto.* / app.bsky.* 互換エンドポイント (PDS/AppView)"}
   {:concern :repo-commit-wire :owner :atprotocol
    :note "repo commit / MST / firehose の atproto wire encoding"}
   {:concern :profile-view :owner :atprotocol
    :note ":kotoba.app/* → profile view への投影 (atprotocol.profile)。旧 W-Protocol fields はここの deprecated alias"}

   ;; kotoba-protocol へ委譲するもの (真実)
   {:concern :identity-keys :owner :kotoba-protocol
    :note "Ed25519 did:key、CACAO 検証 (L3)"}
   {:concern :fact-truth :owner :kotoba-protocol
    :note "datom が唯一の真実 (L1)。record は投影"}
   {:concern :graph-cid :owner :kotoba-protocol
    :note "graph の同一性 (L2)"}
   {:concern :mutable-head :owner :kotoba-protocol
    :note "鍵由来 IPNS head (L3 naming / L4 publish)"}
   {:concern :distribution :owner :kotoba-protocol
    :note "IPFS/pinning/B2 (L4)"}
   {:concern :app-manifest :owner :kotoba-protocol
    :note ":kotoba.app/* datoms / bundle CID / caps (L5)"}])

(defn owner
  "関心事 → :atprotocol | :kotoba-protocol | nil。"
  [concern]
  (:owner (first (filter #(= concern (:concern %)) boundary))))

(defn delegated?
  "この関心事は kotoba-protocol へ委譲されるか。"
  [concern]
  (= :kotoba-protocol (owner concern)))

(ns atprotocol.app-record
  "app manifest の atproto record 投影 (ADR-2607071500)。

  正は kotoba-protocol の :kotoba.app/* datoms。atproto 側では collection
  `net.kotoba.app.manifest` の record (JSON) として流通する — この ns が
  その双方向 codec。record JSON のキーは camelCase 文字列 (JSON に keyword は
  無い)、EDN 側は :kotoba.app/* qualified keyword。

  round-trip 検証は validate-manifest (kotoba.protocol.app) に委譲する。"
  (:require [kotoba.protocol.app :as app]))

(def collection "net.kotoba.app.manifest")

(def rkey
  "actor は app を 1 つ advertise する — profile と同じ self rkey。"
  "self")

(def ^:private field->attr
  {:id :kotoba.app/id
   :version :kotoba.app/version
   :kind :kotoba.app/kind
   :bundleCid :kotoba.app/bundle-cid
   :entry :kotoba.app/entry
   :embedUrl :kotoba.app/embed-url
   :appviewOf :kotoba.app/appview-of
   :wasm :kotoba.app/wasm
   :caps :kotoba.app/caps
   :limits :kotoba.app/limits
   :latest :kotoba.app/latest
   :icon :kotoba.app/icon
   :sig :kotoba.app/sig})

(def ^:private attr->field
  (into {} (map (fn [[f a]] [a f])) field->attr))

(defn record->manifest
  "record value (keywordized JSON map) → :kotoba.app/* manifest entity。
  未知フィールドは黙って落とさず :atprotocol/unprojected に保全する。"
  [value]
  (reduce-kv (fn [m k v]
               (if (= k :$type)
                 m
                 (if-let [attr (field->attr k)]
                   (assoc m attr v)
                   (assoc-in m [:atprotocol/unprojected k] v))))
             {}
             (or value {})))

(defn manifest->record
  "manifest entity → record value map ($type 付き)。:kotoba.app/* 以外の
  属性は record に出さない (投影は一級語彙のみ)。"
  [manifest]
  (reduce-kv (fn [m attr v]
               (if-let [field (attr->field attr)]
                 (assoc m field v)
                 m))
             {:$type collection}
             manifest))

(defn valid-record?
  "record value が投影後に valid な manifest になるか。→ problems ([] = ok)。"
  [value]
  (app/validate-manifest (dissoc (record->manifest value) :atprotocol/unprojected)))

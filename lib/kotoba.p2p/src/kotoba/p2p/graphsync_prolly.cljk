(ns kotoba.p2p.graphsync-prolly
  "Bounded Prolly Tree delta transfer as an explicit GraphSync extension.

  The requester declares a base root it already holds. The responder compares
  that root with the request root and returns only target blocks not proven
  shared by CID. Wire framing remains ordinary GraphSync v2; this namespace
  only defines the extension value and its fail-closed fulfillment policy."
  (:require [ipld.core :as ipld]
            [ipld.link :as link]
            [kotoba.p2p.graphsync :as gs]
            [prolly-tree.diff :as diff]))

(def extension-name "kotoba.graphsync/prolly-base-root/1")

(defn- invalid! [message data]
  (throw (ex-info message (assoc data :type :graphsync/invalid-prolly-extension))))

(defn with-base-root
  "Attach the Prolly base-root extension to a GraphSync `:new` request."
  [request base-root]
  (when-not (and (= :new (:type request)) (string? base-root))
    (invalid! "graphsync prolly: new request and CID base root required"
              {:request-type (:type request) :base-root base-root}))
  (assoc-in request [:extensions extension-name]
            {"base" (link/link base-root)}))

(defn base-root
  "Decode and validate the extension, returning its CID string."
  [request]
  (let [value (get (:extensions request) extension-name)]
    (when-not (and (map? value) (= #{"base"} (set (keys value)))
                   (link/link? (get value "base")))
      (invalid! "graphsync prolly: malformed base-root extension"
                {:extension value}))
    (link/link-cid (get value "base"))))

(defn fulfill-request
  "Fulfill an extension request under responder-owned sync limits.

  Returns `{:message graphsync-message :stats planner-stats}`. The request
  cannot relax `:max-blocks`, `:max-bytes`, or `:max-reads`; those values are
  supplied only by the responder host."
  [get-fn request sync-limits]
  (when-not (= :new (:type request))
    (invalid! "graphsync prolly: only new requests can be fulfilled"
              {:request-type (:type request)}))
  (let [base (base-root request)
        result (diff/sync-blocks* get-fn base (:root request) sync-limits)
        blocks (:blocks result)]
    {:message
     {:responses [{:id (:id request)
                   :status (:completed-full gs/status)
                   :metadata (mapv (fn [{:keys [cid]}]
                                     {:cid cid :action :present}) blocks)
                   :extensions {extension-name
                                {"base" (link/link base)
                                 "target" (link/link (:root request))}}}]
      :blocks blocks}
     :stats (:stats result)}))

(defn land-delta!
  "CID-verify and land a decoded delta response through caller-owned `put-fn`.

  Metadata must name exactly the supplied blocks and a non-empty delta must be
  root-first. This function does not claim the base exists; the caller proves
  completion by reading the target through its combined store."
  [put-fn target-root message]
  (when-not (fn? put-fn)
    (invalid! "graphsync prolly: put-fn required" {}))
  (let [response (first (:responses message))
        blocks (vec (:blocks message))
        cids (mapv :cid blocks)
        metadata-cids (mapv :cid (:metadata response))
        proof (get-in response [:extensions extension-name])]
    (when-not (and (= 1 (count (:responses message)))
                   (= (:completed-full gs/status) (:status response))
                   (map? proof)
                   (= #{"base" "target"} (set (keys proof)))
                   (link/link? (get proof "base"))
                   (= (link/link target-root) (get proof "target"))
                   (= (set cids) (set metadata-cids))
                   (= (count cids) (count (set cids)))
                   (or (empty? blocks) (= target-root (first cids))))
      (invalid! "graphsync prolly: response proof is inconsistent"
                {:target target-root :block-cids cids
                 :metadata-cids metadata-cids :response response}))
    (doseq [{:keys [cid bytes]} blocks]
      (let [actual (ipld/cid bytes)]
        (when-not (= cid actual)
          (invalid! "graphsync prolly: block CID mismatch"
                    {:expected cid :actual actual}))
        (put-fn cid bytes)))
    {:target target-root :blocks (count blocks)}))

(ns kotoba.write
  "Browser write path — publish a member-signed commit to a holder, trustlessly.

   Symmetric to the read plane: the browser builds a content-addressed,
   member-signed commit entirely locally (`KotobaNode.assert` → `commitHeadSigned`
   → `exportBlocks`), then publishes it:

     block.put   each captured Prolly block (content-addressed; server recomputes
                 the CID, so the holder can't substitute bytes)
     ipns.publish the member-signed IpnsRecord (advances the head)

   AUTHORITY is the Ed25519 signature over a key-derived IPNS name, NOT a server
   credential — the holder is an untrusted relay. This is takeover-proof exactly
   for sovereign / DID-scoped graphs (the name binds to the signing key). For a
   SHARED graph whose head name is not key-derived, signatures alone don't grant
   write access; use the CACAO-gated `datomic.transact` path instead.
   See docs/ADR-browser-cid-query-vs-p2p.md."
  (:require [kotoba.blocks :as blocks]))

(defn- hex->bytes [hex]
  (let [n   (quot (.-length hex) 2)
        out (js/Uint8Array. n)]
    (dotimes [i n]
      (aset out i (js/parseInt (.substr hex (* 2 i) 2) 16)))
    out))

(defn- block-put
  "POST one content-addressed block; the server recomputes + returns its CID."
  [remote ^js bytes fetch-fn]
  (-> (fetch-fn (str remote "/xrpc/com.etzhayyim.apps.kotoba.block.put")
                #js {:method  "POST"
                     :headers #js {"content-type" "application/json"}
                     :body    (js/JSON.stringify #js {:data_b64 (blocks/bytes->b64 bytes)})})
      (.then (fn [^js r]
               (if (.-ok r)
                 (.json r)
                 (throw (js/Error. (str "block.put → HTTP " (.-status r)))))))))

(defn- ipns-publish
  "POST a member-signed IpnsRecord JSON string to advance the head."
  [remote ^string record-json fetch-fn]
  (-> (fetch-fn (str remote "/xrpc/com.etzhayyim.apps.kotoba.ipns.publish")
                #js {:method  "POST"
                     :headers #js {"content-type" "application/json"}
                     :body    record-json})
      (.then (fn [^js r]
               (if (.-ok r)
                 (.json r)
                 (-> (.text r)
                     (.then (fn [t]
                              (throw (js/Error. (str "ipns.publish → HTTP " (.-status r) " " t)))))))))))

(defn publish!
  "Publish the node's committed write-set to `remote`:
     1. push every captured block via block.put (content-addressed),
     2. advance the head via ipns.publish with the member-signed record.

   `head-record-json` is the string returned by `KotobaNode.commitHeadSigned`
   (which commits AND signs). Returns Promise<#js{blocks, publish}>.

   The holder is untrusted: block bytes are CID-checked server-side, and the head
   pointer is only as authoritative as the key that signed `head-record-json`."
  [^js node head-record-json {:keys [remote fetch-fn] :or {fetch-fn js/fetch}}]
  (let [blocks-arr (js/JSON.parse (.exportBlocks node))]
    (-> (js/Promise.all
         (clj->js (map (fn [^js b] (block-put remote (hex->bytes (.-hex b)) fetch-fn))
                       (array-seq blocks-arr))))
        (.then (fn [^js put-results]
                 (-> (ipns-publish remote head-record-json fetch-fn)
                     (.then (fn [^js pub]
                              #js {:blocks  (.-length put-results)
                                   :publish pub}))))))))

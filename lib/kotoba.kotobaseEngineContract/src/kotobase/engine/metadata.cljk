(ns kotobase.engine.metadata
  "Bounded, confidential metadata segments shared by durable engines.

  Engine manifests link one immutable segment instead of embedding cumulative
  history and idempotency maps. Segment links remain visible for reachability;
  their payloads always cross the caller-provided seal/open boundary."
  (:require [ipld.core :as ipld]
            [ipld.value :as value]
            [kotobase.engine.completion :as completion]))

(def segment-format "kotobase.engine-metadata/v1")

(defn segment-node
  "Build the public envelope for one already-sealed metadata payload."
  [previous sealed-payload]
  (cond-> {"format" segment-format
           "payload" sealed-payload}
    previous (assoc "previous" (ipld/link previous))))

(defn persist-segment!
  "Encode DELTA canonically, seal it, persist its immutable envelope, and
  return the segment CID. SEAL may return an immediate value or completion."
  [put! seal previous delta]
  (completion/then-result
   (seal (value/encode-value delta))
   (fn [sealed]
     (ipld/put-node! put! (segment-node previous sealed)))))

(defn decode-segment
  "Validate and open a decoded segment node. Returns
  `{:previous cid-or-nil :delta value}` or a completion of that map."
  [open node]
  (when-not (= segment-format (get node "format"))
    (throw (ex-info "unsupported engine metadata segment"
                    {:type :kotobase.engine/unsupported-metadata-segment
                     :format (get node "format")})))
  (completion/then-result
   (open (get node "payload"))
   (fn [plaintext]
     {:previous (some-> (get node "previous") ipld/link-cid)
      :delta (value/decode-value plaintext)})))

(defn restore-chain
  "Read and open HEAD through its previous links. The result is ordered from
  oldest to newest. GET-FN and OPEN may be immediate or completion-valued.
  DECODE-NODE lets an engine unwrap a storage envelope before validation."
  ([get-fn open head]
   (restore-chain get-fn open ipld/decode head))
  ([get-fn open decode-node head]
   (letfn [(step [cid newest-first]
             (if-not cid
               (vec (reverse newest-first))
               (completion/then-result
                (get-fn cid)
                (fn [bytes]
                  (when-not bytes
                    (throw (ex-info "engine metadata block was not found"
                                    {:type :kotobase.engine/missing-metadata-block
                                     :cid cid})))
                  (completion/then-result
                   (decode-segment open (decode-node bytes))
                   (fn [{:keys [previous] :as segment}]
                     (step previous (conj newest-first segment))))))))]
     (step head []))))

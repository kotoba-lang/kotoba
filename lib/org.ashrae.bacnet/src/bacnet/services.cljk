(ns bacnet.services
  "Service-parameter bodies for the four services this library covers —
  ReadProperty, WriteProperty (Clause 15.5 / 15.9, both Confirmed), Who-Is
  and I-Am (Clause 16.10, both Unconfirmed). These are the bytes that go
  in `bacnet.apdu`'s `:params`/`:payload`, not whole APDUs.

  **The classic mixup this module exists to keep straight**: ReadProperty
  and WriteProperty parameters are CONTEXT-tagged (tag numbers 0/1/2/3/4
  reused per-field, per `bacnet.tags`'s class-bit explanation), but I-Am's
  four fields are APPLICATION-tagged — plain Table 20-1 primitives with no
  context wrapper at all. A decoder that always expects context tags
  because 'that is how services normally look' silently misreads I-Am,
  because an application-tagged ObjectIdentifier and a context-tagged one
  differ only in the class bit, and both parse as *something* if you are
  not checking which one the service promised.

  ReadProperty-Request (15.5, ASN.1 SEQUENCE):
    [0] objectIdentifier        BACnetObjectIdentifier
    [1] propertyIdentifier      BACnetPropertyIdentifier (Enumerated encoding)
    [2] propertyArrayIndex      Unsigned OPTIONAL

  ReadProperty-ACK (15.5, service ack):
    [0] objectIdentifier  [1] propertyIdentifier  [2] propertyArrayIndex OPTIONAL
    [3] propertyValue     — an OPENING tag 3, one-or-more application-tagged
                             primitives, a CLOSING tag 3. The open/close
                             bracket is what lets propertyValue hold an
                             arbitrary-shape value (a whole array, for
                             instance) without a length prefix of its own.

  WriteProperty-Request (15.9): objectIdentifier/propertyIdentifier/
  propertyArrayIndex as above, [3] propertyValue (same open/close bracket),
  [4] priority Unsigned(1..16) OPTIONAL. Response is a bare SimpleACK — no
  service-ack body — so there is no `decode-write-property-ack` here.

  Who-Is-Request (16.10): [0] deviceInstanceRangeLowLimit Unsigned OPTIONAL,
  [1] deviceInstanceRangeHighLimit Unsigned OPTIONAL. Both present or both
  absent — a range with only one bound is not a legal encoding, and this
  module rejects it rather than guessing what the missing bound should be.

  I-Am-Request (16.10), all APPLICATION-tagged in this fixed order:
  iAmDeviceIdentifier (ObjectIdentifier), maxAPDULengthAccepted (Unsigned),
  segmentationSupported (Enumerated — BACnetSegmentation), vendorID
  (Unsigned)."
  (:require [bacnet.tags :as tags]))

;; A handful of BACnetPropertyIdentifier enumeration values (Clause 21) —
;; the ones exercised by this library's own tests, not the whole ~200-entry
;; table. Cited by the numbers commonly published for this enumeration;
;; treat additions to this map as needing the same care as any other
;; spec-derived constant, not as free-form naming.
(def property-identifiers
  {:object-identifier 75 :object-name 77 :object-type 79
   :present-value 85 :description 28 :units 117})
;; `property-identifiers` is keyword -> code; this is the reverse, code ->
;; keyword, used when decoding a wire property-identifier number back to a
;; name.
(def property-code->identifier (into {} (map (fn [[k v]] [v k])) property-identifiers))

(def segmentation-values
  {:segmented-both 0 :segmented-transmit 1 :segmented-receive 2 :no-segmentation 3})
(def segmentation-code->kw (into {} (map (fn [[k v]] [v k])) segmentation-values))

;; ── ReadProperty ───────────────────────────────────────────────────────

(defn encode-read-property-request
  "`{:object-type t :instance-number i}` + `:property` (a keyword in
  `property-identifiers`, or a raw integer for a property this table
  doesn't name) + optional `:array-index`."
  [{:keys [object-type instance-number property array-index]}]
  (let [prop-code (if (keyword? property) (property-identifiers property) property)]
    (if (nil? prop-code)
      [:error :bacnet/unknown-property]
      (let [oid (tags/encode-object-identifier-value {:object-type object-type
                                                        :instance-number instance-number})]
        (if (= :error (first oid))
          oid
          {:status :ok
           :bytes (into (tags/encode-context-tag 0 (:bytes oid))
                        (concat (tags/encode-context-tag 1 (:bytes (tags/encode-unsigned-value prop-code)))
                                (when array-index
                                  (tags/encode-context-tag
                                   2 (:bytes (tags/encode-unsigned-value array-index))))))})))))

(defn- decode-context-primitive
  "Decodes one context-tagged primitive at `offset`, checking its tag
  number matches `expected-tag`. Returns the raw data bytes (interpretation
  — Unsigned vs ObjectIdentifier — is the caller's job, since context tags
  carry no type information of their own; that is the whole reason the
  class bit exists, per `bacnet.tags`)."
  [bs offset expected-tag]
  (let [header (tags/decode-tag-header bs offset)]
    (cond
      (= :error (first header)) header
      (not (:context? header)) [:error :bacnet/expected-context-tag]
      (not= (:tag-number header) expected-tag) [:error :bacnet/tag-number-mismatch]
      :else {:status :ok
             :bytes (subvec (vec bs) (:next header) (+ (:next header) (:length header)))
             :next (+ (:next header) (:length header))})))

(defn decode-read-property-request
  [bs]
  (let [obj (decode-context-primitive bs 0 0)]
    (if (= :error (first obj)) obj
        (let [oid (tags/decode-object-identifier-value (:bytes obj))]
          (if (= :error (first oid)) oid
              (let [prop (decode-context-primitive bs (:next obj) 1)]
                (if (= :error (first prop)) prop
                    (let [prop-val (tags/decode-unsigned-value (:bytes prop))
                          has-index? (< (:next prop) (count bs))
                          idx (when has-index? (decode-context-primitive bs (:next prop) 2))]
                      (if (and has-index? (= :error (first idx)))
                        idx
                        {:status :ok
                         :object-type (:object-type oid) :instance-number (:instance-number oid)
                         :property (get property-code->identifier (:value prop-val) (:value prop-val))
                         :property-code (:value prop-val)
                         :array-index (when idx (:value (tags/decode-unsigned-value (:bytes idx))))})))))))))

(defn encode-read-property-ack
  "`property-value` is a single `[type value]` pair (see
  `bacnet.tags/encode-application-value`) — BACnet allows a bracketed list
  for array-valued properties, which this library does not build."
  [{:keys [object-type instance-number property array-index property-value]}]
  (let [prop-code (if (keyword? property) (property-identifiers property) property)]
    (if (nil? prop-code)
      [:error :bacnet/unknown-property]
      (let [oid (tags/encode-object-identifier-value {:object-type object-type
                                                        :instance-number instance-number})
            [vtype vval] property-value]
        (if (= :error (first oid))
          oid
          {:status :ok
           :bytes (into (tags/encode-context-tag 0 (:bytes oid))
                        (concat (tags/encode-context-tag 1 (:bytes (tags/encode-unsigned-value prop-code)))
                                (when array-index
                                  (tags/encode-context-tag
                                   2 (:bytes (tags/encode-unsigned-value array-index))))
                                (tags/encode-opening-tag 3)
                                (tags/encode-application-value vtype vval)
                                (tags/encode-closing-tag 3)))})))))

(defn decode-read-property-ack
  [bs]
  (let [obj (decode-context-primitive bs 0 0)]
    (if (= :error (first obj)) obj
        (let [oid (tags/decode-object-identifier-value (:bytes obj))]
          (if (= :error (first oid)) oid
              (let [prop (decode-context-primitive bs (:next obj) 1)]
                (if (= :error (first prop)) prop
                    (let [prop-val (tags/decode-unsigned-value (:bytes prop))
                          open-header (tags/decode-tag-header bs (:next prop))]
                      (cond
                        (= :error (first open-header)) open-header
                        (not (:opening? open-header)) [:error :bacnet/expected-opening-tag]
                        (not= (:tag-number open-header) 3) [:error :bacnet/tag-number-mismatch]
                        :else
                        (let [val (tags/decode-application-value bs (:next open-header))]
                          (if (= :error (first val)) val
                              (let [close-header (tags/decode-tag-header bs (:next val))]
                                (cond
                                  (= :error (first close-header)) close-header
                                  (not (:closing? close-header)) [:error :bacnet/expected-closing-tag]
                                  (not= (:tag-number close-header) 3) [:error :bacnet/tag-number-mismatch]
                                  :else
                                  {:status :ok
                                   :object-type (:object-type oid) :instance-number (:instance-number oid)
                                   :property-code (:value prop-val)
                                   :property-value [(:type val) (:value val)]})))))))))))))

;; ── WriteProperty ──────────────────────────────────────────────────────

(defn encode-write-property-request
  [{:keys [object-type instance-number property array-index property-value priority]}]
  (let [prop-code (if (keyword? property) (property-identifiers property) property)]
    (if (nil? prop-code)
      [:error :bacnet/unknown-property]
      (if (and priority (not (<= 1 priority 16)))
        [:error :bacnet/priority-out-of-range]
        (let [oid (tags/encode-object-identifier-value {:object-type object-type
                                                          :instance-number instance-number})
              [vtype vval] property-value]
          (if (= :error (first oid))
            oid
            {:status :ok
             :bytes (into (tags/encode-context-tag 0 (:bytes oid))
                          (concat (tags/encode-context-tag 1 (:bytes (tags/encode-unsigned-value prop-code)))
                                  (when array-index
                                    (tags/encode-context-tag
                                     2 (:bytes (tags/encode-unsigned-value array-index))))
                                  (tags/encode-opening-tag 3)
                                  (tags/encode-application-value vtype vval)
                                  (tags/encode-closing-tag 3)
                                  (when priority
                                    (tags/encode-context-tag
                                     4 (:bytes (tags/encode-unsigned-value priority))))))}))))))

(defn decode-write-property-request
  [bs]
  (let [obj (decode-context-primitive bs 0 0)]
    (if (= :error (first obj)) obj
        (let [oid (tags/decode-object-identifier-value (:bytes obj))]
          (if (= :error (first oid)) oid
              (let [prop (decode-context-primitive bs (:next obj) 1)]
                (if (= :error (first prop)) prop
                    (let [prop-val (tags/decode-unsigned-value (:bytes prop))
                          open-header (tags/decode-tag-header bs (:next prop))]
                      (cond
                        (= :error (first open-header)) open-header
                        (not (:opening? open-header)) [:error :bacnet/expected-opening-tag]
                        (not= (:tag-number open-header) 3) [:error :bacnet/tag-number-mismatch]
                        :else
                        (let [val (tags/decode-application-value bs (:next open-header))]
                          (if (= :error (first val)) val
                              (let [close-header (tags/decode-tag-header bs (:next val))]
                                (if (or (= :error (first close-header))
                                        (not (:closing? close-header))
                                        (not= (:tag-number close-header) 3))
                                  [:error :bacnet/expected-closing-tag]
                                  (let [after-close (:next close-header)
                                        has-priority? (< after-close (count bs))
                                        prio (when has-priority?
                                               (decode-context-primitive bs after-close 4))]
                                    (if (and has-priority? (= :error (first prio)))
                                      prio
                                      {:status :ok
                                       :object-type (:object-type oid) :instance-number (:instance-number oid)
                                       :property-code (:value prop-val)
                                       :property-value [(:type val) (:value val)]
                                       :priority (when prio (:value (tags/decode-unsigned-value
                                                                      (:bytes prio))))})))))))))))))))

;; ── Who-Is / I-Am ──────────────────────────────────────────────────────

(defn encode-who-is-request
  "No arguments = an unrestricted Who-Is (every device answers). Giving
  `:low-limit`/`:high-limit` narrows it — both or neither, never one."
  ([] {:status :ok :bytes []})
  ([{:keys [low-limit high-limit]}]
   (if (or (and low-limit (not high-limit)) (and high-limit (not low-limit)))
     [:error :bacnet/range-limits-must-be-paired]
     (if (nil? low-limit)
       {:status :ok :bytes []}
       {:status :ok
        :bytes (into (tags/encode-context-tag 0 (:bytes (tags/encode-unsigned-value low-limit)))
                     (tags/encode-context-tag 1 (:bytes (tags/encode-unsigned-value high-limit))))}))))

(defn decode-who-is-request
  [bs]
  (if (empty? bs)
    {:status :ok :low-limit nil :high-limit nil}
    (let [lo (decode-context-primitive bs 0 0)]
      (if (= :error (first lo)) lo
          (let [hi (decode-context-primitive bs (:next lo) 1)]
            (if (= :error (first hi)) hi
                {:status :ok
                 :low-limit (:value (tags/decode-unsigned-value (:bytes lo)))
                 :high-limit (:value (tags/decode-unsigned-value (:bytes hi)))}))))))

(defn encode-i-am-request
  "All four fields APPLICATION-tagged, per this namespace's docstring."
  [{:keys [object-type instance-number max-apdu-length-accepted segmentation-supported vendor-id]}]
  (let [seg-code (segmentation-values segmentation-supported)]
    (if (nil? seg-code)
      [:error :bacnet/unknown-segmentation-value]
      (let [oid-bytes (tags/encode-application-value
                        :object-identifier {:object-type object-type :instance-number instance-number})]
        (if (= :error (first oid-bytes))
          oid-bytes
          {:status :ok
           :bytes (into oid-bytes
                        (concat (tags/encode-application-value :unsigned max-apdu-length-accepted)
                                (tags/encode-application-value :enumerated seg-code)
                                (tags/encode-application-value :unsigned vendor-id)))})))))

(defn decode-i-am-request
  [bs]
  (let [oid (tags/decode-application-value bs 0)]
    (if (= :error (first oid)) oid
        (if (not= (:type oid) :object-identifier)
          [:error :bacnet/expected-object-identifier]
          (let [apdu-len (tags/decode-application-value bs (:next oid))]
            (if (= :error (first apdu-len)) apdu-len
                (let [seg (tags/decode-application-value bs (:next apdu-len))]
                  (if (= :error (first seg)) seg
                      (let [vendor (tags/decode-application-value bs (:next seg))]
                        (cond
                          (= :error (first vendor)) vendor
                          (nil? (segmentation-code->kw (:value seg))) [:error :bacnet/unknown-segmentation-value]
                          :else
                          {:status :ok
                           :object-type (:object-type (:value oid))
                           :instance-number (:instance-number (:value oid))
                           :max-apdu-length-accepted (:value apdu-len)
                           :segmentation-supported (segmentation-code->kw (:value seg))
                           :vendor-id (:value vendor)}))))))))))

(ns iec60870.asdu
  "IEC 60870-5-104 ASDU — the Application Service Data Unit an I-format
  APCI frame carries.

      Type ID (1)  VSQ (1)  COT (2)  Common Address (2, LE)
      [ Information Object Address (3, LE) + element(s) ] …

  `VSQ` (Variable Structure Qualifier): bit 7 is SQ — 0 means every
  information object below carries its own 3-byte address; 1 means only
  the *first* does, and the rest are implicitly consecutive addresses
  (`ioa`, `ioa+1`, `ioa+2`, …). Bits 6-0 are the object count.

  `COT` (Cause of Transmission), 2 octets in the -104 companion standard:
  octet 1 is `T`(test, bit 7) `P/N`(negative confirmation, bit 6) and a
  6-bit cause code; octet 2 is the originator address (0 unless a
  multi-originator station distinguishes them).

  Information objects for the type-id subset this repo implements —
  binary input (1), measured value normalized (9), single command (45),
  interrogation command (100), measured value short-float with time tag
  (36) — live in `element-codecs`, keyed by type id, each entry `{:size
  :encode :decode}` where `:encode`/`:decode` handle the element *after*
  its 3-byte IOA (the IOA itself is this namespace's job, common to every
  type).

  ;; constructed, not a published spec vector — the cause-of-transmission
  ;; codes, quality-descriptor bit positions, SCO (single command) field
  ;; layout and QOI (qualifier of interrogation) values below are
  ;; reproduced from this session's recollection of widely documented IEC
  ;; 60870-5-101/104 usage, not cross-checked against the standard's own
  ;; table text this session. The framing mechanics — VSQ's SQ bit and
  ;; consecutive-address encoding, the 3-byte little-endian IOA, the fixed
  ;; per-type element sizes — are the part of this namespace to trust."
  (:require [iec60870.float32 :as float32]
            [iec60870.time :as time]))

;; ── little-endian integer helpers ───────────────────────────────────────

(defn- byte-at [v shift] (bit-and (bit-shift-right v shift) 0xFF))
(defn- write-i16-le [v] [(byte-at v 0) (byte-at v 8)])
(defn- read-i16-le [bs i]
  (let [u (bit-or (nth bs i) (bit-shift-left (nth bs (inc i)) 8))]
    (if (>= u 0x8000) (- u 0x10000) u)))
(defn- le16 [n] [(bit-and n 0xFF) (bit-and (unsigned-bit-shift-right n 8) 0xFF)])
(defn- rd-le16 [bs i] (+ (nth bs i) (* 256 (nth bs (inc i)))))
(defn- le24 [n]
  [(bit-and n 0xFF) (bit-and (unsigned-bit-shift-right n 8) 0xFF)
   (bit-and (unsigned-bit-shift-right n 16) 0xFF)])
(defn- rd-le24 [bs i] (+ (nth bs i) (* 256 (nth bs (+ i 1))) (* 65536 (nth bs (+ i 2)))))

;; ── quality descriptor (bits shared by several element types) ──────────

(defn encode-quality
  [{:keys [blocked substituted not-topical invalid]}]
  (bit-or (if blocked 0x10 0) (if substituted 0x20 0) (if not-topical 0x40 0) (if invalid 0x80 0)))

(defn decode-quality
  [b]
  {:blocked (bit-test b 4) :substituted (bit-test b 5) :not-topical (bit-test b 6) :invalid (bit-test b 7)})

;; ── cause of transmission ────────────────────────────────────────────────

(def causes
  {:periodic 1 :spontaneous 3 :request 5 :activation 6 :activation-confirmation 7
   :deactivation 8 :deactivation-confirmation 9 :activation-termination 10
   :interrogated-by-station 20
   :unknown-type-id 44 :unknown-cause 45 :unknown-common-address 46 :unknown-ioa 47})
(def ^:private causes-inv (into {} (map (juxt val key)) causes))

(defn encode-cot
  [{:keys [cause test negative originator-address] :or {originator-address 0}}]
  (let [code (if (keyword? cause) (get causes cause) cause)]
    [(bit-or (bit-and code 0x3F) (if negative 0x40 0) (if test 0x80 0))
     (bit-and originator-address 0xFF)]))

(defn decode-cot
  [b1 b2]
  {:cause (get causes-inv (bit-and b1 0x3F) (bit-and b1 0x3F))
   :negative (bit-test b1 6)
   :test (bit-test b1 7)
   :originator-address b2})

;; ── information elements, keyed by type id ──────────────────────────────

(def type-ids
  {:m-sp-na-1 1 :m-me-na-1 9 :c-sc-na-1 45 :c-ic-na-1 100 :m-me-tf-1 36})

(def element-codecs
  {1 {:size 1
      :encode (fn [{:keys [spi quality]}] [(bit-or (if spi 1 0) (encode-quality quality))])
      :decode (fn [bs i]
                 {:element {:spi (bit-test (nth bs i) 0) :quality (decode-quality (nth bs i))}
                  :size 1})}
   9 {:size 3
      :encode (fn [{:keys [value quality]}]
                 (into (write-i16-le value)
                       [(bit-or (if (:overflow quality) 1 0) (encode-quality quality))]))
      :decode (fn [bs i]
                 (let [qb (nth bs (+ i 2))]
                   {:element {:value (read-i16-le bs i)
                              :quality (assoc (decode-quality qb) :overflow (bit-test qb 0))}
                    :size 3}))}
   45 {:size 1
       :encode (fn [{:keys [scs qu select-execute]}]
                  [(bit-or (if scs 1 0) (bit-shift-left (bit-and qu 0x1F) 2) (if select-execute 0x80 0))])
       :decode (fn [bs i]
                  (let [b (nth bs i)]
                    {:element {:scs (bit-test b 0)
                               :qu (bit-and (unsigned-bit-shift-right b 2) 0x1F)
                               :select-execute (bit-test b 7)}
                     :size 1}))}
   100 {:size 1
        :encode (fn [{:keys [qoi]}] [(bit-and qoi 0xFF)])
        :decode (fn [bs i] {:element {:qoi (nth bs i)} :size 1})}
   36 {:size 12
       :encode (fn [{:keys [value quality timestamp]}]
                  (-> (float32/write-float32-le value)
                      (into [(encode-quality quality)])
                      (into (time/encode-cp56time2a timestamp))))
       :decode (fn [bs i]
                  {:element {:value (float32/read-float32-le bs i)
                             :quality (decode-quality (nth bs (+ i 4)))
                             :timestamp (:point (time/decode-cp56time2a bs (+ i 5)))}
                   :size 12})}})

;; Qualifiers of interrogation (QOI, the payload of C_IC_NA_1): 20 is a
;; whole-station ("global") interrogation, 21..36 select interrogation
;; group 1..16.
(def qoi-station 20)
(defn qoi-group [n] (+ 20 n))

;; ── ASDU ─────────────────────────────────────────────────────────────────

(defn encode-asdu
  "`{:type-id :sq :cot :common-address :objects […]}`. `:objects` is
  `[{:ioa n :element {...}} …]`; when `:sq` is true only the first `:ioa`
  is written to the wire (the rest must — and, since this is round-trip
  tested against `decode-asdu`, will — be consecutive)."
  [{:keys [type-id sq cot common-address objects] :or {sq false}}]
  (let [codec (get element-codecs type-id)]
    (cond
      (nil? codec) {:status :error :reason :unknown-type-id :type-id type-id}
      (not (<= 0 common-address 0xFFFF))
      {:status :error :reason :common-address-out-of-range :value common-address}
      (not (<= 0 (count objects) 0x7F))
      {:status :error :reason :object-count-out-of-range :value (count objects)}
      :else
      (let [vsq (bit-or (if sq 0x80 0) (bit-and (count objects) 0x7F))
            header (-> [type-id vsq]
                       (into (encode-cot cot))
                       (into (le16 common-address)))
            body (if (and sq (seq objects))
                   (-> (le24 (:ioa (first objects)))
                       (into (mapcat #((:encode codec) (:element %)) objects)))
                   (mapcat (fn [{:keys [ioa element]}] (into (le24 ioa) ((:encode codec) element)))
                           objects))]
        {:status :ok :bytes (into header (vec body))}))))

(defn- decode-objects-sq0
  [buf n-total codec pos n]
  (loop [i 0 pos pos out []]
    (if (= i n)
      {:status :ok :objects out :pos pos}
      (if (> (+ pos 3 (:size codec)) n-total)
        {:status :incomplete :need (- (+ pos 3 (:size codec)) n-total)}
        (let [ioa (rd-le24 buf pos)
              {:keys [element]} ((:decode codec) buf (+ pos 3))]
          (recur (inc i) (+ pos 3 (:size codec)) (conj out {:ioa ioa :element element})))))))

(defn- decode-objects-sq1
  [buf n-total codec pos n]
  (if (zero? n)
    {:status :ok :objects [] :pos pos}
    (if (> (+ pos 3) n-total)
      {:status :incomplete :need (- (+ pos 3) n-total)}
      (let [start-ioa (rd-le24 buf pos)]
        (loop [i 0 pos (+ pos 3) out []]
          (if (= i n)
            {:status :ok :objects out :pos pos}
            (if (> (+ pos (:size codec)) n-total)
              {:status :incomplete :need (- (+ pos (:size codec)) n-total)}
              (let [{:keys [element]} ((:decode codec) buf pos)]
                (recur (inc i) (+ pos (:size codec)) (conj out {:ioa (+ start-ioa i) :element element}))))))))))

(defn decode-asdu
  "Decode one ASDU from the front of `buf`. Returns `{:status :ok :asdu
  {…} :consumed n}`, `{:status :incomplete :need n}`, or a named `:error`."
  [buf]
  (let [buf (vec buf) n (count buf)]
    (if (< n 6)
      {:status :incomplete :need (- 6 n)}
      (let [type-id (nth buf 0)
            vsq (nth buf 1)
            sq (bit-test vsq 7)
            obj-count (bit-and vsq 0x7F)
            cot (decode-cot (nth buf 2) (nth buf 3))
            common-address (rd-le16 buf 4)
            codec (get element-codecs type-id)]
        (if (nil? codec)
          {:status :error :reason :unknown-type-id :type-id type-id}
          (let [r (if sq
                    (decode-objects-sq1 buf n codec 6 obj-count)
                    (decode-objects-sq0 buf n codec 6 obj-count))]
            (case (:status r)
              :ok {:status :ok
                   :consumed (:pos r)
                   :asdu {:type-id type-id :sq sq :cot cot :common-address common-address
                          :objects (:objects r)}}
              r)))))))

(ns iec61850.goose
  "The GOOSE PDU (IEC 61850-8-1 clause 8.1) and its retransmission state
  machine.

  ```
  GOOSE-PDU ::= [APPLICATION 1] IMPLICIT SEQUENCE {
      gocbRef             [0] IMPLICIT VisibleString,
      timeAllowedToLive   [1] IMPLICIT INTEGER,
      datSet              [2] IMPLICIT VisibleString,
      goID                [3] IMPLICIT VisibleString OPTIONAL,
      t                   [4] IMPLICIT UtcTime,
      stNum               [5] IMPLICIT INTEGER,
      sqNum               [6] IMPLICIT INTEGER,
      simulation          [7] IMPLICIT BOOLEAN DEFAULT FALSE,
      confRev             [8] IMPLICIT INTEGER,
      ndsCom              [9] IMPLICIT BOOLEAN DEFAULT FALSE,
      numDatSetEntries    [10] IMPLICIT INTEGER,
      allData             [11] IMPLICIT SEQUENCE OF Data
  }
  ```

  (`security [12] IMPLICIT ANY OPTIONAL` exists in the full grammar and is
  out of scope here — nothing in this library signs or encrypts GOOSE.)
  Same provenance caveat as `iec61850.data`: this grammar is reconstructed
  from public open-source GOOSE stacks and dissectors (it is the form
  matched by, among others, Wireshark's public `packet-goose.c`, whose
  `[APPLICATION 1]` tag is exactly the `0x61` byte this namespace emits),
  not transcribed from the paywalled standard text.

  Every field is built through `asn1.core` — `asn1/implicit` for the
  INTEGER/BOOLEAN fields (identical technique to `iec61850.data`), so the
  DER-minimal-integer and boolean-octet rules are `org-ietf-asn1`'s, not
  reimplemented here — with two exceptions that are not nested BER at all:
  `t`, whose 8 content octets are `iec61850.utctime`'s binary encoding, and
  the string fields, which reuse `asn1/ia5-string`'s ASCII content-octet
  encoding under a context tag (VisibleString and IA5String share the same
  printable-ASCII content form; only the universal tag number differs, and
  IMPLICIT tagging discards that number on the wire anyway)."
  (:require [asn1.core :as asn1]
            [iec61850.data :as data]
            [iec61850.utctime :as utctime]))

(def application-tag 1)

(defn- ctx-int [n v] (asn1/implicit n (asn1/integer v)))
(defn- ctx-bool [n v] (asn1/implicit n (asn1/boolean* (boolean v))))
(defn- ctx-string [n s] (asn1/implicit n (asn1/ia5-string s)))

;; ── encode ───────────────────────────────────────────────────────────────────

(defn encode
  "The goosePdu map -> the BER octets of the `[APPLICATION 1]` SEQUENCE (this
  is the APDU that `iec61850.appdu/encode` wraps in an Ethernet frame, not a
  full frame itself).

  `allData` is a seq of `[choice value]` pairs as `iec61850.data/encode-data`
  takes. `numDatSetEntries` is computed from `(count allData)`, never taken
  from the caller, so the two cannot silently disagree — a real IED that
  sends a `numDatSetEntries` inconsistent with the SEQUENCE it sends is
  exactly the kind of malformed input the negative-test suite covers on the
  decode side."
  [{:keys [gocbRef timeAllowedToLive datSet goID t stNum sqNum simulation
           confRev ndsCom allData]
    :or {simulation false ndsCom false allData []}}]
  (let [elements (cond-> [(ctx-string 0 gocbRef)
                           (ctx-int 1 timeAllowedToLive)
                           (ctx-string 2 datSet)]
                   goID (conj (ctx-string 3 goID))
                   true (conj {:asn1/class :context :asn1/tag 4 :asn1/constructed? false
                                :asn1/content (utctime/encode t)}
                               (ctx-int 5 stNum)
                               (ctx-int 6 sqNum)
                               (ctx-bool 7 simulation)
                               (ctx-int 8 confRev)
                               (ctx-bool 9 ndsCom)
                               (ctx-int 10 (count allData))
                               {:asn1/class :context :asn1/tag 11 :asn1/constructed? true
                                :asn1/elements (mapv data/encode-data allData)}))]
    (asn1/encode-ints {:asn1/class :application :asn1/tag application-tag
                        :asn1/constructed? true :asn1/elements elements})))

;; ── decode ───────────────────────────────────────────────────────────────────
;;
;; Each field is a "step": `(fn [element acc] -> [:ok {field val}] |
;; [:error kw data])`. `decode` reduces the field list over the parsed
;; SEQUENCE, merging each step's map into an accumulator and stopping at the
;; first `:error` — a small hand-rolled Result monad rather than nested
;; `let`s, so a 12-field record does not turn into 12 levels of indentation.

(defn- step-string [n field]
  (fn [element _acc]
    (if-let [e (asn1/find-context element n)]
      [:ok {field (asn1/string-value e)}]
      [:error :iec61850.goose/missing-field {:field field}])))

(defn- step-optional-string [n field]
  (fn [element _acc]
    (let [e (asn1/find-context element n)]
      [:ok {field (when e (asn1/string-value e))}])))

(defn- step-int [n field]
  (fn [element _acc]
    (if-let [e (asn1/find-context element n)]
      (try [:ok {field (asn1/integer-value e)}]
           (catch #?(:clj Exception :cljs :default) ex
             [:error :iec61850.goose/bad-integer-field {:field field :message (ex-message ex)}]))
      [:error :iec61850.goose/missing-field {:field field}])))

(defn- step-bool [n field default]
  (fn [element _acc]
    (if-let [e (asn1/find-context element n)]
      (try [:ok {field (asn1/boolean-value e)}]
           (catch #?(:clj Exception :cljs :default) ex
             [:error :iec61850.goose/bad-boolean-field {:field field :message (ex-message ex)}]))
      [:ok {field default}])))

(defn- step-t [element _acc]
  (if-let [e (asn1/find-context element 4)]
    (let [result (utctime/decode (asn1/->ints (:asn1/content e)))]
      (if (= :error (first result)) result [:ok {:t (second result)}]))
    [:error :iec61850.goose/missing-field {:field :t}]))

(defn- step-alldata [element acc]
  (if-let [e (asn1/find-context element 11)]
    (let [decoded (mapv data/decode-data (:asn1/elements e))
          bad (first (filter #(= :error (first %)) decoded))]
      (if bad
        bad
        (let [alldata (mapv second decoded)
              declared (:numDatSetEntries acc)]
          (if (not= declared (count alldata))
            [:error :iec61850.goose/numdatasetentries-mismatch
             {:declared declared :actual (count alldata)}]
            [:ok {:allData alldata}]))))
    [:error :iec61850.goose/missing-field {:field :allData}]))

(def ^:private steps
  [(step-string 0 :gocbRef)
   (step-int 1 :timeAllowedToLive)
   (step-string 2 :datSet)
   (step-optional-string 3 :goID)
   step-t
   (step-int 5 :stNum)
   (step-int 6 :sqNum)
   (step-bool 7 :simulation false)
   (step-int 8 :confRev)
   (step-bool 9 :ndsCom false)
   (step-int 10 :numDatSetEntries)
   step-alldata])

(defn decode
  "APDU octets (i.e. `(:apdu (appdu/decode frame))`, NOT a whole Ethernet
  frame) -> `[:ok goosePdu-map]` or `[:error kw data]`. Never throws:
  malformed BER from `asn1.core` is caught and reported as
  `:iec61850.goose/malformed-ber` with the underlying `asn1.core` error type
  attached, and every other failure mode has its own keyword."
  [apdu]
  (let [decoded (try [:ok (asn1/decode apdu)]
                      (catch #?(:clj Exception :cljs :default) e
                        [:error :iec61850.goose/malformed-ber
                         {:asn1-error (:type (ex-data e)) :message (ex-message e)}]))]
    (if (= :error (first decoded))
      decoded
      (let [element (second decoded)]
        (if-not (and (= :application (:asn1/class element))
                     (= application-tag (:asn1/tag element)))
          [:error :iec61850.goose/bad-pdu-tag
           {:class (:asn1/class element) :tag (:asn1/tag element)}]
          (reduce (fn [acc step]
                    (if (= :error (first acc))
                      (reduced acc)
                      (let [r (step element (second acc))]
                        (if (= :error (first r))
                          (reduced r)
                          [:ok (merge (second acc) (second r))]))))
                  [:ok {}]
                  steps))))))

;; ── stNum/sqNum retransmission semantics (pure predicates) ────────────────────
;;
;; IEC 61850-8-1's GOOSE publisher state machine, in the form every open
;; implementation agrees on regardless of the exact clause number: `stNum`
;; counts DATA CHANGE events and `sqNum` counts RETRANSMISSIONS of the
;; current (unchanged) state, reset to 0 every time `stNum` moves. A
;; subscriber uses this to tell "the data changed" from "the publisher is
;; just repeating itself to prove it is alive" without inspecting the
;; payload at all — which is the entire point of carrying two counters
;; instead of one.

(def ^:private uint32-mod (bit-shift-left 1 32))

(defn next-stnum
  "`stNum` after a data change: increments mod 2^32 (`stNum` wraps rather
  than growing unboundedly, since it is a fixed 32-bit-range wire INTEGER
  in practice even though this codec's `asn1/integer` does not itself
  enforce a width)."
  [stnum]
  (mod (inc stnum) uint32-mod))

(defn next-sqnum
  "`sqNum` after a retransmission of unchanged state: increments mod 2^32."
  [sqnum]
  (mod (inc sqnum) uint32-mod))

(defn data-change?
  "True when `next` is exactly the retransmission-state successor of `prev`
  representing a DATA CHANGE: `stNum` advances by one (mod 2^32) and `sqNum`
  resets to 0. This is a predicate over the four numbers, not over payloads
  — whether the data actually differs is the publisher's business; this
  only checks that the counters tell the story a data change is supposed
  to tell."
  [{prev-st :stNum} {next-st :stNum next-sq :sqNum}]
  (and (= next-st (next-stnum prev-st)) (zero? next-sq)))

(defn retransmission?
  "True when `next` is exactly the retransmission-state successor of `prev`
  representing a RETRANSMISSION of unchanged state: `stNum` unchanged,
  `sqNum` advances by one (mod 2^32)."
  [{prev-st :stNum prev-sq :sqNum} {next-st :stNum next-sq :sqNum}]
  (and (= next-st prev-st) (= next-sq (next-sqnum prev-sq))))

(defn restart?
  "A heuristic third case neither of the above two admits: `stNum` moves to
  a value other than its own successor while `sqNum` resets to 0 — the
  shape produced by a publisher restarting (stNum typically resets to 1)
  rather than by ordinary operation. Not part of the wire protocol itself,
  offered because a subscriber has to do *something* with a transition
  that is neither a clean data change nor a clean retransmission, and
  silently accepting it as a data change would hide a device restart."
  [{prev-st :stNum} {next-st :stNum next-sq :sqNum}]
  (and (not= next-st (next-stnum prev-st)) (not= next-st prev-st) (zero? next-sq)))

(defn classify-transition
  "`:data-change`, `:retransmission`, `:restart`, or `:invalid` (a
  transition matching none of the above — e.g. `sqNum` advancing without
  `stNum` changing in a way that is not a clean +1, or `stNum` changing
  while `sqNum` is nonzero). A subscriber that gets `:invalid` has grounds
  to distrust the publisher or suspect a lost/reordered frame; this
  function does not decide what to do about that, only names the shape."
  [prev next]
  (cond
    (data-change? prev next) :data-change
    (retransmission? prev next) :retransmission
    (restart? prev next) :restart
    :else :invalid))

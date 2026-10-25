(ns iso-8583.mti
  "The Message Type Indicator: four decimal digits, each digit its own
  independent axis rather than a single opaque code --

  digit 1 (version)  0 1987, 1 1993, 2 2003, 8 national use, 9 private use
  digit 2 (class)    1 authorization, 2 financial, 3 file actions,
                     4 reversal/chargeback, 5 reconciliation,
                     6 administrative, 7 fee collection,
                     8 network management, 9 reserved
  digit 3 (function) 0 request, 1 request response, 2 advice,
                     3 advice response, 4 notification,
                     5..7 reserved for ISO use, 8..9 reserved for private use
  digit 4 (origin)   0 acquirer, 1 acquirer repeat, 2 issuer,
                     3 issuer repeat, 4 other, 5 other repeat,
                     6..9 reserved

  Transcribed from the widely published ISO 8583 MTI digit tables (e.g.
  the message-type breakdowns reproduced across processor/switch
  integration guides); this module decomposes and recomposes the code,
  it does not validate that a given class/function/origin combination is
  legal for a specific network -- that is a conformance profile's job."
  (:require [iso-8583.charcode :as cc]))

(def versions
  {"0" :1987 "1" :1993 "2" :2003 "8" :national-use "9" :private-use})

(def classes
  {"1" :authorization "2" :financial "3" :file-actions "4" :reversal-or-chargeback
   "5" :reconciliation "6" :administrative "7" :fee-collection
   "8" :network-management "9" :reserved})

(def functions
  {"0" :request "1" :request-response "2" :advice "3" :advice-response
   "4" :notification "5" :reserved "6" :reserved "7" :reserved
   "8" :reserved-private "9" :reserved-private})

(def origins
  {"0" :acquirer "1" :acquirer-repeat "2" :issuer "3" :issuer-repeat
   "4" :other "5" :other-repeat "6" :reserved "7" :reserved
   "8" :reserved "9" :reserved})

(def ^:private code-0 (cc/char-code \0))

(defn valid?
  [mti]
  (and (string? mti) (= 4 (count mti))
       (every? #(<= code-0 (cc/char-code %) (+ code-0 9)) mti)))

(defn decompose
  "`\"0200\"` -> `{:version :1987 :class :financial :function :request
  :origin :acquirer}`. `[:error :iso8583/invalid-mti]` if `mti` is not
  exactly four decimal digits."
  [mti]
  (if-not (valid? mti)
    [:error :iso8583/invalid-mti]
    {:version (get versions (subs mti 0 1))
     :class (get classes (subs mti 1 2))
     :function (get functions (subs mti 2 3))
     :origin (get origins (subs mti 3 4))}))

(defn recompose
  "Inverse of `decompose` for every digit ISO 8583 actually assigns a
  meaning to (version 0/1/2/8/9, class 1-8, function 0-4, origin 0-5).
  The unassigned/reserved digit ranges collapse several digits onto the
  same `:reserved`/`:reserved-private` keyword in `decompose`, so for
  those `recompose` returns *a* valid digit with that meaning, not
  necessarily the original one -- there is no meaning encoded in a
  reserved digit to preserve. `[:error :iso8583/unknown-mti-component]`
  if any key does not name a code this table knows at all."
  [{:keys [version class function origin]}]
  (let [rlookup (fn [m v] (first (first (filter (fn [[_ mv]] (= mv v)) m))))
        d1 (rlookup versions version)
        d2 (rlookup classes class)
        d3 (rlookup functions function)
        d4 (rlookup origins origin)]
    (if (some nil? [d1 d2 d3 d4])
      [:error :iso8583/unknown-mti-component]
      (str d1 d2 d3 d4))))

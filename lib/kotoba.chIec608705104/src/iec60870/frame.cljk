(ns iec60870.frame
  "The two-layer wire assembly this repo's other namespaces exist to make
  unnecessary to hand-roll: an I-format APCI (`iec60870.apci`) wrapping one
  ASDU (`iec60870.asdu`). S- and U-format frames carry no ASDU, so they
  don't need this — `iec60870.apci/encode-s`/`encode-u` are already the
  whole story for those."
  (:require [iec60870.apci :as apci]
            [iec60870.asdu :as asdu]))

(defn encode-i-asdu
  "Encode `asdu-map` (as `iec60870.asdu/encode-asdu` takes it) and wrap it
  in an I-format APCI frame with the given `:send-seq`/`:recv-seq`."
  [seq-nums asdu-map]
  (let [a (asdu/encode-asdu asdu-map)]
    (if (= :error (:status a))
      a
      (apci/encode-i seq-nums (:bytes a)))))

(defn decode-i-frame
  "Decode one full frame from the front of `buf`. Non-I formats (S, U) are
  returned with no `:asdu`; an I-format frame's ASDU is decoded too, and a
  malformed ASDU inside an otherwise-well-formed APCI frame surfaces as
  that ASDU decode's own named error, not a generic parse failure."
  [buf]
  (let [r (apci/decode buf)]
    (if (not= :ok (:status r))
      r
      (let [frame (:frame r)]
        (if (not= :i (:format frame))
          {:status :ok :consumed (:consumed r) :frame frame}
          (let [a (asdu/decode-asdu (:asdu-bytes frame))]
            (if (not= :ok (:status a))
              a
              {:status :ok :consumed (:consumed r)
               :frame (assoc frame :asdu (:asdu a))})))))))

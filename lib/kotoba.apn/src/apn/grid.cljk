(ns apn.grid
  "The ITU-T G.694.1 fixed 50 GHz DWDM frequency grid, anchored at
  193.1 THz. Channels are numbered sequentially 1..channel-count; this is
  an arbitrary linear numbering for modeling purposes, not a claim of
  conformance to any specific operator's channel plan. Pure arithmetic, no
  I/O, no third-party deps — portable .cljc (JVM, ClojureScript, SCI).")

(def anchor-thz
  "Centre frequency of the grid, THz."
  193.1)

(def spacing-ghz
  "Fixed channel spacing, GHz (ITU-T G.694.1 50 GHz grid)."
  50)

(def channel-count
  "Number of channels modeled (a representative C-band DWDM channel count)."
  96)

(defn channels
  "The full ordered vector of channel numbers, 1..channel-count."
  []
  (vec (range 1 (inc channel-count))))

(defn valid-channel?
  [ch]
  (and (integer? ch) (<= 1 ch channel-count)))

(defn channel->frequency-thz
  "The ITU-T grid frequency (THz) of a channel number, centred so that
  channel (channel-count/2) and (channel-count/2 + 1) straddle anchor-thz."
  [ch]
  (let [centre-offset (/ (inc channel-count) 2.0)
        spacing-thz    (/ spacing-ghz 1000.0)]
    (+ anchor-thz (* (- ch centre-offset) spacing-thz))))

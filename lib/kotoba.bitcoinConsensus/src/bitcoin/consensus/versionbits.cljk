(ns bitcoin.consensus.versionbits
  "BIP9 deployment state transitions at retarget-period boundaries.")

(def versionbits-top-bits 0x20000000)
(def versionbits-top-mask 0xe0000000)

(defn signals?
  "Whether a block version signals the deployment bit under BIP9."
  [version bit]
  (and (= versionbits-top-bits
          (bit-and version versionbits-top-mask))
       (not (zero? (bit-and version (bit-shift-left 1 bit))))))

(defn next-state
  "Return a candidate block's deployment state.

  `height` is the candidate height, `parent-state` is the deployment state of
  its parent, and the MTP/signal count describe the completed parent period.
  State transitions occur only when height is a period boundary."
  [{:keys [start-time timeout min-activation-height period threshold]}
   height parent-state parent-mtp signal-count]
  (if (or (zero? height) (not (zero? (mod height period))))
    parent-state
    (case parent-state
      :defined
      (if (>= parent-mtp start-time) :started :defined)

      :started
      (cond
        (>= signal-count threshold) :locked-in
        (>= parent-mtp timeout) :failed
        :else :started)

      :locked-in
      (if (>= height min-activation-height) :active :locked-in)

      :active :active
      :failed :failed
      parent-state)))

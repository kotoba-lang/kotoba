(ns bitcoin.consensus.codec
  "Bounded, canonical Bitcoin wire decoding over byte vectors.")

(defn fail! [type message data]
  (throw (ex-info message (assoc data :type type))))

(defn ensure-available! [bytes offset length]
  (when (or (neg? offset) (neg? length)
            (> (+ offset length) (count bytes)))
    (fail! :bitcoin.consensus/truncated
           "Bitcoin payload is truncated."
           {:offset offset :length length :available (count bytes)})))

(defn read-bytes [bytes offset length]
  (ensure-available! bytes offset length)
  [(subvec bytes offset (+ offset length)) (+ offset length)])

(defn read-uint-le [bytes offset length]
  (let [[value next-offset] (read-bytes bytes offset length)]
    [(reduce (fn [result byte] (+ (* result 256) byte))
             0N (reverse value))
     next-offset]))

(defn uint-le [value length]
  (let [value (if (neg? value)
                (+ value (reduce * 1N (repeat length 256)))
                value)]
   (loop [value value remaining length result []]
    (if (zero? remaining)
      result
      (recur (quot value 256) (dec remaining)
             (conj result (int (mod value 256))))))))

(defn read-compact-size
  "Decode a canonical CompactSize and return [value next-offset]."
  [bytes offset]
  (let [[prefix next-offset] (read-uint-le bytes offset 1)]
    (case prefix
      0xfd (let [[value end] (read-uint-le bytes next-offset 2)]
             (when (< value 0xfd)
               (fail! :bitcoin.consensus/noncanonical-compact-size
                      "CompactSize uses a non-minimal encoding."
                      {:value value}))
             [value end])
      0xfe (let [[value end] (read-uint-le bytes next-offset 4)]
             (when (<= value 0xffff)
               (fail! :bitcoin.consensus/noncanonical-compact-size
                      "CompactSize uses a non-minimal encoding."
                      {:value value}))
             [value end])
      0xff (let [[value end] (read-uint-le bytes next-offset 8)]
             (when (<= value 0xffffffff)
               (fail! :bitcoin.consensus/noncanonical-compact-size
                      "CompactSize uses a non-minimal encoding."
                      {:value value}))
             [value end])
      [prefix next-offset])))

(defn compact-size [value]
  (cond
    (< value 0xfd) [value]
    (<= value 0xffff) (into [0xfd] (uint-le value 2))
    (<= value 0xffffffff) (into [0xfe] (uint-le value 4))
    :else (into [0xff] (uint-le value 8))))

(defn read-var-bytes [bytes offset limit label]
  (let [[length next-offset] (read-compact-size bytes offset)]
    (when (> length limit)
      (fail! :bitcoin.consensus/resource-limit
             (str label " exceeds its resource limit.")
             {:label label :length length :limit limit}))
    (read-bytes bytes next-offset length)))

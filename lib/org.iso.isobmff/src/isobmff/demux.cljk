(ns isobmff.demux
  "MP4 demux: box tree + buffer → per-track samples (packets). Reads the
   stbl sample table (stts/stsz/stsc/stco/co64/stss) to recover each
   sample's absolute offset/size/pts/keyframe flag. Sample bytes are
   referenced via isobmff.blob/content-id — raw bytes never cross a
   language boundary unaccompanied by their CID. stsd (codec config) is
   kept as opaque raw box bytes for verbatim re-emission by isobmff.mux.

   Extracted from kotoba-lang/utsushi (utsushi.demux, ADR-2606272200) as
   part of `org-iso-isobmff`."
  (:require [isobmff.bytes :as b]
            [isobmff.box :as box]
            [isobmff.blob :as blob]))

;; --- read tables from FullBox payloads (payload[0..3]=version+flags) ---

(defn- parse-stts [p]
  (let [n (b/u32 p 4)]
    (loop [i 0, off 8, acc []]
      (if (>= i n) acc
          (recur (inc i) (+ off 8)
                 (into acc (repeat (b/u32 p off) (b/u32 p (+ off 4)))))))))

(defn- parse-stsz [p]
  (let [sample-size  (b/u32 p 4)
        sample-count (b/u32 p 8)]
    (if (pos? sample-size)
      (vec (repeat sample-count sample-size))
      (mapv #(b/u32 p (+ 12 (* 4 %))) (range sample-count)))))

(defn- parse-stco [p]
  (let [n (b/u32 p 4)] (mapv #(b/u32 p (+ 8 (* 4 %))) (range n))))

(defn- parse-co64 [p]
  (let [n (b/u32 p 4)] (mapv #(b/u64 p (+ 8 (* 8 %))) (range n))))

(defn- parse-stsc
  "Expand stsc into samples-per-chunk for each chunk (1-based)."
  [p num-chunks]
  (let [n (b/u32 p 4)
        entries (mapv #(let [o (+ 8 (* 12 %))]
                         {:first (b/u32 p o) :spc (b/u32 p (+ o 4))})
                      (range n))]
    (mapv (fn [chunk] (:spc (last (filter #(<= (:first %) chunk) entries))))
          (range 1 (inc num-chunks)))))

(defn- parse-stss [p]
  (let [n (b/u32 p 4)] (set (map #(b/u32 p (+ 8 (* 4 %))) (range n)))))

(defn- build-samples
  "Assemble the sample list from chunk-offsets/spc/sizes/deltas/sync. Samples
   within a chunk are laid out contiguously. sync=nil means 'every sample is
   a keyframe' (no stss box)."
  [{:keys [chunk-offsets spc sizes deltas sync]}]
  (loop [chunks (map vector chunk-offsets spc), si 0, pts 0, acc []]
    (if (empty? chunks)
      acc
      (let [[off n] (first chunks)
            [acc* si* pts* _]
            (reduce (fn [[a i p o] _]
                      (let [sz (nth sizes i)
                            d  (nth deltas i)]
                        [(conj a {:idx i :offset o :size sz :pts p :duration d
                                  :keyframe (or (nil? sync) (contains? sync (inc i)))})
                         (inc i) (+ p d) (+ o sz)]))
                    [acc si pts off]
                    (range n))]
        (recur (rest chunks) si* pts* acc*)))))

(defn- trak->track [buf trak]
  (let [tk   [trak]
        lp   #(box/leaf-payload buf %)
        tkhd (box/find-box tk "tkhd")
        mdhd (box/find-box tk "mdhd")
        hdlr (box/find-box tk "hdlr")
        stsd (box/find-box tk "stsd")
        stts (box/find-box tk "stts")
        stsz (box/find-box tk "stsz")
        stsc (box/find-box tk "stsc")
        stco (box/find-box tk "stco")
        co64 (box/find-box tk "co64")
        stss (box/find-box tk "stss")
        offsets (if stco (parse-stco (lp stco)) (parse-co64 (lp co64)))
        spc     (parse-stsc (lp stsc) (count offsets))
        sizes   (parse-stsz (lp stsz))
        deltas  (parse-stts (lp stts))
        sync    (when stss (parse-stss (lp stss)))
        samples (->> (build-samples {:chunk-offsets offsets :spc spc
                                     :sizes sizes :deltas deltas :sync sync})
                     (mapv (fn [s]
                             (let [bytes (subvec buf (:offset s) (+ (:offset s) (:size s)))]
                               (assoc s :bytes bytes :cid (blob/content-id bytes))))))]
    {:track-id  (b/u32 (lp tkhd) 12)
     :handler   (b/ascii4 (lp hdlr) 8)
     :timescale (b/u32 (lp mdhd) 12)
     :stsd      (subvec buf (:start stsd) (+ (:start stsd) (:size stsd)))
     :samples   samples}))

(defn demux
  "MP4 byte vector → {:timescale :tracks [track...]}. Each track is
   {:track-id :handler :timescale :stsd(raw bytes) :samples [{:idx :offset
   :size :pts :duration :keyframe :bytes :cid}...]}."
  [buf]
  (let [buf   (vec buf)
        boxes (box/parse-boxes buf)
        moov  (box/find-box boxes "moov")
        traks (filter #(= "trak" (:type %)) (:children moov))
        tracks (mapv #(trak->track buf %) traks)]
    {:timescale (:timescale (first tracks))
     :tracks    tracks}))

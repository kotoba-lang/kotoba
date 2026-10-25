(ns kotoba.live.setlist
  "Setlist — the show's table of contents.

  A setlist owns N tracks laid end to end on the show timeline. Each track
  carries its own BPM and optional cue points (`:drop` / `:breakdown` /
  `:callout` / `:custom`) that other modules subscribe to.")

(def cue-kinds #{:drop :breakdown :callout :custom})

(defn track
  "Construct a track. `cues` is a seq of `{:at-beat n :kind k :tag s}`,
  auto-sorted by `:at-beat`. `:audio` is an optional `AudioPattern` map
  (see `kotoba.live.audio`)."
  [{:keys [id title bpm length-beats cues dance audio]}]
  {:id id
   :title title
   :bpm bpm
   :length-beats length-beats
   :cues (vec (sort-by :at-beat (or cues [])))
   :dance dance
   :audio audio})

(defn duration-seconds
  "Length of `trk` in seconds at its own BPM."
  [trk]
  (* (:length-beats trk) (/ 60.0 (:bpm trk))))

(defn new-setlist [] {:tracks []})

(defn push
  "Append `trk` (cues re-sorted) to `setlist`."
  [setlist trk]
  (update setlist :tracks conj (track trk)))

(defn locate
  "Locate the track containing show-time `t` seconds. Returns
  `[index track-local-seconds]`, or `nil` if `t` is past the end."
  [{:keys [tracks]} t]
  (loop [i 0 acc 0.0]
    (if (>= i (count tracks))
      nil
      (let [trk (nth tracks i)
            d (duration-seconds trk)]
        (if (< t (+ acc d))
          [i (- t acc)]
          (recur (inc i) (+ acc d)))))))

(defn total-duration-seconds
  "Total show length in seconds."
  [{:keys [tracks]}]
  (reduce + 0.0 (map duration-seconds tracks)))

(defn cues-between
  "Cues on `track-idx` with `:at-beat` in `(prev-beat, cur-beat]`."
  [{:keys [tracks]} track-idx prev-beat cur-beat]
  (filterv #(and (> (:at-beat %) prev-beat) (<= (:at-beat %) cur-beat))
           (:cues (nth tracks track-idx))))

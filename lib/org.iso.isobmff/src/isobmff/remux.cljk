(ns isobmff.remux
  "Re-encode-free edits (trim / concat). Transforms the demux structure and
   re-muxes with isobmff.mux; never touches codec bytes.

   Extracted from kotoba-lang/utsushi (utsushi.remux, ADR-2606272200) as
   part of `org-iso-isobmff`."
  (:require [isobmff.mux :as mux]))

(defn- track-duration [track]
  (reduce + 0 (map :duration (:samples track))))

(defn trim
  "Restrict each track's samples to pts ∈ [pts-start, pts-end) — re-encode
   free, pure sample selection. R0 does not round to keyframe boundaries.
   pts values are demux-derived absolutes."
  [demuxed pts-start pts-end]
  (update demuxed :tracks
          (fn [tracks]
            (mapv (fn [t]
                    (update t :samples
                            (fn [ss]
                              (vec (filter #(and (>= (:pts %) pts-start)
                                                 (< (:pts %) pts-end))
                                           ss)))))
                  tracks))))

(defn concat-streams
  "Concatenate two demux structures track-by-track (same track order,
   compatible stsd assumed, R0). Shifts the second stream's pts values by
   the first track's total duration."
  [a b]
  (assoc a :tracks
         (mapv (fn [ta tb]
                 (let [dur (track-duration ta)
                       shifted (mapv #(update % :pts + dur) (:samples tb))]
                   (update ta :samples into shifted)))
               (:tracks a) (:tracks b))))

(defn remux
  "Write a demux structure (as-is, or after trim/concat) back to an MP4
   byte vector — a thin alias."
  [demuxed]
  (mux/mux demuxed))

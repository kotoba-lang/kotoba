(ns kami.ongaku.notation
  "Portable score/notation IR: part -> measure -> note (pitch(es)/rest),
  with time signature, key signature, tempo, dynamics and articulation.

  v0 scope, per ADR-2607121400 (kami-ongaku-notation is the L3-authoring
  data model in the `ongaku` domain, analogous to Sibelius/Dorico/
  MuseScore's internal score model): pure data model + structural
  validation + MusicXML-subset I/O (kami.ongaku.notation.musicxml). No
  playback/audio rendering (that's `kotoba-lang/audio`'s L2 concern) and
  no visual layout/engraving.

  Portable .cljc across JVM / ClojureScript."
  (:require [kami.ongaku.notation.pitch :as pitch]
            [kami.ongaku.notation.duration :as duration]
            [kami.ongaku.notation.rational :as r]))

(def dynamics-marks [:ppp :pp :p :mp :mf :f :ff :fff])
(def dynamic->velocity {:ppp 16 :pp 33 :p 49 :mp 64 :mf 80 :f 96 :ff 112 :fff 127})
(defn valid-dynamic? [d] (contains? (set dynamics-marks) d))

(def articulation-marks #{:staccato :legato :accent :tenuto :marcato})
(defn valid-articulations? [as] (and (set? as) (every? articulation-marks as)))

(def tie-states #{:start :stop})

(defn note
  "Construct a note/rest event. `pitches` is a vector of 1+ pitch maps for
  a (possibly multi-pitch = chord) note, or nil/empty for a rest. `type`/
  `dots` follow kami.ongaku.notation.duration. `voice` defaults to 1.
  Returns nil when any field is invalid."
  [{:keys [pitches type dots voice tie dynamic articulations]
    :or {dots 0 voice 1 articulations #{}}}]
  (when (and (duration/valid-type? type)
             (duration/valid-dots? dots)
             (pos-int? voice)
             (or (nil? tie) (contains? tie-states tie))
             (or (nil? dynamic) (valid-dynamic? dynamic))
             (valid-articulations? articulations)
             (or (nil? pitches) (empty? pitches)
                 (every? some? (map pitch/coerce pitches))))
    (cond-> {:note/type type
             :note/dots dots
             :note/voice voice
             :note/rest? (or (nil? pitches) (empty? pitches))
             :note/articulations articulations}
      (seq pitches) (assoc :note/pitches (mapv pitch/coerce pitches))
      tie            (assoc :note/tie tie)
      dynamic        (assoc :note/dynamic dynamic))))

(defn duration-value
  [n]
  (duration/duration-value {:type (:note/type n) :dots (:note/dots n)}))

(defn time-signature
  [{:keys [beats beat-type]}]
  (when (and (pos-int? beats) (contains? #{1 2 4 8 16 32} beat-type))
    {:time-sig/beats beats :time-sig/beat-type beat-type}))

(defn time-signature-capacity
  "Whole-note-fraction capacity of one measure in this time signature, as
  an exact kami.ongaku.notation.rational."
  [{:time-sig/keys [beats beat-type]}]
  (r/mul (r/int->rational beats) (r/make 1 beat-type)))

(def key-modes #{:major :minor})

(defn key-signature
  [{:keys [fifths mode] :or {mode :major}}]
  (when (and (integer? fifths) (<= -7 fifths 7) (contains? key-modes mode))
    {:key-sig/fifths fifths :key-sig/mode mode}))

(def ^:private tempo-beat-units (set (vals duration/base-values)))

(defn tempo
  [{:keys [bpm beat-unit] :or {beat-unit (duration/base-values :quarter)}}]
  (when (and (number? bpm) (pos? bpm) (contains? tempo-beat-units beat-unit))
    {:tempo/bpm bpm :tempo/beat-unit beat-unit}))

(defn measure
  [{:keys [number time-sig key-sig notes] tempo-spec :tempo}]
  (when (and (pos-int? number)
             (or (nil? time-sig) (some? (time-signature time-sig)))
             (or (nil? key-sig) (some? (key-signature key-sig)))
             (or (nil? tempo-spec) (some? (tempo tempo-spec)))
             (vector? notes) (every? some? notes))
    (cond-> {:measure/number number :measure/notes notes}
      time-sig   (assoc :measure/time-signature (time-signature time-sig))
      key-sig    (assoc :measure/key-signature (key-signature key-sig))
      tempo-spec (assoc :measure/tempo (tempo tempo-spec)))))

(defn part
  [{:keys [id name measures]}]
  (when (and (string? id) (seq id) (string? name) (vector? measures) (every? some? measures))
    {:part/id id :part/name name :part/measures measures}))

(defn score
  [{:keys [parts]}]
  (when (and (vector? parts) (seq parts) (every? some? parts))
    {:score/parts parts}))

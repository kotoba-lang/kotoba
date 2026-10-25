(ns kotoba.live.show
  "`LiveShow` — top-level façade that ties every subsystem together.

  ```clojure
  (require '[kotoba.live.show :as show])
  (-> (show/builder) (show/bpm 128.0) (show/stage-preset :hall) (show/build))
  ```

  A show is a plain map; [[tick]] and [[snapshot]] are pure functions that
  return `[show' ...]` — the functional analogue of the original mutable
  `LiveShow::tick` / `LiveShow::snapshot`."
  (:require [kotoba.live.audio :as audio]
            [kotoba.live.beat :as beat]
            [kotoba.live.cheer :as cheer]
            [kotoba.live.crowd :as crowd]
            [kotoba.live.lighting :as lighting]
            [kotoba.live.performer :as performer]
            [kotoba.live.setlist :as setlist]
            [kotoba.live.stage :as stage]
            [kotoba.live.vj :as vj]))

;; ── builder ──────────────────────────────────────────────────────────────

(defn builder []
  {:bpm 128.0 :stage-preset :hall :crowd-cfg (crowd/default-config)
   :performer-name "Mitama" :vj-deck nil :swing 0.0 :beats-per-bar 4 :bars-per-phrase 8})

(defn bpm [b v] (assoc b :bpm v))
(defn stage-preset [b p] (assoc b :stage-preset p))
(defn crowd-cfg [b c] (assoc b :crowd-cfg c))
(defn performer-name [b n] (assoc b :performer-name n))
(defn vj-deck [b d] (assoc b :vj-deck d))
(defn swing [b s] (assoc b :swing s))
(defn meter [b beats-per-bar bars-per-phrase]
  (assoc b :beats-per-bar (max 1 beats-per-bar) :bars-per-phrase (max 1 bars-per-phrase)))

(defn build
  "Build a `LiveShow` from a builder map."
  [b]
  (let [st (stage/build-preset (:stage-preset b))
        perf-home (get-in st [:zones :performer :centre] [0.0 1.0 0.0])
        perf (performer/new-performer (:performer-name b) perf-home)
        cr (crowd/new-crowd (:crowd-cfg b) st)
        deck (or (:vj-deck b) (vj/default-program))]
    {:grid (beat/new-grid (:bpm b) :beats-per-bar (:beats-per-bar b)
                           :bars-per-phrase (:bars-per-phrase b) :swing (:swing b))
     :setlist (setlist/new-setlist)
     :stage st
     :performer perf
     :lighting (lighting/new-designer)
     :vj deck
     :crowd cr
     :cheers (cheer/new-aggregate 2.0)
     :last-cue-beat []
     :last-bass-beat []
     :last-track nil
     :started false
     :muted false}))

;; ── accessors / mutators (pure — return an updated show) ────────────────────

(defn setlist-push [show trk] (update show :setlist setlist/push trk))
(defn lighting-push [show cue at-bar] (update show :lighting lighting/push cue at-bar))
(defn set-performer-move [show move] (update show :performer performer/set-move move))

(defn start
  "Mark the show started and (re)initialize per-track cue/bass cursors."
  [show]
  (let [n (count (get-in show [:setlist :tracks]))]
    (assoc show :started true
           :last-cue-beat (vec (repeat n 0))
           :last-bass-beat (vec (repeat n 0))
           :last-track nil)))

;; ── tick ─────────────────────────────────────────────────────────────────

(defn- track-start-seconds [setlist idx]
  (reduce + 0.0 (map setlist/duration-seconds (take idx (:tracks setlist)))))

(defn- emit-audio-for-event [show track-idx pat ev out]
  (case (:type ev)
    :eighth (if-let [d (:drums pat)]
              (let [step (mod (:eighth-index ev) 8)]
                (reduce (fn [o [slot vel]]
                          (conj o {:type :audio :cue {:type :drum :at-time (:time ev) :slot slot :velocity vel}}))
                        out (audio/hits-at d step)))
              out)
    :beat (let [ts (track-start-seconds (:setlist show) track-idx)
                local-t (- (:time ev) ts)]
            (if (neg? local-t)
              out
              (let [trk (nth (get-in show [:setlist :tracks]) track-idx)
                    local-beat (long (* local-t (/ (:bpm trk) 60.0)))
                    prev (nth (:last-bass-beat show) track-idx)
                    out (if-let [b (:bass pat)]
                          (reduce (fn [o note]
                                    (conj o {:type :audio
                                             :cue {:type :note :at-time (:time ev) :midi (:pitch-midi note)
                                                   :velocity (:velocity note) :duration-beats (:length-beats note)}}))
                                  out (audio/notes-between b prev local-beat))
                          out)
                    out (if (seq (:lead-arp pat))
                          (let [lead-idx (mod (:beat-index ev) (count (:lead-arp pat)))]
                            (conj out {:type :audio
                                       :cue {:type :note :at-time (:time ev) :midi (nth (:lead-arp pat) lead-idx)
                                             :velocity 0.5 :duration-beats 0.45}}))
                          out)]
                {:out out :local-beat local-beat})))
    out))

(defn- handle-cue [show cue]
  (case (:kind cue)
    :drop (let [pit (stage/zone (:stage show) :pit)]
            (-> show
                (update :crowd crowd/set-mood-all :jump)
                (update :crowd crowd/react :jump (fn [p] (boolean (and pit (stage/box-contains? pit p)))))))
    :breakdown (update show :crowd crowd/set-mood-all :sway)
    :callout (update show :crowd crowd/set-mood-all :hush)
    show))

(defn tick
  "Advance the show by `dt` seconds. Returns `[show' events]`."
  [show dt]
  (if-not (:started show)
    [show []]
    (let [[grid' drained] (beat/tick (:grid show) dt)
          phase (beat/phase grid')
          active-idx (first (setlist/locate (:setlist show) (:time phase)))
          ;; 1) beat-grid events -> lighting + audio
          [show events]
          (reduce
           (fn [[sh evs] ev]
             (let [sh (update sh :lighting lighting/on-event ev)
                   evs (conj evs {:type :beat :beat ev})
                   pat (when active-idx (get-in sh [:setlist :tracks active-idx :audio]))]
               (if pat
                 (let [r (emit-audio-for-event sh active-idx pat ev [])]
                   (if (map? r)
                     [(assoc-in sh [:last-bass-beat active-idx] (:local-beat r))
                      (into evs (:out r))]
                     [sh (into evs r)]))
                 [sh evs])))
           [(assoc show :grid grid') []]
           drained)
          now (:time phase)
          loc (setlist/locate (:setlist show) now)]
      (if loc
        (let [[idx _local-seconds] loc
              trk (nth (get-in show [:setlist :tracks]) idx)
              track-changed? (not= (:last-track show) idx)
              [show events]
              (if track-changed?
                (let [show (cond-> show (:dance trk) (set-performer-move (:dance trk)))
                      show (assoc show :last-track idx)
                      events (conj events {:type :track-changed :index idx :title (:title trk) :bpm (:bpm trk)})
                      pat (:audio trk)
                      events (if pat
                               (conj events {:type :audio
                                             :cue {:type :pad :at-time now
                                                   :midis (vec (take 5 (:pad-chord pat)))}})
                               (conj events {:type :audio :cue {:type :stop :at-time now}}))]
                  [show events])
                [show events])
              ts (track-start-seconds (:setlist show) idx)
              local-t (- now ts)
              local-beat (long (max 0.0 (* local-t (/ (:bpm trk) 60.0))))
              prev-local-beat (nth (:last-cue-beat show) idx)
              cues (setlist/cues-between (:setlist show) idx prev-local-beat local-beat)
              [show events] (reduce (fn [[sh evs] cue]
                                       [(handle-cue sh cue) (conj evs {:type :cue :track-index idx :cue cue})])
                                     [show events] cues)
              show (assoc-in show [:last-cue-beat idx] local-beat)
              show (update show :lighting lighting/prune (:bar phase))
              show (update show :cheers cheer/evict now)]
          [show events])
        (if (some? (:last-track show))
          (let [events (conj events {:type :audio :cue {:type :stop :at-time now}} {:type :set-ended})
                show (assoc show :last-track nil)
                show (update show :lighting lighting/prune (:bar phase))
                show (update show :cheers cheer/evict now)]
            [show events])
          (let [show (update show :lighting lighting/prune (:bar phase))
                show (update show :cheers cheer/evict now)]
            [show events]))))))

;; ── snapshot ─────────────────────────────────────────────────────────────

(defn snapshot
  "Build the per-frame snapshot. Returns `[show' snapshot]` (crowd
  energy/VJ ease advance)."
  [show]
  (let [phase (beat/phase (:grid show))
        pose (performer/pose (:performer show) (:beat-frac phase) (:bar-frac phase))
        lit (lighting/resolve-frames (:lighting show) phase)
        loud (cheer/loudness (:cheers show))
        target (max 0.4 (min 1.0 (* loud 0.05)))
        [deck' vjf] (vj/frame (:vj show) phase target)
        [crowd' fans] (crowd/snapshot (:crowd show) phase)]
    [(assoc show :vj deck' :crowd crowd')
     {:phase phase :current-track (:last-track show) :performer-pose pose
      :lighting lit :vj vjf :crowd fans :cheer-loudness loud}]))

(defn ingest-cheer
  "Ingest a cheer of `kind`/`weight` at the show's current time."
  [show kind weight]
  (let [now (:time (beat/phase (:grid show)))
        show (update show :cheers cheer/push {:at now :kind kind :weight (max 0.0 weight)})
        pit (stage/zone (:stage show) :pit)]
    (update show :crowd crowd/react kind (fn [p] (boolean (and pit (stage/box-contains? pit p)))))))

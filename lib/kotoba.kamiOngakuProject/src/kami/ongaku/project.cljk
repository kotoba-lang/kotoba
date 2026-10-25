(ns kami.ongaku.project
  "Portable DAW-session data model: tracks, buses (a real bus graph, not a
  flat list), tick-placed clips, parameter automation, and a tick-keyed
  tempo map. The L3 SSoT of the `ongaku` domain per ADR-2607121400 — this
  is the layer that actually ties `kami.ongaku.notation` (score IR) and
  `kami.ongaku.sequencer` (MIDI-equivalent event IR) into one session, the
  way a Logic Pro/Cubase/Ableton project file does.

  v0 scope: pure session/graph data model + referential-integrity
  validation. No audio rendering, no plugin execution (plugin instances
  are opaque refs here; the plugin *contract* itself is
  `kami-ongaku-plugin-host`'s job, Wave 3 of ADR-2607121400).

  Portable .cljc across JVM / ClojureScript. Ticks are plain integers at
  :project/ppq resolution, matching kami.ongaku.sequencer's convention —
  no float/ratio time arithmetic here."
  (:require [kotoba.lang.text :as str]))

(def default-ppq
  "Ticks per quarter note. Matches kami.ongaku.sequencer/default-ppq."
  480)

(def default-sample-rate 48000)

;; ---------------------------------------------------------------------------
;; constructors — structural shape only. Cross-referential integrity
;; (dangling ids, bus-graph cycles, clip/track type mismatches) is
;; validate-project's job below, since it needs the whole Project to check.

(defn plugin-ref
  [{:keys [id bypass? wet-dry] :or {bypass? false wet-dry 1.0}}]
  (when (and (string? id) (seq id) (number? wet-dry) (<= 0.0 wet-dry 1.0))
    {:plugin-ref/id id :plugin-ref/bypass? (boolean bypass?) :plugin-ref/wet-dry wet-dry}))

(def track-types #{:midi :audio :notation})

(defn track
  [{:keys [id type name color mute? solo? armed? output-bus]
    :or {mute? false solo? false armed? false}}]
  (when (and (string? id) (seq id)
             (contains? track-types type)
             (string? name) (seq name)
             (or (nil? color) (string? color))
             (or (nil? output-bus) (string? output-bus)))
    (cond-> {:track/id id :track/type type :track/name name
             :track/mute? (boolean mute?) :track/solo? (boolean solo?) :track/armed? (boolean armed?)}
      color       (assoc :track/color color)
      output-bus  (assoc :track/output-bus output-bus))))

(defn bus
  "`gain` is the bus's own linear gain multiplier (default 1.0), applied to
  the SUM of this bus's :inputs (tracks and/or other buses) at render time —
  see kami-ongaku-project's README, 'Real bus-graph mixing proof'. This
  constructor only validates the shape; it does not itself mix anything."
  [{:keys [id name inputs plugin-chain gain] :or {inputs #{} plugin-chain [] gain 1.0}}]
  (when (and (string? id) (seq id)
             (string? name) (seq name)
             (set? inputs) (every? string? inputs)
             (vector? plugin-chain) (every? some? plugin-chain)
             (number? gain) (>= gain 0.0))
    {:bus/id id :bus/name name :bus/inputs inputs :bus/plugin-chain plugin-chain :bus/gain gain}))

(def clip-content-shape-ok?
  "Cheap structural (not deep-validity) shape check per track type, used by
  both `clip-placement` and `validate-project`."
  {:midi     (fn [c] (and (map? c) (vector? (:events c)) (pos-int? (:length-ticks c))))
   :notation (fn [c] (and (map? c) (vector? (:part/measures c))))
   :audio    (fn [c] (and (map? c) (string? (:audio/uri c)) (seq (:audio/uri c))))})

(defn clip-placement
  [{:keys [id track-id start-tick length-ticks content]}]
  (when (and (string? id) (seq id)
             (string? track-id) (seq track-id)
             (nat-int? start-tick)
             (pos-int? length-ticks)
             (map? content))
    {:clip/id id :clip/track-id track-id
     :clip/start-tick start-tick :clip/length-ticks length-ticks
     :clip/content content}))

(def interp-modes #{:linear :hold :curve})

(defn automation-point
  [{:keys [tick value interp] :or {interp :linear}}]
  (when (and (nat-int? tick) (number? value) (contains? interp-modes interp))
    {:point/tick tick :point/value value :point/interp interp}))

(defn automation-lane
  [{:keys [id target-id param points]}]
  (when (and (string? id) (seq id)
             (string? target-id) (seq target-id)
             (keyword? param)
             (vector? points) (seq points) (every? some? points))
    {:lane/id id :lane/target-id target-id :lane/param param :lane/points points}))

(defn tempo-point
  [{:keys [tick bpm time-sig]}]
  (when (and (nat-int? tick) (number? bpm) (pos? bpm)
             (vector? time-sig) (= 2 (count time-sig))
             (pos-int? (first time-sig)) (contains? #{1 2 4 8 16 32} (second time-sig)))
    {:tempo-point/tick tick :tempo-point/bpm bpm :tempo-point/time-sig time-sig}))

(defn project
  [{:keys [ppq sample-rate tempo-map tracks buses clips automation]
    :or {ppq default-ppq sample-rate default-sample-rate
         buses [] clips [] automation []}}]
  (when (and (pos-int? ppq) (pos-int? sample-rate)
             (vector? tempo-map) (seq tempo-map) (every? some? tempo-map)
             (vector? tracks) (seq tracks) (every? some? tracks)
             (vector? buses) (every? some? buses)
             (vector? clips) (every? some? clips)
             (vector? automation) (every? some? automation))
    {:project/ppq ppq :project/sample-rate sample-rate
     :project/tempo-map tempo-map :project/tracks tracks
     :project/buses buses :project/clips clips :project/automation automation}))

;; ---------------------------------------------------------------------------
;; lookups

(defn track-ids [proj] (set (map :track/id (:project/tracks proj))))
(defn bus-ids [proj] (set (map :bus/id (:project/buses proj))))
(defn node-ids
  "All ids a bus input / automation target / track output-bus may
   legally reference: every track id union every bus id."
  [proj]
  (into (track-ids proj) (bus-ids proj)))

;; ---------------------------------------------------------------------------
;; bus-graph cycle detection

(defn- bus-input-edges
  "Directed edges bus-id -> bus-id, i.e. only the subset of :bus/inputs
   entries that are themselves bus ids (track inputs are graph leaves)."
  [proj]
  (let [bids (bus-ids proj)]
    (into {}
          (map (fn [b] [(:bus/id b) (filterv bids (:bus/inputs b))]))
          (:project/buses proj))))

(defn find-cycle
  "Returns a cycle (vector of bus ids, first == last) if the bus-input
   graph has one, else nil. Depth-first search tracking the current path;
   hitting a node already on the path means a bus receives (directly or
   transitively) from itself — a real signal-flow bug, not just a
   modeling nicety."
  [proj]
  (let [edges (bus-input-edges proj)
        visited (atom #{})]
    (letfn [(dfs [node path]
              (if (some #(= node %) path)
                (conj (vec (drop-while #(not= node %) path)) node)
                (do
                  (swap! visited conj node)
                  (some #(dfs % (conj path node)) (get edges node [])))))]
      (some (fn [node] (when-not (@visited node) (dfs node [])))
            (keys edges)))))

;; ---------------------------------------------------------------------------
;; validate-project — referential integrity + per-track-type content checks.
;; Returns a (possibly empty) vector of error strings, mirroring
;; kami.ongaku.sequencer's validate-* convention.

(defn- dangling-refs [ids referenced-by-fn items label]
  (mapcat (fn [item]
            (let [ref (referenced-by-fn item)]
              (when (and ref (not (contains? ids ref)))
                [(str label " references unknown id: " ref)])))
          items))

(defn- clip-errors [proj]
  (let [by-id (into {} (map (juxt :track/id identity)) (:project/tracks proj))]
    (mapcat
     (fn [c]
       (if-let [trk (get by-id (:clip/track-id c))]
         (let [shape-ok? (get clip-content-shape-ok? (:track/type trk))]
           (when-not (shape-ok? (:clip/content c))
             [(str "clip " (:clip/id c) " content shape does not match track type "
                   (:track/type trk) " (track " (:clip/track-id c) ")")]))
         [(str "clip " (:clip/id c) " references unknown track: " (:clip/track-id c))]))
     (:project/clips proj))))

(defn- automation-errors [proj nids]
  (mapcat
   (fn [lane]
     (cond-> []
       (not (contains? nids (:lane/target-id lane)))
       (conj (str "automation lane " (:lane/id lane) " references unknown target: " (:lane/target-id lane)))

       (not (apply <= (map :point/tick (:lane/points lane))))
       (conj (str "automation lane " (:lane/id lane) " points are not tick-sorted"))))
   (:project/automation proj)))

(defn- tempo-map-errors [proj]
  (let [tm (:project/tempo-map proj)
        ticks (map :tempo-point/tick tm)]
    (cond-> []
      (not (apply <= ticks))
      (conj "tempo-map points are not tick-sorted")

      (not= 0 (:tempo-point/tick (first tm)))
      (conj "tempo-map must start at tick 0"))))

(defn validate-project
  [proj]
  (let [bids (bus-ids proj)
        nids (node-ids proj)]
    (vec
     (concat
      (dangling-refs bids :track/output-bus (:project/tracks proj) "track/output-bus")
      (mapcat (fn [b]
                (keep (fn [in]
                        (when-not (contains? nids in)
                          (str "bus " (:bus/id b) " has input referencing unknown id: " in)))
                      (:bus/inputs b)))
              (:project/buses proj))
      (when-let [cycle (find-cycle proj)]
        [(str "bus graph has a cycle: " (str/join " -> " cycle))])
      (clip-errors proj)
      (automation-errors proj nids)
      (tempo-map-errors proj)))))

(defn valid-project? [proj] (empty? (validate-project proj)))

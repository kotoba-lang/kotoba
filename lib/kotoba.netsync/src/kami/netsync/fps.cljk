(ns kami.netsync.fps
  "Hitscan rewind — Source-style lag compensation as pure EDN.

   Movement still uses `kami.netsync/pred-reconcile` (the shooter predicts their
   own motion). This namespace is the *shot*: the client sends a fire intent
   stamped with the tick it saw; the authority rewinds everyone else to that
   tick and raycasts there. The client never decides a hit.

   Transport is out of scope. T1 WebSocket / T2 WebRTC / T3 P2P all feed the
   same intent. No clock, no sockets, no mutation.")

(def default-policy
  "Forkable. `:history` is the ring length in ticks. `:max-rewind` is how far
   back a fire intent may look — older than that is `:stale`, not a miss.
   `:hit-radius` is the rewinded target's sphere. `:origin-slop` is how far the
   claimed muzzle may sit from the shooter's rewinded position (anti-cheat)."
  {:history 128
   :max-rewind 20
   :hit-radius 0.55
   :origin-slop 2.0})

(defn history-new
  ([] (history-new default-policy))
  ([policy] {:policy policy :ticks {} :latest nil}))

(defn record
  "Store `entities` ({id {:x :y :z :alive?}}) at `tick`. Trimmed to `:history`.
   Later records at the same tick replace. Pure."
  [history tick entities]
  (let [cap (get-in history [:policy :history] 128)
        ticks (assoc (:ticks history) tick entities)
        keep (if (> (count ticks) cap)
               (->> ticks keys sort (take-last cap) set)
               (set (keys ticks)))
        ticks' (into {} (filter (fn [[t _]] (contains? keep t)) ticks))]
    {:policy (:policy history)
     :ticks ticks'
     :latest (if (or (nil? (:latest history)) (> tick (:latest history)))
               tick
               (:latest history))}))

(defn world-at
  "Entities at `tick`, or nil when that tick is not in the ring."
  [history tick]
  (get-in history [:ticks tick]))

(defn fire-intent
  "Wire payload. `origin` and `dir` are 3-vectors. `tick` is the world the
   shooter claims they saw — not wall-clock, not the arrival tick."
  [shooter-id origin dir tick]
  {:fire/shooter shooter-id
   :fire/origin (vec origin)
   :fire/dir (vec dir)
   :fire/tick tick})

(defn- v3 [[x y z]] [(double (or x 0)) (double (or y 0)) (double (or z 0))])

(defn- v-sub [a b] (mapv - a b))
(defn- v-add [a b] (mapv + a b))
(defn- v-scale [a s] (mapv #(* % s) a))
(defn- v-dot [a b] (reduce + 0 (map * a b)))
(defn- v-len2 [a] (v-dot a a))
(defn- v-dist [a b] (Math/sqrt (v-len2 (v-sub a b))))

(defn- normalize [dir]
  (let [d (v3 dir)
        l2 (v-len2 d)]
    (when (pos? l2)
      (v-scale d (/ 1.0 (Math/sqrt l2))))))

(defn- pos-of [entity]
  (v3 [(:x entity) (:y entity) (:z entity)]))

(defn- ray-sphere
  "Smallest t>=0 at which ray (origin, unit dir) hits sphere (center, r), or nil."
  [origin dir center radius]
  (let [oc (v-sub origin center)
        b (* 2.0 (v-dot dir oc))
        c (- (v-len2 oc) (* radius radius))
        disc (- (* b b) (* 4.0 c))]
    (when-not (neg? disc)
      (let [s (Math/sqrt disc)
            t1 (/ (- (- b) s) 2.0)
            t2 (/ (+ (- b) s) 2.0)
            t (cond
                (>= t1 0.0) t1
                (>= t2 0.0) t2
                :else nil)]
        (when t t)))))

(defn- reject [reason extras]
  (merge {:ok false :hit nil :reason reason} extras))

(defn resolve-hitscan
  "Authority-only. Rewind to `:fire/tick`, validate the muzzle, raycast every
   living non-shooter. Returns `{:ok true :hit id :at [x y z] :tick t}` on a
   hit, `{:ok true :hit nil :reason :miss}` on a clean miss, or `{:ok false
   :reason …}` when the intent is refused (not the same as a miss — a refuse
   must not apply damage and must not look like a whiff)."
  [history intent]
  (let [policy (:policy history)
        tick (:fire/tick intent)
        shooter (:fire/shooter intent)
        latest (:latest history)
        max-rewind (:max-rewind policy 20)
        radius (:hit-radius policy 0.55)
        slop (:origin-slop policy 2.0)
        dir (normalize (:fire/dir intent))
        origin (v3 (:fire/origin intent))]
    (cond
      (nil? latest)
      (reject :no-history {:tick tick})

      (nil? dir)
      (reject :zero-dir {:tick tick})

      (not (integer? tick))
      (reject :bad-tick {:tick tick})

      (> tick latest)
      (reject :future {:tick tick :latest latest})

      (> (- latest tick) max-rewind)
      (reject :stale {:tick tick :latest latest :max-rewind max-rewind})

      (nil? (world-at history tick))
      (reject :no-history {:tick tick})

      :else
      (let [world (world-at history tick)
            me (get world shooter)]
        (cond
          (nil? me)
          (reject :unknown-shooter {:tick tick :shooter shooter})

          (false? (:alive? me))
          (reject :dead-shooter {:tick tick :shooter shooter})

          (> (v-dist origin (pos-of me)) slop)
          (reject :bad-origin {:tick tick
                               :claimed origin
                               :rewinded (pos-of me)})

          :else
          (let [hit (->> world
                         (keep (fn [[id e]]
                                 (when (and (not= id shooter)
                                            (not (false? (:alive? e))))
                                   (when-let [t (ray-sphere origin dir (pos-of e) radius)]
                                     {:id id :t t :at (v-add origin (v-scale dir t))}))))
                         (sort-by :t)
                         first)]
            (if hit
              {:ok true :hit (:id hit) :at (:at hit) :tick tick :t (:t hit)}
              {:ok true :hit nil :reason :miss :tick tick})))))))

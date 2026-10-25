(ns dcs.model
  "DCS-as-EDN: a plant/area hierarchy, I/O tags, PID control loops and alarms
  as plain data, in the ISA-95 / ISA-18.2 vocabulary. No I/O, no third-party
  deps — portable .cljc (JVM, ClojureScript, SCI).

  A system is a map keyed by namespaced :dcs/* keys, each collection
  id-keyed for O(1) lookup:

    {:dcs/areas  {\"area-1\" {:dcs/id \"area-1\" :dcs/name \"Reactor\" :dcs/parent nil}}
     :dcs/tags   {\"TIC-101.PV\" {:dcs/id \"TIC-101.PV\" :dcs/kind :ai
                                 :dcs/units :degC :dcs/range [0 500]}}
     :dcs/loops  {\"TIC-101\" {:dcs/id \"TIC-101\" :dcs/pv-tag \"TIC-101.PV\"
                              :dcs/output-tag \"TIC-101.OUT\" :dcs/mode :auto
                              :dcs/setpoint 350.0
                              :dcs/tuning {:kp 2.0 :ki 0.1 :kd 0.0}
                              :dcs/output-limits [0.0 100.0]}}
     :dcs/alarms {\"TIC-101.HI\" {:dcs/id \"TIC-101.HI\" :dcs/tag \"TIC-101.PV\"
                                 :dcs/type :hi :dcs/setpoint 420.0
                                 :dcs/priority :high :dcs/deadband 2.0}}}")

(def tag-kinds
  "Allowed :dcs/kind values for a tag: analog/digital input/output."
  #{:ai :ao :di :do})

(def loop-modes
  "Allowed :dcs/mode values for a control loop."
  #{:auto :manual :cascade})

(def alarm-types
  "Allowed :dcs/type values for an alarm."
  #{:hi :hi-hi :lo :lo-lo :dev})

(def alarm-priorities
  "Allowed :dcs/priority values for an alarm."
  #{:critical :high :low :journal})

;; --- builder (threadable) ---

(defn system
  "A fresh, empty DCS system."
  []
  {:dcs/areas {} :dcs/tags {} :dcs/loops {} :dcs/alarms {}})

(defn area
  "A bare area map (to be attached via `add-area`). opts: {:name :parent}."
  ([id] (area id nil))
  ([id opts]
   (cond-> {:dcs/id id}
     (:name opts)   (assoc :dcs/name (:name opts))
     (:parent opts) (assoc :dcs/parent (:parent opts)))))

(defn add-area
  "Attach `area-map` (built via `area`) into `sys`."
  [sys area-map]
  (assoc-in sys [:dcs/areas (:dcs/id area-map)] area-map))

(defn tag
  "A bare I/O tag map (to be attached via `add-tag`). `kind` is one of
  `tag-kinds`. opts: {:units :range [lo hi] :area :description}."
  ([id kind] (tag id kind nil))
  ([id kind opts]
   (cond-> {:dcs/id id :dcs/kind kind}
     (:units opts)       (assoc :dcs/units (:units opts))
     (:range opts)       (assoc :dcs/range (vec (:range opts)))
     (:area opts)        (assoc :dcs/area (:area opts))
     (:description opts) (assoc :dcs/description (:description opts)))))

(defn add-tag
  "Attach `tag-map` (built via `tag`) into `sys`."
  [sys tag-map]
  (assoc-in sys [:dcs/tags (:dcs/id tag-map)] tag-map))

(defn ctrl-loop
  "A bare control-loop map (to be attached via `add-loop`). opts: {:pv-tag
  :output-tag :mode (one of `loop-modes`, default :manual) :setpoint :tuning
  {:kp :ki :kd} :output-limits [lo hi]}."
  [id opts]
  (cond-> {:dcs/id id :dcs/mode (get opts :mode :manual)}
    (:pv-tag opts)        (assoc :dcs/pv-tag (:pv-tag opts))
    (:output-tag opts)    (assoc :dcs/output-tag (:output-tag opts))
    (:setpoint opts)      (assoc :dcs/setpoint (:setpoint opts))
    (:tuning opts)        (assoc :dcs/tuning (:tuning opts))
    (:output-limits opts) (assoc :dcs/output-limits (vec (:output-limits opts)))))

(defn add-loop
  "Attach `loop-map` (built via `ctrl-loop`) into `sys`."
  [sys loop-map]
  (assoc-in sys [:dcs/loops (:dcs/id loop-map)] loop-map))

(defn alarm
  "A bare alarm map (to be attached via `add-alarm`). opts: {:tag :type (one
  of `alarm-types`) :setpoint :priority (one of `alarm-priorities`, default
  :low) :deadband (default 0.0)}."
  [id opts]
  (cond-> {:dcs/id id
           :dcs/tag (:tag opts)
           :dcs/type (:type opts)
           :dcs/priority (get opts :priority :low)
           :dcs/deadband (get opts :deadband 0.0)}
    (:setpoint opts) (assoc :dcs/setpoint (:setpoint opts))))

(defn add-alarm
  "Attach `alarm-map` (built via `alarm`) into `sys`."
  [sys alarm-map]
  (assoc-in sys [:dcs/alarms (:dcs/id alarm-map)] alarm-map))

;; --- queries ---

(defn areas  [sys] (vals (:dcs/areas sys)))
(defn tags   [sys] (vals (:dcs/tags sys)))
(defn loops  [sys] (vals (:dcs/loops sys)))
(defn alarms [sys] (vals (:dcs/alarms sys)))

(defn area-by-id  [sys id] (get-in sys [:dcs/areas id]))
(defn tag-by-id   [sys id] (get-in sys [:dcs/tags id]))
(defn loop-by-id  [sys id] (get-in sys [:dcs/loops id]))
(defn alarm-by-id [sys id] (get-in sys [:dcs/alarms id]))

(defn alarms-for-tag
  "All alarms configured against `tag-id`."
  [sys tag-id]
  (filter #(= tag-id (:dcs/tag %)) (alarms sys)))

(defn loops-for-tag
  "All loops that read or write `tag-id` (as pv-tag or output-tag)."
  [sys tag-id]
  (filter #(or (= tag-id (:dcs/pv-tag %)) (= tag-id (:dcs/output-tag %))) (loops sys)))

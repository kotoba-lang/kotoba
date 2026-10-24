(ns kotoba.lang.device
  "Device capability interfaces (bluetooth/wifi/display/geolocation/camera/
  motion/audio-io/ble-scan/wifi-info) as EDN + a discover protocol,
  host-injected drivers. The kotoba principle — a component touches only
  what it was granted — applies especially to hardware. device does NOT wrap
  OS APIs; it defines device surfaces as wit capability tokens and a
  discover/describe protocol, so aiueos's :aiueos/device + aiueos:host gate
  can grant/deny each surface. Consumes wit + coll. No third-party deps;
  .cljc (JVM/SCI/CLJS/GraalVM/kotoba-WASM).

  motion/audio-io/ble-scan/wifi-info were added for ADR-2607140600 Phase 3a
  (the indoor floorplan-lab's device-capability bridge). They follow the
  bluetooth/wifi/display/geolocation/camera precedent exactly: this
  namespace stays dependency-free (no `:deps` entry added for this) and
  carries no concrete driver implementation for ANY surface, old or new —
  bluetooth/wifi/display/geolocation/camera have none either, only
  `mock-device` for tests; the actual driver is always assembled by the
  caller and injected via `make-device-manager`'s `drivers` map. For these 4
  surfaces specifically, the intended host-injected driver is
  kotoba-lang/kotoba's `kotoba.sensing-host` (its `read-motion`/
  `play-audio!`/`record-audio`/`scan-ble`/`read-wifi-info` fns, registered
  as kotoba-core-contracts capability ids 234-237) — see
  `sensing-host-driver-refs` below for that wiring as pure EDN data, not a
  code dependency."
  (:require [kotoba.lang.wit :as w]
            [kotoba.lang.coll :as c])
  (:require [kotoba.device.device :as device-p]))

;; ---------- device surfaces (capability tokens) ----------

(def ^:private surface-effects
  "Effects per device surface — what a granted surface lets the component do.
  `array-map` (not a `{}` literal) is deliberate: `discover`'s canonical
  order depends on stable insertion-order iteration, which a plain map
  literal only guarantees up to 8 entries (beyond that Clojure silently
  promotes to a PersistentHashMap with hash-bucket order) — this map has 9
  entries since ADR-2607140600 Phase 3a added motion/audio-io/ble-scan/
  wifi-info."
  (array-map :bluetooth   #{:scan :connect :read :write}
             :wifi        #{:scan :connect :read}
             :display     #{:write}
             :geolocation #{:read}
             :camera      #{:read}
             ;; ADR-2607140600 Phase 3a — read-only, no pairing/GATT-write/raw-scan.
             :motion      #{:read}
             :audio-io    #{:read :write}
             :ble-scan    #{:scan}
             :wifi-info   #{:read}))

(defn- surface->cap [s] (str "device:" (name s)))

(defn surfaces
  "Return the canonical device-surface capability tokens (wit-compatible). Each
  is {:wit/capability \"device:<s>\" :wit/effects #{...}}."
  []
  (for [[s effects] surface-effects]
    {:wit/capability (surface->cap s)
     :wit/effects    effects}))

(defn surface-cap
  "Return the capability string for a device surface keyword (`:bluetooth` etc)."
  [s] (surface->cap s))

;; ---------- surface schemas ----------

(defn- surface-schema
  "Return the method schema for a device surface."
  [s]
  (case s
    :bluetooth   {:methods {:scan     {:params {} :result :seq}
                            :connect  {:params {:id :string} :result :bool}
                            :read     {:params {:handle :string} :result :bytes}
                            :write    {:params {:handle :string :data :bytes} :result :bool}}}
    :wifi        {:methods {:scan    {:params {} :result :seq}
                            :connect {:params {:ssid :string} :result :bool}
                            :read    {:params {:handle :string} :result :bytes}}}
    :display     {:methods {:write {:params {:target :string :data :bytes} :result :bool}}}
    :geolocation {:methods {:read {:params {} :result {:lat :double :lon :double}}}}
    :camera      {:methods {:read {:params {:source :string} :result :bytes}}}
    ;; ADR-2607140600 Phase 3a. :read/:write reuse the generic handle+data
    ;; call() slots (see `call` below) the same way bluetooth/wifi already
    ;; do for methods whose real params don't literally mean "handle" —
    ;; geolocation's :read passes no handle at all for the same reason.
    :motion      {:methods {:read {:params {} :result :seq}}}
    :audio-io    {:methods {:write {:params {:freq-hz :int :duration-ms :int} :result :bool}
                            :read  {:params {:duration-ms :int} :result :seq}}}
    :ble-scan    {:methods {:scan {:params {} :result :seq}}}
    :wifi-info   {:methods {:read {:params {} :result {:signal-dbm :int}}}}
    nil))

(defn describe
  "Return a surface's schema (methods + effects), or nil if unknown."
  [s]
  (when-let [schema (surface-schema s)]
    (c/assoc-some (assoc schema :surface s)
                  :effects (get surface-effects s))))

;; ---------- sensing-host driver wiring (data only, ADR-2607140600 Phase 3a) ----------

(def sensing-host-driver-refs
  "Pure EDN documentation data — NOT a code/`:deps` dependency on
  kotoba-lang/kotoba — pointing each of the 4 ADR-2607140600 Phase 3a
  surfaces at the kotoba-core-contracts capability id + kotoba.sensing-host
  fn a caller should use when assembling that surface's IDevice driver for
  `make-device-manager`'s `drivers` map. kotoba.sensing-host's own fns
  already take an optional DRIVER map and fall back to a deterministic stub
  when none is injected, so wiring an IDevice around them here costs
  nothing even with no native shim present yet. bluetooth/wifi/display/
  geolocation/camera have no entry — they predate the kotoba runtime bridge
  and this repo has never wired any surface to a concrete implementation
  (only `mock-device` exists, for tests)."
  {:motion    {:kotoba-core-contracts/capability-id 234
               :kotoba-core-contracts/capability     "motion/read"
               :kotoba.sensing-host/ns               'kotoba.sensing-host
               :kotoba.sensing-host/read-op          'read-motion}
   :audio-io  {:kotoba-core-contracts/capability-id 235
               :kotoba-core-contracts/capability     "audio/io"
               :kotoba.sensing-host/ns               'kotoba.sensing-host
               :kotoba.sensing-host/write-op         'play-audio!
               :kotoba.sensing-host/read-op          'record-audio}
   :ble-scan  {:kotoba-core-contracts/capability-id 236
               :kotoba-core-contracts/capability     "ble/scan"
               :kotoba.sensing-host/ns               'kotoba.sensing-host
               :kotoba.sensing-host/scan-op          'scan-ble}
   :wifi-info {:kotoba-core-contracts/capability-id 237
               :kotoba-core-contracts/capability     "wifi/info"
               :kotoba.sensing-host/ns               'kotoba.sensing-host
               :kotoba.sensing-host/read-op          'read-wifi-info}})

(defn sensing-host-driver-ref
  "Return `sensing-host-driver-refs`' entry for surface `s`, or nil (e.g. for
  bluetooth/wifi/display/geolocation/camera, which have none)."
  [s]
  (get sensing-host-driver-refs s))

;; ---------- IDevice protocol (host-injected driver) ----------

(def IDevice
  "The protocol itself lives in one repo of its own now. This name is that
  SAME protocol, not a second one: an implementation reified against either
  is accepted by both (ADR-2609091900)."
  device-p/Device)

(def read-dev device-p/read-dev)
(def scan device-p/scan)
(def subscribe device-p/subscribe)
(def write-dev device-p/write-dev)

;; ---------- mock device (tests / OSS standalone) ----------

(defn mock-device
  "An in-memory IDevice for tests. `state` is an atom of {handle value}. scan
  returns the keys; read returns the value; write sets it; subscribe is a no-op
  (records the subscription)."
  ([]
   (mock-device (atom {})))
  ([state]
   (let [subs (atom {})]
     (reify IDevice
       (scan [_] (keys @state))
       (read-dev [_ handle] (get @state handle))
       (write-dev [_ handle data] (swap! state assoc handle data) true)
       (subscribe [_ handle f] (swap! subs update handle (fnil conj []) f) nil)))))

;; ---------- device manager (policy-gated) ----------

(defn make-device-manager
  "Make a device manager. `policy` is a wit policy (set of granted capability
  strings). `drivers` is a map of surface-key → IDevice. `opts` unused for now.
  Every device call is gated: a surface not in the policy returns ::denied."
  [policy drivers opts]
  {:policy policy :drivers drivers :opts opts})

(defn discover
  "Enumerate the device surfaces a manager's policy grants (in canonical
  order). Returns a seq of surface keywords."
  [mgr]
  (let [granted? (fn [s] (w/allows? (:policy mgr) (surface-cap s)))]
    (filter granted? (keys surface-effects))))

(defn- gate
  "Return the driver for `surface` if the policy grants it, else nil."
  [mgr surface]
  (when (w/allows? (:policy mgr) (surface-cap surface))
    (get-in mgr [:drivers surface])))

(def denied ::denied)

(defn call
  "Capability-gated device call. `surface` is a keyword (`:bluetooth`), `method`
  is `:scan`/`:read`/`:write`/`:subscribe`, `args` is a map of method args.
  Returns `::denied` if the surface isn't granted, `::unknown-method` if
  `method` isn't among the surface's declared effects (see surface-effects) —
  granting a surface only authorizes the methods that surface's schema
  actually exposes, not every IDevice method a driver happens to implement —
  dispatches to the driver otherwise."
  [mgr surface method args]
  (if-let [dev (gate mgr surface)]
    (if (contains? (get surface-effects surface) method)
      (case method
        :scan      (scan dev)
        :read      (read-dev dev (:handle args))
        :write     (write-dev dev (:handle args) (:data args))
        :subscribe (subscribe dev (:handle args) (:fn args))
        ::unknown-method)
      ::unknown-method)
    denied))

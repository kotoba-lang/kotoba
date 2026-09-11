(ns kotoba.sensing-host
  "Host implementation for the 4 read-only device-sensing host imports
  registered by ADR-2607140600 Phase 3a (the indoor floorplan-lab's
  device-capability bridge): motion-read (kotoba-core-contracts
  \"motion/read\", capability id 234), audio-play/audio-record (\"audio/io\",
  235), ble-scan (\"ble/scan\", 236), wifi-info (\"wifi/info\", 237).

  PHASE 3a SCOPE (see the ADR's \"Scope of this ADR\" section): this
  namespace is SOFTWARE ONLY. It never calls CoreMotion, CoreBluetooth,
  AVAudioEngine, or any other real OS sensing API -- that native shim is
  explicitly out of scope here, to be implemented separately (human or a
  separately-authorized agent) as a thin, judgment-free glue layer per
  ADR-2607030900's `aiueos-device-provider` design (\"the native shim only
  does what it's told, all policy/judgment logic stays on this side of the
  boundary\"). Every op here is a DETERMINISTIC STUB when no DRIVER is
  injected -- always the same input-independent answer, mirroring
  aiueos.execute's `device-access-stub` (\"registering these as
  capabilities makes them nameable/gateable from .kotoba source, it does
  not grant hardware access\") and kotoba.wasm-exec's own stub-host-
  function convention:
    motion-read   -> 0 samples written (no motion data available)
    audio-play    -> -1 (nothing was actually played)
    audio-record  -> 0 samples written (no audio captured)
    ble-scan      -> 0 peripherals found
    wifi-info     -> 0 (info unavailable -- also the honest iOS-constrained
                     default even with a real driver: no raw RSSI scan
                     without special entitlements)

  DRIVER INJECTION POINT (ADR-2607030900's device-access-provider pattern,
  \"実機呼び出しの「向こう側」は将来の差し替えポイントとして関数シグネチャ
  だけ用意しておく\"): every op takes an optional DRIVER map of plain
  Clojure functions (`{:motion-read (fn [] ...) :audio-play (fn [freq-hz
  duration-ms] ...) :audio-record (fn [duration-ms] ...) :ble-scan (fn
  [duration-ms] ...) :wifi-info (fn [] ...)}`). A nil driver, or a driver
  missing a given key, falls back to that op's stub answer above -- the
  judgment of WHETHER/HOW to call a real sensor stays entirely on the
  driver's side (never implemented here), and this namespace's job is
  only to route the call and encode/decode the Wasm memory ABI.

  PORTABLE (.cljc) per the repo-wide runtime priority (CLAUDE.md:
  kotoba wasm > clojurewasm > ClojureScript > nbb, JVM last resort),
  same split as kotoba.kami-host:
    :cljs  `sensing-host-imports` -- a (module \"kotoba\") import object for
           the native `js/WebAssembly` engine (browser or Node/nbb).
    :clj   `sensing-effects`/`sensing-host-functions` -- Chicory wiring,
           kept for kotoba.wasm-exec's JVM test suite; last-resort runtime,
           not the premise.

  Wire ABI: every op uses the SAME (out-ptr, out-cap) -> written-count-or-
  (-1)-on-overflow memory convention kotoba.wasm-exec's log-read/fs-read
  already use (see capability_contract.edn's comments) -- a guest that
  doesn't know how many samples it'll get still gets a bounded, safe
  write. motion-read/audio-record encode each sample as a little-endian
  i32 fixed-point value (`fixed-point-scale`, matching the task's \"固定
  小数点\" requirement -- no f32 host-import params/results are used here
  since these ops move a variable-length buffer, not a single scalar).
  ble-scan encodes each detected peripheral as an (id, rssi) i32 pair."
  #?(:clj (:require [kotoba.wasm-exec :as wasm-exec])))

;; ---------------------------------------------------------------------------
;; Pure, portable driver-dispatch layer -- unit-testable on any runtime
;; without a wasm instance or any Wasm memory ABI involved at all. Every fn
;; takes DRIVER first (nil-safe) so a caller with no real driver gets the
;; deterministic stub answer documented in the namespace docstring.

(defn read-motion
  "9 fixed-point sample values (accel x/y/z, gyro x/y/z, mag x/y/z) from
  DRIVER's `:motion-read` fn, or [] when DRIVER (or that key) is absent --
  the motion-read stub answer (0 samples)."
  [driver]
  (if-let [f (:motion-read driver)] (vec (f)) []))

(defn play-audio!
  "true/false success from DRIVER's `:audio-play` fn (FREQ-HZ, DURATION-MS),
  or false when DRIVER (or that key) is absent -- the audio-play stub
  answer (nothing was actually played)."
  [driver freq-hz duration-ms]
  (boolean (when-let [f (:audio-play driver)] (f freq-hz duration-ms))))

(defn record-audio
  "Fixed-point PCM samples from DRIVER's `:audio-record` fn (DURATION-MS),
  or [] when DRIVER (or that key) is absent -- the audio-record stub
  answer (0 samples captured)."
  [driver duration-ms]
  (if-let [f (:audio-record driver)] (vec (f duration-ms)) []))

(defn scan-ble
  "Detected peripherals (a seq of {:id :rssi}) from DRIVER's `:ble-scan`
  fn (DURATION-MS), or [] when DRIVER (or that key) is absent -- the
  ble-scan stub answer (0 peripherals found)."
  [driver duration-ms]
  (if-let [f (:ble-scan driver)] (vec (f duration-ms)) []))

(defn read-wifi-info
  "A {:signal-dbm ...} map (or whatever shape a real driver chooses) from
  DRIVER's `:wifi-info` fn, or nil when DRIVER (or that key) is absent --
  the wifi-info stub answer (info unavailable), which per ADR-2607140600
  is also the HONEST default even with a real driver most of the time (no
  raw RSSI scan without special entitlements under iOS)."
  [driver]
  (when-let [f (:wifi-info driver)] (f)))

(def fixed-point-scale
  "motion-read/audio-record encode each sample as `(round (* v scale))`,
  a little-endian i32 -- 1000 gives millesimal precision (matching the
  fixed-point convention the task and gpu-set-position's f32 params both
  avoid needing here, since these ops move a buffer, not a scalar)."
  1000)

;; ---------------------------------------------------------------------------
;; Wire layer, :cljs -- the canonical non-JVM host path: a (module "kotoba")
;; import object for the native js/WebAssembly engine (browser or Node).
;; Same deferred-memory MEMORY-BOX convention as kotoba.kami-host/
;; kami-host-imports.

#?(:cljs
   (defn- write-i32-seq!
     "Write VALUES (already-integer i32s) little-endian into MEMORY-BOX's
     wasm memory at PTR (capacity CAP bytes); returns the count written,
     or -1 if the encoded bytes would overflow CAP. 0 values -> 0, no
     memory touched (safe even before the module exports memory)."
     [memory-box ptr cap values]
     (let [n (count values)
           need (* 4 n)]
       (cond
         (zero? n) 0
         (> need cap) -1
         :else
         (let [view (js/DataView. (.-buffer (.-memory memory-box)) ptr need)]
           (doseq [[i v] (map-indexed vector values)]
             (.setInt32 view (* 4 i) v true))
           n)))))

#?(:cljs
   (defn- write-ble-entries!
     "Write ENTRIES ({:id :rssi} maps) as little-endian (id, rssi) i32 pairs
     into MEMORY-BOX's wasm memory at PTR (capacity CAP bytes); returns the
     entry count written, or -1 on overflow."
     [memory-box ptr cap entries]
     (let [n (count entries)
           need (* 8 n)]
       (cond
         (zero? n) 0
         (> need cap) -1
         :else
         (let [view (js/DataView. (.-buffer (.-memory memory-box)) ptr need)]
           (doseq [[i {:keys [id rssi]}] (map-indexed vector entries)]
             (.setInt32 view (* 8 i) id true)
             (.setInt32 view (+ 4 (* 8 i)) rssi true))
           n)))))

#?(:cljs
   (defn- fixed-point [v] (js/Math.round (* v fixed-point-scale))))

#?(:cljs
   (defn sensing-host-imports
     "DRIVER as the namespace docstring's driver map (nil for the pure
     deterministic stub). MEMORY-BOX per kotoba.kami-host/kami-host-
     imports (`(set! (.-memory memory-box) (.. instance -exports -memory))`
     after instantiation)."
     ([memory-box] (sensing-host-imports nil memory-box))
     ([driver memory-box]
      #js {:motion_read
           (fn [ptr cap]
             (write-i32-seq! memory-box ptr cap
                             (map fixed-point (read-motion driver))))
           :audio_play
           (fn [freq-hz duration-ms]
             (if (play-audio! driver freq-hz duration-ms) 0 -1))
           :audio_record
           (fn [duration-ms ptr cap]
             (write-i32-seq! memory-box ptr cap
                             (map fixed-point (record-audio driver duration-ms))))
           :ble_scan
           (fn [duration-ms ptr cap]
             (write-ble-entries! memory-box ptr cap (scan-ble driver duration-ms)))
           :wifi_info
           (fn [ptr cap]
             (let [info (read-wifi-info driver)]
               (if (nil? info)
                 0
                 (let [written (write-i32-seq! memory-box ptr cap
                                               [(fixed-point (:signal-dbm info 0))])]
                   (if (neg? written) 0 1)))))})))

;; ---------------------------------------------------------------------------
;; Wire layer, :clj -- Chicory wiring, kept ONLY so the existing
;; kotoba.wasm-exec test suite stays green (the JVM is the last-resort
;; runtime here, not the premise -- see the namespace docstring).

#?(:clj
   (do
     (defn- write-i32-seq!
       "Write VALUES (already-integer i32s) little-endian into INSTANCE's
       exported linear memory at PTR (capacity CAP bytes); returns the
       count written, or -1 if the encoded bytes would overflow CAP. 0
       values -> 0, no memory touched (safe to call with a nil/fake
       INSTANCE for the deterministic-stub path, which never has any
       values to write)."
       [instance ptr cap values]
       (let [n (count values)
             need (* 4 n)]
         (cond
           (zero? n) 0
           (> need cap) -1
           :else
           (let [buf (java.nio.ByteBuffer/allocate need)]
             (.order buf java.nio.ByteOrder/LITTLE_ENDIAN)
             (doseq [v values] (.putInt buf (int v)))
             (.write (.memory instance) (int ptr) (.array buf) 0 need)
             n))))

     (defn- write-ble-entries!
       "Write ENTRIES ({:id :rssi} maps) as little-endian (id, rssi) i32
       pairs into INSTANCE's exported linear memory at PTR (capacity CAP
       bytes); returns the entry count written, or -1 on overflow. 0
       entries -> 0, no memory touched."
       [instance ptr cap entries]
       (let [n (count entries)
             need (* 8 n)]
         (cond
           (zero? n) 0
           (> need cap) -1
           :else
           (let [buf (java.nio.ByteBuffer/allocate need)]
             (.order buf java.nio.ByteOrder/LITTLE_ENDIAN)
             (doseq [{:keys [id rssi]} entries]
               (.putInt buf (int id))
               (.putInt buf (int rssi)))
             (.write (.memory instance) (int ptr) (.array buf) 0 need)
             n))))

     (defn- fixed-point ^long [v] (Math/round (double (* v fixed-point-scale))))

     (defn sensing-effects
       "op -> (fn [instance args] -> long) for every sensing-* host import,
       against DRIVER (the namespace docstring's driver map; nil for the
       pure deterministic stub) -- same raw-effect shape as
       kotoba.wasm-exec/real-op-effects and kotoba.kami-host/kami-effects,
       consumed by `sensing-host-functions`. Every branch's stub path (nil
       DRIVER, or DRIVER missing that key) never touches INSTANCE, so it's
       safe to call these fns directly with `instance` nil in tests."
       ([] (sensing-effects nil))
       ([driver]
        {'motion-read
         (fn [instance args]
           (long (write-i32-seq! instance (aget args 0) (aget args 1)
                                 (map fixed-point (read-motion driver)))))
         'audio-play
         (fn [_instance args]
           (long (if (play-audio! driver (aget args 0) (aget args 1)) 0 -1)))
         'audio-record
         (fn [instance args]
           (long (write-i32-seq! instance (aget args 1) (aget args 2)
                                 (map fixed-point (record-audio driver (aget args 0))))))
         'ble-scan
         (fn [instance args]
           (long (write-ble-entries! instance (aget args 1) (aget args 2)
                                     (scan-ble driver (aget args 0)))))
         'wifi-info
         (fn [instance args]
           (let [info (read-wifi-info driver)]
             (long
              (if (nil? info)
                0
                (let [written (write-i32-seq! instance (aget args 0) (aget args 1)
                                              [(fixed-point (:signal-dbm info 0))])]
                  (if (neg? written) 0 1))))))}))

     (defn sensing-host-functions
       "Guarded HostFunctions for the sensing-* surface (see
       kotoba.wasm-exec/guarded-host-functions: fail-closed per-call
       capability check against POLICY, receipted via OPTS' :record! when
       supplied). A policy that doesn't grant motion/read, audio/io,
       ble/scan, or wifi/info denies that op's very first call. DRIVER as
       `sensing-effects` (nil for the pure deterministic stub)."
       ([policy] (sensing-host-functions nil policy nil))
       ([driver policy] (sensing-host-functions driver policy nil))
       ([driver policy opts]
        (wasm-exec/guarded-host-functions (sensing-effects driver) policy opts)))))

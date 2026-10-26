(ns kotoba.kami-engine-host
  "ClojureScript port of kotoba-lang/kami-script-runtime-rs — the wasmtime
  host that binds every `kami:engine/*` import `kotoba.engine-clj.codegen/
  compile` emits (`bind_scene`/`bind_input`/`bind_random`/`bind_time`, 14
  host-imports total) and drives a compiled game's `init`/`<name>-tick`
  lifecycle against a minimal in-memory ECS store. Ported 1:1 in semantics
  from that crate's `src/lib.rs` so the same compiled `game.wasm` a Rust/
  wasmtime host runs also runs on the browser's OR Node's native
  `WebAssembly` engine — no wasmtime, no JVM, no Chicory.

  Compiled once via shadow-cljs `:target :esm` (see shadow-cljs.edn's
  `:kami-engine-host` build) to a single ES module (`src/kami-engine-host.js`)
  that runs identically in a browser `<script type=\"module\">` and in Node
  (`import`) — the same artifact, not separate per-platform hand-ports. This
  supersedes the earlier hand-written-JS approach this repo's other modules
  (`actor-host.js`/`kgraph.js`) used (see ADR-2607072715).

  Unlike `actor-host.js`'s single `(module \"kotoba\")` ABI, this host wires
  FOUR distinct WASM import modules (`kami:engine/scene@1.0.0`, `/input`,
  `/random`, `/time`, each `@1.0.0`) — the exact namespaces
  `kotoba.engine-clj.wasm-bytes/emit-module`'s import section encodes.

  i64 <-> JS: every WASM `i64` param/result crosses the WebAssembly-JS
  boundary as a native `BigInt` (standard \"WebAssembly BigInt integration\"
  behavior all evergreen engines, including V8 in both Node and Chromium,
  have shipped since ~2020). `f32` params/results are plain JS `number`s.
  Entity/query ids are stored internally as plain numbers (safe: no
  realistic game approaches 2^53 live entities) and converted to/from
  `BigInt` only at the import-function boundary.

  Not ported (matches kami-script-runtime-rs's own documented scope): the
  `render`/`audio`/`physics` bindings the original crate never wired either;
  the `wasmi` no-JIT backend (this port only targets the native `WebAssembly`
  engine browsers/Node already ship, which is JIT/AOT already).")

;; ---------------------------------------------------------------------------
;; BigInt interop helpers — ClojureScript's numeric tower (bit-xor et al.)
;; assumes JS `number`, not `BigInt`; JS's own `^`/`<<`/`>>` operators DO
;; support BigInt operands (but require BOTH sides be BigInt, unlike
;; relational operators which tolerate a Number/BigInt mix) — these thin
;; wrappers make that requirement explicit rather than relying on numeric
;; auto-coercion.

(defn- b-xor [a b] (js* "(~{} ^ ~{})" a b))
(defn- b-shl [a n] (js* "(~{} << BigInt(~{}))" a n))
(defn- b-shr [a n] (js* "(~{} >> BigInt(~{}))" a n))
(defn- b-mask64 [x] (js* "BigInt.asUintN(64, ~{})" x))
(defn- b-mod [a b] (js* "(~{} % ~{})" a b))

;; ---------------------------------------------------------------------------
;; `ordered-tick-exports`: hand-parse the WASM export section (id 7) for
;; every export name ending in `-tick`, in export-section (definition)
;; order — ported verbatim from the recovered `ordered_tick_exports`/
;; `read_uleb`. System execution order must match the guest's own
;; `defsystem` definition order, not whatever order `instance.exports`
;; iterates in (not guaranteed stable).

(defn- read-uleb [bytes off]
  (loop [off off val 0 shift 0]
    (if (>= off (alength bytes))
      [val off]
      (let [byte (aget bytes off)
            off' (inc off)
            val' (bit-or val (bit-shift-left (bit-and byte 0x7f) shift))]
        (if (zero? (bit-and byte 0x80))
          [val' off']
          (recur off' val' (+ shift 7)))))))

(defn- ordered-tick-exports*
  [wasm-bytes]
  (let [len (alength wasm-bytes)]
    (if (< len 8)
      []
      (loop [i 8]
        (if (>= i len)
          []
          (let [id (aget wasm-bytes i)
                i (inc i)
                [size i] (read-uleb wasm-bytes i)
                end (min (+ i size) len)]
            (if (= id 7)
              (let [[count j0] (read-uleb wasm-bytes i)]
                (loop [k 0 j j0 acc (transient [])]
                  (if (>= k count)
                    (persistent! acc)
                    (let [[nlen nj] (read-uleb wasm-bytes j)
                          e (min (+ nj nlen) len)
                          name (.decode (js/TextDecoder. "utf-8") (.slice wasm-bytes nj e))
                          j (inc e) ; skip name bytes + export-kind byte
                          [_ j] (read-uleb wasm-bytes j)]
                      (recur (inc k) j
                             (if (.endsWith name "-tick") (conj! acc name) acc))))))
              (recur end))))))))

(defn ordered-tick-exports
  "Returns a plain JS array of export names (JS-facing export — see
  shadow-cljs.edn's `:exports`)."
  [wasm-bytes]
  (clj->js (ordered-tick-exports* wasm-bytes)))

;; ---------------------------------------------------------------------------
;; ECS store + host state — ported field-for-field from the recovered
;; `EcsStore`/`HostState`, using an atom of plain Clojure data (persistent
;; maps/vectors) rather than mutable `js/Map`s: this data is small (tens of
;; entities), so idiomatic immutable-data-in-an-atom is both simpler and
;; less interop-error-prone than mirroring Rust's `HashMap` 1:1.

(defn- tagged-ids [st tag]
  (->> (:tags st)
       (filter (fn [[_ t]] (= t tag)))
       (map key)))

(defn- do-spawn! [state tag]
  (let [id (:next-id @state)]
    (swap! state (fn [st]
                   (cond-> (-> st
                               (assoc :next-id (inc id))
                               (assoc-in [:entities id] {:pos [0 0 0] :vel [0 0 0]}))
                     (seq tag) (assoc-in [:tags id] tag))))
    id))

(defn- do-despawn! [state id]
  (swap! state (fn [st] (-> st (update :entities dissoc id) (update :tags dissoc id)))))

(defn- do-count-tagged [st tag] (count (tagged-ids st tag)))

(defn- do-query-begin! [state tag]
  (let [ids (vec (tagged-ids @state tag))
        handle (:next-query @state)]
    (swap! state (fn [st] (-> st (update :next-query inc) (assoc-in [:query-cursors handle] ids))))
    handle))

(defn- do-query-next! [state handle]
  (let [ids (get-in @state [:query-cursors handle])]
    (if (empty? ids)
      (do (swap! state update :query-cursors dissoc handle) -1)
      (let [id (peek ids)]
        (swap! state assoc-in [:query-cursors handle] (pop ids))
        id))))

;; nearest(tag, x, y, maxd) -> entity-id or nil. 2D broadphase, host-side —
;; ported verbatim from `bind_scene::nearest`.
(defn- do-nearest [st tag x y maxd]
  (let [max2 (* maxd maxd)]
    (->> (tagged-ids st tag)
         (map (fn [id]
                (let [[ex ey] (get-in st [:entities id :pos])
                      dx (- ex x) dy (- ey y)]
                  [id (+ (* dx dx) (* dy dy))])))
         (filter (fn [[_ d2]] (<= d2 max2)))
         (reduce (fn [best [id d2]] (if (or (nil? best) (< d2 (second best))) [id d2] best)) nil)
         first)))

;; move-toward(entity, target, speed) — host does the normalize*speed math,
;; ported verbatim from `bind_scene::move-toward`.
(defn- do-move-toward! [state eid target speed]
  (let [st @state
        sp (get-in st [:entities eid :pos])
        tp (get-in st [:entities target :pos])]
    (when (and sp tp)
      (let [dx (- (nth tp 0) (nth sp 0))
            dy (- (nth tp 1) (nth sp 1))
            len (js/Math.sqrt (+ (* dx dx) (* dy dy)))
            vel (if (> len 1e-6) [(* (/ dx len) speed) (* (/ dy len) speed) 0] [0 0 0])]
        (swap! state assoc-in [:entities eid :vel] vel)))))

;; xorshift64, ported verbatim from `bind_random::int` — host-owned seeded
;; PRNG so replays/tests are reproducible. `state`'s `:rng` holds a native
;; JS BigInt (never a cljs number).
(defn- next-random! [state]
  (let [x (:rng @state)
        x (b-mask64 (b-xor x (b-mask64 (b-shl x 13))))
        x (b-mask64 (b-xor x (b-shr x 7)))
        x (b-mask64 (b-xor x (b-mask64 (b-shl x 17))))]
    (swap! state assoc :rng x)
    x))

;; ---------------------------------------------------------------------------
;; Public API — a factory function (not a JS `class`, more idiomatic here)
;; returning a plain JS object exposing the same method surface a consumer
;; drives: `imports`, `setAxis`, `attach`, `callInit`, `tick`, `entityCount`,
;; `taggedCount`, `debugDump`.

(defn create-kami-engine-host
  "`seed`: any JS BigInt or Number, forced odd/non-zero (xorshift64 never
  degenerates) — matches the recovered `HostState::new`."
  [seed]
  (let [state (atom {:entities {} :tags {} :next-id 0 :axes {} :tick-n 0
                      :query-cursors {} :next-query 1
                      :rng (js* "(BigInt(~{}) | 1n)" seed)
                      :systems [] :instance nil})
        read-str (fn [memory-box ptr len]
                   (if (<= len 0)
                     ""
                     (.decode (js/TextDecoder. "utf-8")
                              (js/Uint8Array. (.-buffer (.-memory memory-box)) ptr len))))]
    #js {"imports"
         (fn [memory-box]
           #js {"kami:engine/scene@1.0.0"
                #js {"spawn"         (fn [ptr len] (js/BigInt (do-spawn! state (read-str memory-box ptr len))))
                     "despawn"       (fn [eid] (do-despawn! state (js/Number eid)))
                     "set-position"  (fn [eid x y z]
                                       (swap! state (fn [st]
                                                      (if (contains? (:entities st) (js/Number eid))
                                                        (assoc-in st [:entities (js/Number eid) :pos] [x y z])
                                                        st))))
                     "set-velocity"  (fn [eid vx vy vz]
                                       (swap! state (fn [st]
                                                      (if (contains? (:entities st) (js/Number eid))
                                                        (assoc-in st [:entities (js/Number eid) :vel] [vx vy vz])
                                                        st))))
                     "get-x"         (fn [eid] (get-in @state [:entities (js/Number eid) :pos 0] 0))
                     "get-y"         (fn [eid] (get-in @state [:entities (js/Number eid) :pos 1] 0))
                     "count-tagged"  (fn [ptr len] (js/BigInt (do-count-tagged @state (read-str memory-box ptr len))))
                     "query-begin"   (fn [ptr len] (js/BigInt (do-query-begin! state (read-str memory-box ptr len))))
                     "query-next"    (fn [handle] (js/BigInt (do-query-next! state (js/Number handle))))
                     "nearest"       (fn [ptr len x y maxd]
                                       (let [tag (read-str memory-box ptr len)
                                             id (do-nearest @state tag x y maxd)]
                                         (if (nil? id) (js/BigInt -1) (js/BigInt id))))
                     "move-toward"   (fn [eid target speed]
                                       (do-move-toward! state (js/Number eid) (js/Number target) speed))}
                "kami:engine/input@1.0.0"
                #js {"axis" (fn [ptr len] (get (:axes @state) (read-str memory-box ptr len) 0))}
                "kami:engine/random@1.0.0"
                #js {"int" (fn [n] (if (<= n 0) (js/BigInt 0) (b-mod (next-random! state) n)))}
                "kami:engine/time@1.0.0"
                #js {"tick" (fn [] (js/BigInt (:tick-n @state)))}})

         "setAxis" (fn [name value] (swap! state assoc-in [:axes name] value))

         ;; Call after `WebAssembly.instantiate(wasmBytes, importObject)`
         ;; resolves, with the same `wasmBytes` and the resulting `instance`.
         "attach" (fn [instance wasm-bytes]
                    (swap! state assoc :instance instance :systems (ordered-tick-exports* wasm-bytes)))

         "callInit" (fn [] (js-invoke (.-exports (:instance @state)) "init"))

         ;; Run every `<name>-tick` export once, in definition order
         ;; (advancing `tick_n` first), then integrate motion — ported
         ;; verbatim from `KamiHost::tick`.
         "tick" (fn [dt-ms]
                  (swap! state update :tick-n inc)
                  (let [exports (.-exports (:instance @state))]
                    (doseq [name (:systems @state)]
                      (let [f (aget exports name)]
                        (when (fn? f) (f (js/BigInt dt-ms))))))
                  (let [dt (/ dt-ms 1000)]
                    (swap! state update :entities
                           (fn [entities]
                             (into {} (map (fn [[id e]]
                                             (let [[px py pz] (:pos e) [vx vy vz] (:vel e)]
                                               [id (assoc e :pos [(+ px (* vx dt)) (+ py (* vy dt)) (+ pz (* vz dt))])])))
                                   entities))))
                  (swap! state assoc :query-cursors {}))

         "entityCount" (fn [] (count (:entities @state)))
         "taggedCount" (fn [tag] (do-count-tagged @state tag))

         ;; Debug-only: `{id, tag, pos, vel}` for every live entity.
         "debugDump" (fn []
                       (clj->js (map (fn [[id e]] {:id id :tag (get (:tags @state) id "") :pos (:pos e) :vel (:vel e)})
                                     (:entities @state))))}))

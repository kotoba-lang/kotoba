(ns kami.sim
  "L3 — the engine loop: fixed-step tick, system registry, and the commit-on-save
  bridge back to Datomic. This is the public runtime entry point (ARCHITECTURE.md
  §10/§12). Runs in the browser (RAF-driven) over an in-memory `kami.ecs` world."
  (:refer-clojure :exclude [run!])
  (:require [kami.ecs    :as ecs]
            [kami.render :as render]
            [kami.gpu    :as gpu]))

(defonce ^{:doc "Registered systems: ident → {:fn (fn [world dt] world) :order n}."}
  registry (atom {}))

(defn register!
  "Register a system fn under `ident` with `opts` ({:order n}, default 0).
  `f` is (fn [world dt] -> world), pure over the ECS world. Returns ident."
  [ident opts f]
  (swap! registry assoc ident (merge {:order 0} opts {:fn f}))
  ident)

#?(:clj
   (defmacro defsystem
     "Define + register a tick system. Supports an optional opts map and docstring:
       (defsystem spin {:order 10} [world dt] \"doc\" body…)
     Body sees `world` and `dt` (ms) and returns the updated world. Pure — no IO,
     no GPU. Mirrors `kami-clj`'s `defsystem` but stays host-side."
     [sym & more]
     (let [opts     (if (map? (first more)) (first more) {})
           more     (if (map? (first more)) (rest more) more)
           arglist  (first more)
           body     (rest more)
           body     (if (string? (first body)) (rest body) body) ; drop docstring
           ident    (keyword (str *ns*) (name sym))]
       `(do (defn ~sym ~arglist ~@body)
            (register! ~ident ~opts ~sym)))))

(defn systems-in-order
  "Resolved system fns to run, sorted by :order. `idents` selects a subset
  (default: all registered)."
  ([] (systems-in-order (keys @registry)))
  ([idents]
   (->> idents
        (keep @registry)
        (sort-by :order)
        (map :fn))))

(defn step
  "Advance one fixed timestep: thread `world` through the selected systems in
  :order with delta `dt` (ms). Pure (no render). Decoupled from RAF so it can run
  at a fixed 30/60 Hz independent of frame rate (cf. kami-dec 30 Hz physics)."
  ([world dt] (step world dt (keys @registry)))
  ([world dt idents]
   (reduce (fn [w f] (f w dt)) world (systems-in-order idents))))

(defn commit!
  "Save path: diff `world` via `kami.ecs/->tx` and persist via `transact-fn`
  (a closure over `kami.db/transact!` + conn, or an HTTP POST from cljs — keeps
  this ns platform-neutral). Returns the world re-anchored with the new basis-t
  via `kami.ecs/mark-saved`. `transact-fn` must return the post-tx basis-t."
  [world transact-fn]
  (let [tx (ecs/->tx world)]
    (if (empty? tx)
      world
      (ecs/mark-saved world (transact-fn tx)))))

(defn render-once
  "Build one render-IR frame from `world` and submit it to `backend`. Returns the
  frame map (handy for golden tests / record-replay)."
  [world backend {:keys [n aspect] :or {n 0 aspect 1.7777778}}]
  (let [fr (render/frame world {:n n :aspect aspect})]
    (gpu/submit! backend fr)
    fr))

(defn run!
  "Boot the runtime. `opts`:
     {:canvas \"c\"            ; canvas id (cljs)
      :snapshot <snapshot>    ; from kami.scene (loaded over the wire)
      :backend  <IGpuBackend> ; from kami.gpu/backend
      :systems  [ident …]     ; default: all registered
      :aspect 1.78 :hz 30}    ; fixed step rate
  Loads the snapshot into an ECS world, ensures assets, then drives the loop:
  fixed-step `step` → `render-once`. In cljs this attaches a requestAnimationFrame
  loop with a fixed-step accumulator; on the JVM it returns the initialized handle
  (host backends drive their own loop). Returns
  {:world (atom) :stop (fn) :commit (fn transact-fn)}."
  [{:keys [snapshot backend systems aspect hz]
    :or   {aspect 1.7777778 hz 30}}]
  (when-not backend (throw (ex-info "run!: missing :backend" {})))
  (let [world   (atom (ecs/load-snapshot snapshot))
        dt      (/ 1000.0 hz)
        running (atom true)]
    (gpu/ensure-assets! backend snapshot)
    #?(:cljs
       ;; Fixed-step accumulator: the RAF timestamp drives real elapsed time, which
       ;; we bank into `acc` and drain in whole `dt` steps. This decouples the
       ;; simulation rate (`hz`) from the display refresh — on a frame drop we catch
       ;; up with multiple steps; on a fast display we don't over-step. The 250 ms
       ;; clamp avoids a "spiral of death" after a long stall (tab backgrounded).
       (let [acc  (atom 0.0)
             last (atom nil)]
         (letfn [(frame-loop [ts n]
                   (when @running
                     (let [prev    (or @last ts)
                           elapsed (min 250.0 (- ts prev))]
                       (reset! last ts)
                       (swap! acc + elapsed)
                       (while (>= @acc dt)
                         (swap! world step dt systems)
                         (swap! acc - dt))
                       (render-once @world backend {:n n :aspect aspect})
                       (js/requestAnimationFrame #(frame-loop % (inc n))))))]
           (js/requestAnimationFrame #(frame-loop % 0)))))
    {:world  world
     :stop   (fn [] (reset! running false))
     :commit (fn [transact-fn] (swap! world commit! transact-fn))}))

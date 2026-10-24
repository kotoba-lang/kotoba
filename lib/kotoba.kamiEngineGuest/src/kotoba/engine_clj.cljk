(ns kotoba.engine-clj
  "kami-clj — Clojure-subset -> WASM-targeted-instruction-IR game-script
  compiler.

  Ported from `kami-engine-clj`'s Rust `src/lib.rs` (deleted, uncommitted,
  recovered from `kami-engine` git history, clj-wgsl migration
  ADR-2607010930). `kami-clj` reads a Clojure/EDN-subset source file and
  compiles it to a Module IR targeting the `kami:engine@1.0.0` WIT world
  (see `kotoba.engine-clj.component`). The compiled IR is meant to plug
  into a `kami-script-runtime`-style host that binds every `kami:engine/*`
  import to live engine state (ECS world, input, audio, draw queue) — see
  `kotoba.engine-clj.codegen`'s docstring for exactly where this port draws
  the AST/codegen-vs-byte-emission-adapter line.

  ## Architecture

  ```text
  .clj source --> kami-clj compiler --> Module IR (data)
                  (ast + codegen)              |
                                       [future: mechanical .wasm
                                        byte-emission host-adapter]
                                                |
                                      kami-game Component
                                                |
                                     kami-script-runtime-style host
                                                |
                            +-------------------+------------------+
                       hecs::World         kami-input          kami-audio
                      (ECS entities)     (keyboard/gamepad)  (spatial audio)
  ```

  ## Clojure subset supported

  - **F32 literals**: `(f32 1.5)` — compiled to
    f32.const -> i32.reinterpret_f32 -> i64.extend_i32_u so the value stays
    on the all-i64 stack.
  - **`defsystem`**: top-level tick-handler form — see below.
  - **Scene / ECS builtins**: `spawn-entity`, `despawn-entity`, `get-x`,
    `set-position!`, `get-vx`, `set-velocity!`, … (full list in
    `kotoba.engine-clj.ast`).
  - **Input builtins**: `key-down?`, `key-pressed?`, `axis`, `pointer-x/y`.
  - **Render builtins**: `draw-mesh!`, `spawn-particle!`, `draw-line!`.
  - **Audio builtins**: `play-sound`, `stop-sound`, `play-sound-at`.
  - **Time builtins**: `delta-ms`, `elapsed-ms`, `tick-n`.

  ## defsystem

  ```clojure
  (defsystem player-controller [dt]
    ;; runs every tick; dt is the delta time in milliseconds (i64)
    (when (key-down? \"ArrowRight\")
      (let [vx (f32 2.0)]
        (set-velocity! player vx (f32 0.0) (f32 0.0))))
    (when (key-down? \"ArrowLeft\")
      (set-velocity! player (f32 -2.0) (f32 0.0) (f32 0.0))))
  ```

  `defsystem` desugars to `(defn player-controller-tick [dt] …)`, exported as
  `player-controller-tick`.

  ## Game PRELUDE

  Every module compiled with [[compile-str-with-prelude]] gets
  [[game-prelude]] prepended, which provides Vec3 heap helpers, entity-
  position sugar, a fixed-step timer, and a growable Vector / Map state bag
  — see the prelude source below for the full API.

  ## Quick example

  ```clojure
  (require '[kotoba.engine-clj :as engine-clj])
  (def src \"
    (def player-eid 1)
    (defn init [] player-eid)
    (defsystem move [dt]
      (when (key-down? \\\"ArrowRight\\\")
        (set-velocity! player-eid (f32 2.0) (f32 0.0) (f32 0.0))))\")
  (engine-clj/compile-str src)
  ;; => {:host-imports [...] :functions [...] :atoms [] ...}  ; Module IR
  ```"
  (:require [kotoba.engine-clj.ast :as ast]
            [kotoba.engine-clj.codegen :as codegen]
            [kotoba.lang.text :as str]))

#?(:clj
   (defn compile-str
     "Compile Clojure-subset source into a Module IR (see
     `kotoba.engine-clj.codegen` for what that IR is and why it stops short
     of raw `.wasm` bytes)."
     [src]
     (-> src ast/parse-program-str codegen/compile)))

(defn- strip-shebang
  "A leading Unix shebang (`#!...`) is stripped so scripts can be
  executable: `#!/usr/bin/env kami-clj`."
  [src]
  (if (str/starts-with? src "#!")
    (let [i (str/index-of src "\n")]
      (if i (subs src (inc i)) ""))
    src))

#?(:clj
   (defn compile-file
     "Compile a `.kami` or `.clj` game-script file."
     [path]
     (compile-str (strip-shebang (slurp path)))))

;; ---------------------------------------------------------------------------
;; GAME_PRELUDE — convenience helpers written in the language itself
;;
;; This is literal kami-clj *source text* (not Rust logic), copied verbatim
;; from `lib.rs`'s `GAME_PRELUDE` constant — nothing to "port" here beyond
;; the string itself. It compiles through the SAME `compile-str` as any
;; other program, exercising `ast`/`codegen` end-to-end.
;; ---------------------------------------------------------------------------

(def game-prelude
  "Common f32 constants and Vec3/timer/vec/map utilities prepended by
  [[compile-str-with-prelude]].

  ## Vec3

  A Vec3 is a heap-allocated triple `[x:i32@0, y:i32@4, z:i32@8]` (3 x 4
  bytes = 12 bytes; stored as f32 bit-patterns).

  ## Timer

  A timer is a heap cell `[period-ms:i64@0, elapsed-ms:i64@8]`.
  `(timer-tick! t dt)` advances the elapsed counter; `(timer-fired? t)`
  returns 1 if elapsed >= period (and resets elapsed)."
  "
;; ---- Common f32 bit-pattern constants (IEEE-754) --------------------------
(def F32-ZERO     0)           ;; 0.0f  = 0x00000000
(def F32-ONE      1065353216)  ;; 1.0f  = 0x3F800000
(def F32-HALF     1056964608)  ;; 0.5f  = 0x3F000000
(def F32-NEG-ONE -1082130432)  ;; -1.0f = 0xBF800000
(def F32-TWO      1073741824)  ;; 2.0f  = 0x40000000

;; ---- Vec3 helpers ----------------------------------------------------------
;; Allocate a Vec3 (3 x i32 f32-bit-pattern words)
(defn vec3-make [x y z]
  (let [p (alloc 12)]
    (store32! p x)
    (store32! (+ p 4) y)
    (store32! (+ p 8) z)
    p))

(defn vec3-x [v] (load32 v))
(defn vec3-y [v] (load32 (+ v 4)))
(defn vec3-z [v] (load32 (+ v 8)))

(defn vec3-set-x! [v x] (store32! v x) v)
(defn vec3-set-y! [v y] (store32! (+ v 4) y) v)
(defn vec3-set-z! [v z] (store32! (+ v 8) z) v)

;; Read entity position into a fresh Vec3 heap cell.
(defn entity-pos [eid]
  (vec3-make (get-x eid) (get-y eid) (get-z eid)))

;; Convenience single-component reads.
(defn entity-x [eid] (get-x eid))
(defn entity-y [eid] (get-y eid))
(defn entity-z [eid] (get-z eid))

;; ---- Fixed-step timer ------------------------------------------------------
;; Timer layout: [period-ms:i64@0, elapsed-ms:i64@8]
(defn timer-make [period-ms]
  (let [t (alloc 16)]
    (store64! t period-ms)
    (store64! (+ t 8) 0)
    t))

(defn timer-tick! [t dt]
  (let [elapsed (+ (load64 (+ t 8)) dt)]
    (store64! (+ t 8) elapsed)
    t))

(defn timer-fired? [t]
  (let [period  (load64 t)
        elapsed (load64 (+ t 8))]
    (if (>= elapsed period)
      (do (store64! (+ t 8) 0) 1)
      0)))

;; ---- Vector (state bag) ----------------------------------------------------
;; A growable-by-push, fixed-capacity i64 array — the Phase-4 building block for
;; game state that ECS components don't cover (spawn queues, wave lists, score
;; rings, cooldown tables). Slots hold any i64-stack value: entity ids, ints,
;; or f32 bit-patterns. Layout: [cap:i64@0, len:i64@8, slot0@16, slot1@24, …].
(defn vec-make [cap]
  (let [v (alloc (+ 16 (* cap 8)))]
    (store64! v cap)
    (store64! (+ v 8) 0)
    v))

(defn vec-cap [v] (load64 v))
(defn vec-len [v] (load64 (+ v 8)))

;; Address of slot i (no bounds check — callers stay within len/cap).
(defn vec-slot [v i] (+ v 16 (* i 8)))

(defn vec-get [v i] (load64 (vec-slot v i)))
(defn vec-set! [v i x] (store64! (vec-slot v i) x) v)

;; Append x if there's room; returns v either way (full push is a silent no-op,
;; matching the fixed-capacity contract — size for the worst case at vec-make).
(defn vec-push! [v x]
  (let [n (vec-len v)]
    (if (< n (vec-cap v))
      (do (store64! (vec-slot v n) x)
          (store64! (+ v 8) (+ n 1))
          v)
      v)))

;; Reset length to 0 (capacity/backing memory retained for reuse each frame).
(defn vec-clear! [v] (store64! (+ v 8) 0) v)

;; ---- Map (assoc bag) -------------------------------------------------------
;; A fixed-capacity i64->i64 association with linear-scan lookup — the Phase-4
;; key/value store for sparse game state (per-entity cooldowns keyed by id,
;; tag->count tallies, flag sets). Both keys and values are i64-stack values
;; (entity ids, ints, f32 bit-patterns). Layout: [cap:i64@0, len:i64@8] then
;; cap x (key:i64, val:i64) pairs (16 bytes each). Linear scan suits the small
;; maps gameplay needs; reach for a real hash table only past a few dozen keys.
(defn map-make [cap]
  (let [m (alloc (+ 16 (* cap 16)))]
    (store64! m cap)
    (store64! (+ m 8) 0)
    m))

(defn map-cap [m] (load64 m))
(defn map-len [m] (load64 (+ m 8)))

;; Slot addresses for entry i: key word, then value word 8 bytes after it.
(defn map-key-slot [m i] (+ m 16 (* i 16)))
(defn map-val-slot [m i] (+ (map-key-slot m i) 8))

;; Index of key k, or -1 if absent (loop/recur linear scan — no self-recursion).
(defn map-find [m k]
  (let [n (map-len m)]
    (loop [i 0]
      (if (< i n)
        (if (= (load64 (map-key-slot m i)) k)
          i
          (recur (+ i 1)))
        -1))))

(defn map-has? [m k] (if (>= (map-find m k) 0) 1 0))

;; Insert or update k->v. A new key past capacity is a silent no-op (size for the
;; worst case at map-make), matching the vector's fixed-capacity contract.
(defn map-put! [m k v]
  (let [idx (map-find m k)]
    (if (>= idx 0)
      (do (store64! (map-val-slot m idx) v) m)
      (let [n (map-len m)]
        (if (< n (map-cap m))
          (do (store64! (map-key-slot m n) k)
              (store64! (map-val-slot m n) v)
              (store64! (+ m 8) (+ n 1))
              m)
          m)))))

;; Value for k, or `default` when absent (no nil in the i64 value model).
(defn map-get-or [m k default]
  (let [idx (map-find m k)]
    (if (>= idx 0) (load64 (map-val-slot m idx)) default)))

;; Value for k, or 0 when absent (the common tally/flag case).
(defn map-get [m k] (map-get-or m k 0))

;; Reset to empty (capacity/backing memory retained for per-frame reuse).
(defn map-clear! [m] (store64! (+ m 8) 0) m)
")

#?(:clj
   (defn compile-str-with-prelude
     "Compile with [[game-prelude]] prepended."
     [src]
     (compile-str (str game-prelude "\n" src))))

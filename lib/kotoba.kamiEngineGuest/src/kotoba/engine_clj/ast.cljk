(ns kotoba.engine-clj.ast
  "Lowering from EDN → typed AST for the Clojure-subset compiler.

  Ported 1:1 from `kami-engine-clj`'s Rust `src/ast.rs` (deleted, uncommitted,
  recovered from `kami-engine` git history at HEAD `kami-engine-clj/src/ast.rs`
  as part of the clj-wgsl migration, ADR-2607010930). Extends the kotoba-clj
  value model with:

    - `{:node :float ...}` — float literals (compiled to
      f32.const → i32.reinterpret_f32 → i64.extend_i32_u).
    - Game-engine host-import builtins (scene / physics / input / render /
      audio / time / steam).
    - `defsystem` top-level form: sugar for a `(defn name-tick [dt] …)`
      exported fn.
    - `defentity` top-level form: sugar for a self-spawning constructor fn.
    - `defatom` top-level form: a mutable i64 state cell (a WASM global).

  ## Value model

  All values on the WASM stack are i64 (same as kotoba-clj). F32 values are
  represented as their IEEE-754 bit-pattern zero-extended to i64.

  Host imports that take f32 parameters receive the low 32 bits of the i64
  (via i32.wrap_i64); `kotoba.engine-clj.codegen` handles this wrapping
  automatically per the `:param-kind` annotation on each host import.

  ## Representation

  Rust's `enum Expr` (tagged union) becomes a tagged map `{:node <kw> …}`;
  `enum Builtin` becomes a plain keyword (`:add`, `:fadd`, `:spawn-entity`, …);
  `enum HostImport` becomes a *namespaced* keyword under `:host-import/…` so
  it is never ambiguous with a `Builtin` keyword even where the English name
  coincides (e.g. Builtin `:steam-unlock` vs `:host-import/steam-unlock`)."
  (:require [kotoba.engine-clj.errors :as err]
            #?(:clj [clojure.edn :as edn])))

;; ---------------------------------------------------------------------------
;; Hygienic gensym — mirrors `ast.rs`'s `AtomicU32` GENSYM counter, so nested
;; expansions (doseq-entities iterators, as-> / cond-> temporaries, dotimes
;; bound-N, min/max/clamp temporaries) never shadow each other.
;; ---------------------------------------------------------------------------

(defonce ^:private gensym-counter (atom 0))

(defn- engine-gensym [prefix]
  (str "__" prefix (swap! gensym-counter inc)))

;; ---------------------------------------------------------------------------
;; Builtins — split into kotoba-core ops and kami-engine host imports
;; ---------------------------------------------------------------------------
;; Mirrors `enum Builtin` (ast.rs:70-197). One keyword per Rust variant,
;; kebab-cased.

(def builtin-name->op
  "Mirrors `Builtin::from_name` (ast.rs:250-361) — surface syntax → Builtin op."
  {;; arithmetic
   "+" :add "-" :sub "*" :mul "/" :div "quot" :div "mod" :mod "rem" :mod
   "inc" :inc "dec" :dec "abs" :abs
   ;; f32 arithmetic (real float math on i64-boxed bit-patterns)
   "+f" :fadd "-f" :fsub "*f" :fmul "/f" :fdiv
   ;; f32 comparison (sign-correct)
   "<f" :flt ">f" :fgt "<=f" :fle ">=f" :fge "=f" :feq
   ;; comparison
   "=" :eq "!=" :noteq "not=" :noteq
   "<" :lt ">" :gt "<=" :le ">=" :ge
   "zero?" :zero "pos?" :pos "neg?" :neg
   ;; logic
   "and" :and "or" :or
   "bit-and" :bit-and "bit-or" :bit-or "bit-xor" :bit-xor
   "bit-shift-left" :shl "bit-shift-right" :shr-s
   "not" :not
   ;; strings / bytes
   "str-len" :str-len "byte-at" :byte-at
   "bytes-alloc" :bytes-alloc "byte-append!" :byte-append
   "bytes-len" :bytes-len "bytes-finish" :bytes-finish
   ;; raw memory
   "alloc" :alloc "load64" :load64 "store64!" :store64
   "load32" :load32 "store32!" :store32
   ;; f32 helpers
   "f32->bits" :f32-bits "bits->f32" :bits-f32
   ;; scene / ECS
   "spawn-entity" :spawn-entity "despawn-entity" :despawn-entity
   "get-x" :get-x "get-y" :get-y "get-z" :get-z "set-position!" :set-position
   "get-vx" :get-vx "get-vy" :get-vy "get-vz" :get-vz "set-velocity!" :set-velocity
   "get-rx" :get-rx "get-ry" :get-ry "get-rz" :get-rz "get-rw" :get-rw
   "set-rotation!" :set-rotation
   ;; physics
   "apply-impulse!" :apply-impulse "apply-force!" :apply-force "raycast" :raycast
   ;; input
   "key-down?" :key-down "key-pressed?" :key-pressed "axis" :axis
   "pointer-x" :pointer-x "pointer-y" :pointer-y
   ;; render
   "draw-mesh!" :draw-mesh "spawn-particle!" :spawn-particle
   "draw-line!" :draw-line "rt-enable!" :rt-enable
   ;; audio
   "play-sound" :play-sound "stop-sound" :stop-sound
   "play-sound-at" :play-sound-at "set-listener!" :set-listener
   ;; steam (Valve Steamworks, ADR-0048)
   "steam-unlock!" :steam-unlock "steam-set-stat!" :steam-set-stat
   "steam-rich-presence!" :steam-rich-presence
   ;; time
   "delta-ms" :delta-ms "elapsed-ms" :elapsed-ms "tick-n" :tick-n
   ;; query / RNG (survivors)
   "rand-int" :rand-int "query-begin" :query-begin "query-next" :query-next
   "count-tagged" :count-tagged "nearest-tagged" :nearest-tagged
   "move-toward!" :move-toward})

(def builtin->host-import
  "Mirrors `Builtin::host_import` (ast.rs:200-248) — the subset of Builtin ops
  that lower to a host WASM import rather than in-guest instructions."
  {:spawn-entity      :host-import/scene-spawn
   :despawn-entity    :host-import/scene-despawn
   :get-x             :host-import/scene-get-x
   :get-y             :host-import/scene-get-y
   :get-z             :host-import/scene-get-z
   :set-position      :host-import/scene-set-position
   :get-vx            :host-import/scene-get-vx
   :get-vy            :host-import/scene-get-vy
   :get-vz            :host-import/scene-get-vz
   :set-velocity      :host-import/scene-set-velocity
   :get-rx            :host-import/scene-get-rx
   :get-ry            :host-import/scene-get-ry
   :get-rz            :host-import/scene-get-rz
   :get-rw            :host-import/scene-get-rw
   :set-rotation      :host-import/scene-set-rotation
   :apply-impulse     :host-import/physics-apply-impulse
   :apply-force       :host-import/physics-apply-force
   :raycast           :host-import/physics-raycast
   :key-down          :host-import/input-key-down
   :key-pressed       :host-import/input-key-pressed
   :axis              :host-import/input-axis
   :pointer-x         :host-import/input-pointer-x
   :pointer-y         :host-import/input-pointer-y
   :draw-mesh         :host-import/render-draw-mesh
   :spawn-particle    :host-import/render-spawn-particle
   :draw-line         :host-import/render-draw-line
   :rt-enable         :host-import/render-rt-enable
   :play-sound        :host-import/audio-play
   :stop-sound        :host-import/audio-stop
   :play-sound-at     :host-import/audio-play-at
   :set-listener      :host-import/audio-set-listener
   :steam-unlock      :host-import/steam-unlock
   :steam-set-stat    :host-import/steam-set-stat
   :steam-rich-presence :host-import/steam-rich-presence
   :delta-ms          :host-import/time-delta-ms
   :elapsed-ms        :host-import/time-elapsed-ms
   :tick-n            :host-import/time-tick
   :rand-int          :host-import/random-int
   :query-begin       :host-import/scene-query-begin
   :query-next        :host-import/scene-query-next
   :count-tagged      :host-import/scene-count-tagged
   :nearest-tagged    :host-import/scene-nearest
   :move-toward       :host-import/scene-move-toward})

(defn host-import
  "The `:host-import/*` keyword a builtin op `op` (e.g. `:spawn-entity`) maps
  to, or nil if `op` is a pure guest builtin (e.g. `:add`) with no host
  import."
  [op]
  (get builtin->host-import op))

;; ---------------------------------------------------------------------------
;; Host imports — each maps to a (module, field) WASM import
;; ---------------------------------------------------------------------------
;; Mirrors `enum ParamKind` / `enum ReturnKind` / `enum HostImport` and its
;; `module_field` / `param_kinds` / `return_kind` methods (ast.rs:369-535).
;;
;; ParamKind:
;;   :i64          — plain i64 value (entity IDs, string handles, booleans, ints)
;;   :f32          — f32 bit-pattern stored in an i64; codegen emits
;;                   i32.wrap_i64 + f32.reinterpret_i32 before the host call.
;;   :string-handle — packed `(offset<<32)|len` lowered to a `(ptr:i32, len:i32)`
;;                    pair.
;; ReturnKind: :void :i32 :i64 :f32

(def host-import->module-field
  "WASM import `(module, field)` matching `wit/kami-game/world.wit`."
  {:host-import/scene-spawn          ["kami:engine/scene@1.0.0"   "spawn"]
   :host-import/scene-despawn        ["kami:engine/scene@1.0.0"   "despawn"]
   :host-import/scene-get-x          ["kami:engine/scene@1.0.0"   "get-x"]
   :host-import/scene-get-y          ["kami:engine/scene@1.0.0"   "get-y"]
   :host-import/scene-get-z          ["kami:engine/scene@1.0.0"   "get-z"]
   :host-import/scene-set-position   ["kami:engine/scene@1.0.0"   "set-position"]
   :host-import/scene-get-vx         ["kami:engine/scene@1.0.0"   "get-vx"]
   :host-import/scene-get-vy         ["kami:engine/scene@1.0.0"   "get-vy"]
   :host-import/scene-get-vz         ["kami:engine/scene@1.0.0"   "get-vz"]
   :host-import/scene-set-velocity   ["kami:engine/scene@1.0.0"   "set-velocity"]
   :host-import/scene-get-rx         ["kami:engine/scene@1.0.0"   "get-rx"]
   :host-import/scene-get-ry         ["kami:engine/scene@1.0.0"   "get-ry"]
   :host-import/scene-get-rz         ["kami:engine/scene@1.0.0"   "get-rz"]
   :host-import/scene-get-rw         ["kami:engine/scene@1.0.0"   "get-rw"]
   :host-import/scene-set-rotation   ["kami:engine/scene@1.0.0"   "set-rotation"]
   :host-import/physics-apply-impulse ["kami:engine/physics@1.0.0" "apply-impulse"]
   :host-import/physics-apply-force  ["kami:engine/physics@1.0.0" "apply-force"]
   :host-import/physics-raycast      ["kami:engine/physics@1.0.0" "raycast"]
   :host-import/input-key-down       ["kami:engine/input@1.0.0"   "key-down"]
   :host-import/input-key-pressed    ["kami:engine/input@1.0.0"   "key-pressed"]
   :host-import/input-axis           ["kami:engine/input@1.0.0"   "axis"]
   :host-import/input-pointer-x      ["kami:engine/input@1.0.0"   "pointer-x"]
   :host-import/input-pointer-y      ["kami:engine/input@1.0.0"   "pointer-y"]
   :host-import/render-draw-mesh     ["kami:engine/render@1.0.0"  "draw-mesh"]
   :host-import/render-spawn-particle ["kami:engine/render@1.0.0" "spawn-particle"]
   :host-import/render-draw-line     ["kami:engine/render@1.0.0"  "draw-line"]
   :host-import/render-rt-enable     ["kami:engine/render@1.0.0"  "rt-enable"]
   :host-import/audio-play           ["kami:engine/audio@1.0.0"   "play"]
   :host-import/audio-stop           ["kami:engine/audio@1.0.0"   "stop"]
   :host-import/audio-play-at        ["kami:engine/audio@1.0.0"   "play-at"]
   :host-import/audio-set-listener   ["kami:engine/audio@1.0.0"   "set-listener"]
   :host-import/steam-unlock         ["kami:engine/steam@1.0.0"   "unlock-achievement"]
   :host-import/steam-set-stat       ["kami:engine/steam@1.0.0"   "set-stat"]
   :host-import/steam-rich-presence  ["kami:engine/steam@1.0.0"   "set-rich-presence"]
   :host-import/time-delta-ms        ["kami:engine/time@1.0.0"    "delta-ms"]
   :host-import/time-elapsed-ms      ["kami:engine/time@1.0.0"    "elapsed-ms"]
   :host-import/time-tick            ["kami:engine/time@1.0.0"    "tick"]
   :host-import/random-int           ["kami:engine/random@1.0.0"  "int"]
   :host-import/scene-query-begin    ["kami:engine/scene@1.0.0"   "query-begin"]
   :host-import/scene-query-next     ["kami:engine/scene@1.0.0"   "query-next"]
   :host-import/scene-count-tagged   ["kami:engine/scene@1.0.0"   "count-tagged"]
   :host-import/scene-nearest        ["kami:engine/scene@1.0.0"   "nearest"]
   :host-import/scene-move-toward    ["kami:engine/scene@1.0.0"   "move-toward"]})

(def host-import->param-kinds
  "Parameter kinds from the guest's perspective (each i64 on the value stack).
  `:string-handle` lowers to 2 × i32 (ptr, len) — must be accounted for in the
  WASM function type."
  {:host-import/scene-spawn          [:string-handle]
   :host-import/scene-despawn        [:i64]
   :host-import/scene-get-x          [:i64]
   :host-import/scene-get-y          [:i64]
   :host-import/scene-get-z          [:i64]
   :host-import/scene-set-position   [:i64 :f32 :f32 :f32]
   :host-import/scene-get-vx         [:i64]
   :host-import/scene-get-vy         [:i64]
   :host-import/scene-get-vz         [:i64]
   :host-import/scene-set-velocity   [:i64 :f32 :f32 :f32]
   :host-import/scene-get-rx         [:i64]
   :host-import/scene-get-ry         [:i64]
   :host-import/scene-get-rz         [:i64]
   :host-import/scene-get-rw         [:i64]
   :host-import/scene-set-rotation   [:i64 :f32 :f32 :f32 :f32]
   :host-import/physics-apply-impulse [:i64 :f32 :f32 :f32]
   :host-import/physics-apply-force  [:i64 :f32 :f32 :f32]
   :host-import/physics-raycast      [:f32 :f32 :f32 :f32 :f32 :f32]
   :host-import/input-key-down       [:string-handle]
   :host-import/input-key-pressed    [:string-handle]
   :host-import/input-axis           [:string-handle]
   :host-import/input-pointer-x      []
   :host-import/input-pointer-y      []
   :host-import/render-draw-mesh     [:string-handle :f32 :f32 :f32]
   :host-import/render-spawn-particle [:string-handle :f32 :f32 :f32]
   :host-import/render-draw-line     [:f32 :f32 :f32 :f32 :f32 :f32 :i64]
   :host-import/render-rt-enable     [:string-handle]
   :host-import/audio-play           [:string-handle]
   :host-import/audio-stop           [:string-handle]
   :host-import/audio-play-at        [:string-handle :f32 :f32 :f32]
   :host-import/audio-set-listener   [:f32 :f32 :f32 :f32 :f32 :f32]
   :host-import/steam-unlock         [:string-handle]
   :host-import/steam-set-stat       [:string-handle :i64]
   :host-import/steam-rich-presence  [:string-handle :string-handle]
   :host-import/time-delta-ms        []
   :host-import/time-elapsed-ms      []
   :host-import/time-tick            []
   :host-import/random-int           [:i64]
   :host-import/scene-query-begin    [:string-handle]
   :host-import/scene-query-next     [:i64]
   :host-import/scene-count-tagged   [:string-handle]
   :host-import/scene-nearest        [:string-handle :f32 :f32 :f32]
   :host-import/scene-move-toward    [:i64 :i64 :f32]})

(def host-import->return-kind
  {:host-import/scene-spawn          :i64
   :host-import/scene-despawn        :void
   :host-import/scene-get-x          :f32
   :host-import/scene-get-y          :f32
   :host-import/scene-get-z          :f32
   :host-import/scene-set-position   :void
   :host-import/scene-get-vx         :f32
   :host-import/scene-get-vy         :f32
   :host-import/scene-get-vz         :f32
   :host-import/scene-set-velocity   :void
   :host-import/scene-get-rx         :f32
   :host-import/scene-get-ry         :f32
   :host-import/scene-get-rz         :f32
   :host-import/scene-get-rw         :f32
   :host-import/scene-set-rotation   :void
   :host-import/physics-apply-impulse :void
   :host-import/physics-apply-force  :void
   :host-import/physics-raycast      :i64
   :host-import/input-key-down       :i32
   :host-import/input-key-pressed    :i32
   :host-import/input-axis           :f32
   :host-import/input-pointer-x      :f32
   :host-import/input-pointer-y      :f32
   :host-import/render-draw-mesh     :void
   :host-import/render-spawn-particle :void
   :host-import/render-draw-line     :void
   :host-import/render-rt-enable     :void
   :host-import/audio-play           :void
   :host-import/audio-stop           :void
   :host-import/audio-play-at        :void
   :host-import/audio-set-listener   :void
   :host-import/steam-unlock         :void
   :host-import/steam-set-stat       :void
   :host-import/steam-rich-presence  :void
   :host-import/time-delta-ms        :i64
   :host-import/time-elapsed-ms      :i64
   :host-import/time-tick            :i64
   :host-import/random-int           :i64
   :host-import/scene-query-begin    :i64
   :host-import/scene-query-next     :i64
   :host-import/scene-count-tagged   :i64
   :host-import/scene-nearest        :i64
   :host-import/scene-move-toward    :void})

;; ---------------------------------------------------------------------------
;; Expression AST (superset of kotoba-clj)
;; ---------------------------------------------------------------------------
;; Mirrors `enum Expr` (ast.rs:541-578). Each variant is a tagged map
;; `{:node <kw> …}`:
;;   :int      {:value <i64>}
;;   :float    {:value <f32-as-double>}
;;   :str      {:value <string>}           ; bytes computed at codegen time
;;   :var      {:name <string>}
;;   :if       {:cond :then :else}
;;   :let      {:bindings [[name expr] …] :body [expr …]}
;;   :do       {:body [expr …]}
;;   :loop     {:bindings [[name expr] …] :body [expr …]}
;;   :recur    {:args [expr …]}
;;   :builtin  {:op <kw> :args [expr …]}
;;   :call     {:name <string> :args [expr …]}
;;   :atom-get {:name <string>}
;;   :atom-set {:name <string> :value expr}

;; ---------------------------------------------------------------------------
;; Parser
;; ---------------------------------------------------------------------------

#?(:clj
   (defn read-all-forms
     "Read every top-level EDN form from `src`. The JVM convenience reader
     backing `parse-program` — mirrors `kotoba_edn::parse_all` (an external
     reader dependency in the Rust original)."
     [src]
     (with-open [rdr (java.io.PushbackReader. (java.io.StringReader. src))]
       (loop [acc (transient [])]
         (let [form (edn/read {:eof ::eof} rdr)]
           (if (identical? form ::eof)
             (persistent! acc)
             (recur (conj! acc form))))))))

(defn- sym->qualified
  "Mirrors `Symbol::to_qualified` — the bare or `ns/name`-qualified string form
  of a symbol, as it appears in source."
  [s]
  (str s))

(defn- sym-name
  "Mirrors `sym_name` (ast.rs:1277-1284)."
  [v ctx]
  (if (symbol? v)
    (sym->qualified v)
    (throw (err/lower-error (str ctx " must be a symbol, found " (pr-str v))))))

(defn- list-head-symbol
  "Mirrors `list_head_symbol` (ast.rs:621-628)."
  [items]
  (let [h (first items)]
    (if (symbol? h)
      h
      (throw (err/lower-error "list must begin with a symbol in head position")))))

(declare lower-expr)

(defn- lower-param-vec
  "Mirrors `lower_param_vec` (ast.rs:729-739)."
  [v ctx]
  (if (vector? v)
    (mapv #(sym-name % "parameter") v)
    (throw (err/lower-error (str "`" ctx "` parameter list must be a vector `[…]`")))))

(defn- lower-def
  "Mirrors `lower_def` (ast.rs:630-638)."
  [items]
  (when-not (= (count items) 3)
    (throw (err/lower-error "def takes exactly: (def name value)")))
  {:name (sym-name (nth items 1) "def name")
   :value (lower-expr (nth items 2))})

(defn- lower-defatom
  "`(defatom name <int>)` — mirrors `lower_defatom` (ast.rs:640-654)."
  [items]
  (when-not (= (count items) 3)
    (throw (err/lower-error "defatom takes exactly: (defatom name <int-literal>)")))
  (let [nm (sym-name (nth items 1) "defatom name")
        v  (lower-expr (nth items 2))]
    (if (= (:node v) :int)
      {:name nm :init (:value v)}
      (throw (err/lower-error (str "defatom `" nm "` initial value must be an integer literal"))))))

(defn- lower-defn
  "Mirrors `lower_defn` (ast.rs:656-664)."
  [items]
  (when-not (>= (count items) 4)
    (throw (err/lower-error "defn requires: (defn name [params…] body…)")))
  (let [nm     (sym-name (nth items 1) "defn name")
        params (lower-param-vec (nth items 2) nm)
        body   (mapv lower-expr (drop 3 items))]
    {:name nm :params params :body body}))

(defn- lower-defsystem
  "`(defsystem name [dt] body…)` — sugar for a tick handler, exported as
  `name-tick`. Mirrors `lower_defsystem` (ast.rs:675-686)."
  [items]
  (when-not (>= (count items) 4)
    (throw (err/lower-error "defsystem requires: (defsystem name [dt] body…)")))
  (let [nm        (sym-name (nth items 1) "defsystem name")
        tick-name (str nm "-tick")
        params    (lower-param-vec (nth items 2) nm)
        body      (mapv lower-expr (drop 3 items))]
    {:name tick-name :params params :body body}))

(defn- lower-defentity
  "`(defentity name [params…] body…)` — entity-template constructor sugar.
  Desugars to a fn that spawns a fresh entity tagged `\"name\"`, binds it to
  `self` for the body to initialize, and returns the entity id. Mirrors
  `lower_defentity` (ast.rs:702-727)."
  [items]
  (when-not (>= (count items) 4)
    (throw (err/lower-error "defentity requires: (defentity name [params…] body…)")))
  (let [nm     (sym-name (nth items 1) "defentity name")
        params (lower-param-vec (nth items 2) nm)
        body0  (mapv lower-expr (drop 3 items))
        body   (conj body0 {:node :var :name "self"})
        spawn  {:node :builtin :op :spawn-entity :args [{:node :str :value nm}]}
        let-expr {:node :let :bindings [["self" spawn]] :body body}]
    {:name nm :params params :body [let-expr]}))

(defn parse-program
  "Mirrors `parse_program` (ast.rs:584-615) — EDN forms → `Program`
  `{:defs [...] :functions [...] :atoms [...]}`."
  [forms]
  (loop [forms forms defs [] functions [] atoms []]
    (if (empty? forms)
      {:defs defs :functions functions :atoms atoms}
      (let [form (first forms)
            items (if (seq? form) (vec form)
                      (throw (err/lower-error (str "top-level form must be a list, found: " (pr-str form)))))
            head (list-head-symbol items)]
        (case (name head)
          "ns"        (recur (rest forms) defs functions atoms)
          "def"       (recur (rest forms) (conj defs (lower-def items)) functions atoms)
          "defn"      (recur (rest forms) defs (conj functions (lower-defn items)) atoms)
          "defsystem" (recur (rest forms) defs (conj functions (lower-defsystem items)) atoms)
          "defentity" (recur (rest forms) defs (conj functions (lower-defentity items)) atoms)
          "defatom"   (recur (rest forms) defs functions (conj atoms (lower-defatom items)))
          (throw (err/lower-error
                  (str "unsupported top-level form `(" (name head) " …)` — "
                       "expected def/defn/ns/defsystem/defentity/defatom"))))))))

#?(:clj
   (defn parse-program-str
     "Convenience: read + lower a whole source string in one step. Mirrors the
     Rust free fn `parse_program(src: &str)` exactly (which itself calls
     `kotoba_edn::parse_all` then folds over the forms)."
     [src]
     (parse-program (read-all-forms src))))

;; ---------------------------------------------------------------------------
;; Lowering helpers — special forms
;; ---------------------------------------------------------------------------

(defn- lower-if
  [args]
  (when-not (= (count args) 3)
    (throw (err/lower-error "if takes: (if cond then else)")))
  {:node :if
   :cond (lower-expr (nth args 0))
   :then (lower-expr (nth args 1))
   :else (lower-expr (nth args 2))})

(defn- lower-when
  [args]
  (when (empty? args)
    (throw (err/lower-error "when takes: (when cond body…)")))
  {:node :if
   :cond (lower-expr (first args))
   :then {:node :do :body (mapv lower-expr (rest args))}
   :else {:node :int :value 0}})

(defn- lower-let
  [args]
  (let [binding-vec (first args)]
    (when-not (vector? binding-vec)
      (throw (err/lower-error "let requires a binding vector")))
    (when (odd? (count binding-vec))
      (throw (err/lower-error "let binding vector must have an even number of forms")))
    (let [bindings (mapv (fn [[nm val]] [(sym-name nm "let binding name") (lower-expr val)])
                          (partition 2 binding-vec))
          body (mapv lower-expr (rest args))]
      (when (empty? body)
        (throw (err/lower-error "let requires at least one body expression")))
      {:node :let :bindings bindings :body body})))

(defn- is-else-test [v]
  (or (and (keyword? v) (= (name v) "else"))
      (true? v)))

(defn- lower-cond
  [args]
  (when (odd? (count args))
    (throw (err/lower-error "cond requires an even number of test/expr forms")))
  (loop [pairs (reverse (partition 2 args)) acc {:node :int :value 0}]
    (if (empty? pairs)
      acc
      (let [[test expr] (first pairs)
            then (lower-expr expr)]
        (recur (rest pairs)
               (if (is-else-test test)
                 then
                 {:node :if :cond (lower-expr test) :then then :else acc}))))))

(defn- lower-loop
  [args]
  (let [binding-vec (first args)]
    (when-not (vector? binding-vec)
      (throw (err/lower-error "loop requires a binding vector")))
    (when (odd? (count binding-vec))
      (throw (err/lower-error "loop binding vector must have an even number of forms")))
    (let [bindings (mapv (fn [[nm val]] [(sym-name nm "loop binding name") (lower-expr val)])
                          (partition 2 binding-vec))
          body (mapv lower-expr (rest args))]
      (when (empty? body)
        (throw (err/lower-error "loop requires at least one body expression")))
      {:node :loop :bindings bindings :body body})))

(defn- lower-recur [args]
  {:node :recur :args (mapv lower-expr args)})

(defn- lower-do [args]
  {:node :do :body (mapv lower-expr args)})

(defn- lower-if-not
  "(if-not c then else) ≡ (if c else then) — no `not` needed, just swap arms."
  [args]
  (when-not (= (count args) 3)
    (throw (err/lower-error "if-not takes: (if-not cond then else)")))
  {:node :if
   :cond (lower-expr (nth args 0))
   :then (lower-expr (nth args 2))
   :else (lower-expr (nth args 1))})

(defn- lower-when-not
  "(when-not c body…) ≡ (if c 0 (do body…))"
  [args]
  (when (empty? args)
    (throw (err/lower-error "when-not takes: (when-not cond body…)")))
  {:node :if
   :cond (lower-expr (first args))
   :then {:node :int :value 0}
   :else {:node :do :body (mapv lower-expr (rest args))}})

(defn- lower-case
  [args]
  (when (empty? args)
    (throw (err/lower-error "case takes: (case expr v1 e1 … [default])")))
  (let [subject (first args)
        rest-args (vec (rest args))
        has-default (odd? (count rest-args))
        default-expr (if has-default (lower-expr (last rest-args)) {:node :int :value 0})
        pairs (vec (if has-default (butlast rest-args) rest-args))]
    (loop [chunks (reverse (partition 2 pairs)) acc default-expr]
      (if (empty? chunks)
        acc
        (let [[v result] (first chunks)
              test {:node :builtin :op :eq :args [(lower-expr subject) (lower-expr v)]}]
          (recur (rest chunks)
                 {:node :if :cond test :then (lower-expr result) :else acc}))))))

(defn- thread-edn
  "Thread an accumulator EDN value into a step AT THE EDN LEVEL, returning the
  rewritten form. Done pre-lowering (not on lowered Exprs) so special-form
  steps — (clamp …), (case …), (min …), (cond-> …) — go back through
  lower-call and desugar correctly, instead of being mis-lowered to a bare
  call. Mirrors `thread_edn` (ast.rs:877-891)."
  [step acc first?]
  (cond
    (seq? step) (let [v (vec step)]
                  (seq (if first? (into (conj (subvec v 0 1) acc) (subvec v 1))
                           (conj v acc))))
    (symbol? step) (list step acc)
    :else (throw (err/lower-error (str "-> / ->> step must be a call or symbol, found " (pr-str step))))))

(defn- lower-thread
  [args first?]
  (when (empty? args)
    (throw (err/lower-error "-> / ->> takes: (-> x step…)")))
  (loop [acc (first args) steps (rest args)]
    (if (empty? steps)
      (lower-expr acc)
      (recur (thread-edn (first steps) acc first?) (rest steps)))))

(defn- binding-pair
  [args form]
  (let [b (first args)]
    (if (and (vector? b) (= (count b) 2))
      [(nth b 0) (nth b 1)]
      (throw (err/lower-error (str form " requires a [name expr] binding vector"))))))

(defn- lower-if-let
  "(if-let [name expr] then else?) ≡ (let [name expr] (if name then else))"
  [args]
  (let [[name-v expr-v] (binding-pair args "if-let")
        nm  (sym-name name-v "if-let binding name")
        val (lower-expr expr-v)
        then (if (>= (count args) 2)
               (lower-expr (nth args 1))
               (throw (err/lower-error "if-let needs a then branch")))
        els  (if (>= (count args) 3) (lower-expr (nth args 2)) {:node :int :value 0})]
    {:node :let :bindings [[nm val]]
     :body [{:node :if :cond {:node :var :name nm} :then then :else els}]}))

(defn- lower-when-let
  "(when-let [name expr] body…) ≡ (let [name expr] (if name (do body…) 0))"
  [args]
  (let [[name-v expr-v] (binding-pair args "when-let")
        nm  (sym-name name-v "when-let binding name")
        val (lower-expr expr-v)
        body (mapv lower-expr (rest args))]
    {:node :let :bindings [[nm val]]
     :body [{:node :if
             :cond {:node :var :name nm}
             :then {:node :do :body body}
             :else {:node :int :value 0}}]}))

(defn- lower-dotimes
  "(dotimes [i n] body…) — run body n times with i = 0..n-1.
  ≡ (let [n* n] (loop [i 0] (if (< i n*) (do body… (recur (inc i))) 0)))"
  [args]
  (let [[i-v n-v] (binding-pair args "dotimes")
        i (sym-name i-v "dotimes binding name")
        n (lower-expr n-v)
        nsym (engine-gensym "n")
        body0 (mapv lower-expr (rest args))
        body (conj body0 {:node :recur :args [{:node :builtin :op :inc :args [{:node :var :name i}]}]})]
    {:node :let
     :bindings [[nsym n]]
     :body [{:node :loop
             :bindings [[i {:node :int :value 0}]]
             :body [{:node :if
                     :cond {:node :builtin :op :lt :args [{:node :var :name i} {:node :var :name nsym}]}
                     :then {:node :do :body body}
                     :else {:node :int :value 0}}]}]}))

(defn- nest-lets
  "Fold a sequence of (name, value) rebindings into NESTED single-binding
  lets, so each value sees the previous binding of the same name
  (guaranteed-sequential shadowing) — the substrate for as-> and cond->.
  Mirrors `nest_lets` (ast.rs:970-976)."
  [bindings body]
  (reduce (fn [acc [nm val]] {:node :let :bindings [[nm val]] :body [acc]})
          body (reverse bindings)))

(defn- lower-as-thread
  "(as-> expr name form…) — rebind `name` through each form, returning the
  last value."
  [args]
  (when-not (>= (count args) 2)
    (throw (err/lower-error "as-> takes: (as-> expr name form…)")))
  (let [nm (sym-name (nth args 1) "as-> binding name")
        bindings (into [[nm (lower-expr (nth args 0))]]
                        (map (fn [form] [nm (lower-expr form)]))
                        (drop 2 args))]
    (nest-lets bindings {:node :var :name nm})))

(defn- lower-cond-thread
  "(cond-> expr t1 f1 …) — thread expr through f_i only when t_i is truthy
  (cond->> = thread-last)."
  [args first?]
  (when (empty? args)
    (throw (err/lower-error "cond-> takes: (cond-> expr test form…)")))
  (let [rest-args (vec (rest args))]
    (when (odd? (count rest-args))
      (throw (err/lower-error "cond-> requires test/form pairs")))
    (let [nm (engine-gensym "ct")
          sym (symbol nm)
          bindings (reduce
                    (fn [bindings [test-edn form-edn]]
                      (let [test (lower-expr test-edn)
                            threaded (lower-expr (thread-edn form-edn sym first?))]
                        (conj bindings
                              [nm {:node :if :cond test :then threaded
                                   :else {:node :var :name nm}}])))
                    [[nm (lower-expr (nth args 0))]]
                    (partition 2 rest-args))]
      (nest-lets bindings {:node :var :name nm}))))

(defn- lower-parity
  "(even? x) ≡ (= (mod x 2) 0) ; (odd? x) ≡ (not= (mod x 2) 0)"
  [args even?]
  (when-not (= (count args) 1)
    (throw (err/lower-error "even?/odd? takes one argument")))
  (let [m {:node :builtin :op :mod :args [(lower-expr (nth args 0)) {:node :int :value 2}]}]
    {:node :builtin :op (if even? :eq :noteq) :args [m {:node :int :value 0}]}))

(defn- lower-min-max
  "(min a b) ≡ (let [ta a tb b] (if (< ta tb) ta tb)) ; max uses >. Args bound
  once (no re-eval)."
  [args is-min?]
  (when-not (= (count args) 2)
    (throw (err/lower-error "min/max takes two arguments")))
  (let [op (if is-min? :lt :gt)
        ta (engine-gensym "m")
        tb (engine-gensym "m")]
    {:node :let
     :bindings [[ta (lower-expr (nth args 0))] [tb (lower-expr (nth args 1))]]
     :body [{:node :if
             :cond {:node :builtin :op op :args [{:node :var :name ta} {:node :var :name tb}]}
             :then {:node :var :name ta}
             :else {:node :var :name tb}}]}))

(defn- lower-clamp
  "(clamp x lo hi) ≡ (min (max x lo) hi) — all three bound once."
  [args]
  (when-not (= (count args) 3)
    (throw (err/lower-error "clamp takes: (clamp x lo hi)")))
  (let [tx (engine-gensym "c") tlo (engine-gensym "c")
        thi (engine-gensym "c") tlow (engine-gensym "c")
        maxv {:node :if
              :cond {:node :builtin :op :gt :args [{:node :var :name tx} {:node :var :name tlo}]}
              :then {:node :var :name tx}
              :else {:node :var :name tlo}}
        minv {:node :if
              :cond {:node :builtin :op :lt :args [{:node :var :name tlow} {:node :var :name thi}]}
              :then {:node :var :name tlow}
              :else {:node :var :name thi}}]
    {:node :let
     :bindings [[tx (lower-expr (nth args 0))] [tlo (lower-expr (nth args 1))] [thi (lower-expr (nth args 2))]]
     :body [{:node :let :bindings [[tlow maxv]] :body [minv]}]}))

(defn- lower-doseq-entities
  "`(doseq-entities [e tag] body…)` — iterate every entity tagged `tag`,
  binding each entity-id to `e` for the body. Desugars to a host-driven
  cursor loop:

    (let [it (query-begin tag)]
      (loop [e (query-next it)]
        (when (not= e -1)
          body…
          (recur (query-next it)))))

  Mirrors `lower_doseq_entities` (ast.rs:1173-1221)."
  [args]
  (when-not (>= (count args) 2)
    (throw (err/lower-error "doseq-entities requires: (doseq-entities [e tag] body…)")))
  (let [binding (first args)]
    (when-not (and (vector? binding) (= (count binding) 2))
      (throw (err/lower-error "doseq-entities binding must be `[entity-sym tag]`")))
    (let [evar (sym-name (nth binding 0) "doseq-entities entity binding")
          tag  (lower-expr (nth binding 1))
          it   (engine-gensym "it")
          next-call {:node :builtin :op :query-next :args [{:node :var :name it}]}
          body0 (mapv lower-expr (rest args))]
      (when (empty? body0)
        (throw (err/lower-error "doseq-entities requires at least one body form")))
      (let [body (conj body0 {:node :recur :args [next-call]})
            loop-expr {:node :loop
                       :bindings [[evar next-call]]
                       :body [{:node :if
                               :cond {:node :builtin :op :noteq
                                      :args [{:node :var :name evar} {:node :int :value -1}]}
                               :then {:node :do :body body}
                               :else {:node :int :value 0}}]}]
        {:node :let
         :bindings [[it {:node :builtin :op :query-begin :args [tag]}]]
         :body [loop-expr]}))))

;; ---------------------------------------------------------------------------
;; Builtin arity checking — mirrors `check_builtin_arity` (ast.rs:1223-1275)
;; ---------------------------------------------------------------------------

(defn- builtin-arity-ok? [op n]
  (case op
    (:not :inc :dec :abs :zero :pos :neg
     :str-len :bytes-alloc :bytes-len :bytes-finish
     :alloc :load64 :load32
     :f32-bits :bits-f32
     :despawn-entity
     :get-x :get-y :get-z :get-vx :get-vy :get-vz
     :get-rx :get-ry :get-rz :get-rw
     :play-sound :stop-sound
     :key-down :key-pressed :axis
     :rand-int :query-begin :query-next :count-tagged
     :rt-enable
     :spawn-entity) (= n 1)

    (:pointer-x :pointer-y :delta-ms :elapsed-ms :tick-n) (= n 0)

    :steam-unlock (= n 1)
    (:steam-set-stat :steam-rich-presence) (= n 2)

    (:store64 :store32 :byte-at :byte-append) (= n 2)

    :move-toward (= n 3)

    (:set-position :set-velocity :apply-impulse :apply-force
     :draw-mesh :spawn-particle :play-sound-at
     :nearest-tagged) (= n 4)

    :set-rotation (= n 5)
    :raycast (= n 6)
    :set-listener (= n 6)
    :draw-line (= n 7)

    :sub (>= n 1)
    (:add :mul :and :or) (>= n 1)
    (:bit-and :bit-or :bit-xor) (>= n 1)
    (:shl :shr-s) (= n 2)
    (:div :mod) (= n 2)
    (:eq :noteq :lt :gt :le :ge) (>= n 1)
    (:fadd :fmul) (>= n 1)
    (:fsub :fdiv) (>= n 2)
    (:flt :fgt :fle :fge :feq) (>= n 1)
    ;; unreachable in Rust's exhaustive match — treat unknown ops as an error
    false))

(defn- check-builtin-arity [op n]
  (when-not (builtin-arity-ok? op n)
    (throw (err/lower-error (str "builtin " op " called with wrong number of arguments (" n ")")))))

;; ---------------------------------------------------------------------------
;; Call / expression lowering — mirrors `lower_call` (ast.rs:755-820)
;; ---------------------------------------------------------------------------

(defn- lower-call [items]
  (let [head (list-head-symbol items)
        args (vec (rest items))]
    (case (name head)
      "if"    (lower-if args)
      "when"  (lower-when args)
      "let"   (lower-let args)
      "cond"  (lower-cond args)
      "loop"  (lower-loop args)
      "recur" (lower-recur args)
      "do"    (lower-do args)
      "if-not"   (lower-if-not args)
      "when-not" (lower-when-not args)
      "case"     (lower-case args)
      "->"       (lower-thread args true)
      "->>"      (lower-thread args false)
      "if-let"   (lower-if-let args)
      "when-let" (lower-when-let args)
      "dotimes"  (lower-dotimes args)
      "as->"     (lower-as-thread args)
      "cond->"   (lower-cond-thread args true)
      "cond->>"  (lower-cond-thread args false)
      "even?"    (lower-parity args true)
      "odd?"     (lower-parity args false)
      "min"      (lower-min-max args true)
      "max"      (lower-min-max args false)
      "clamp"    (lower-clamp args)
      "doseq-entities" (lower-doseq-entities args)
      ("atom-val" "deref")
      (do (when-not (= (count args) 1)
            (throw (err/lower-error "(atom-val name) takes exactly one argument")))
          {:node :atom-get :name (sym-name (nth args 0) "atom name")})
      "set-atom!"
      (do (when-not (= (count args) 2)
            (throw (err/lower-error "(set-atom! name value) takes exactly two arguments")))
          {:node :atom-set
           :name (sym-name (nth args 0) "atom name")
           :value (lower-expr (nth args 1))})
      "f32"
      (do (when-not (= (count args) 1)
            (throw (err/lower-error "(f32 val) takes exactly one argument")))
          (let [a (nth args 0)]
            (cond
              (and (number? a) (not (integer? a))) {:node :float :value (double a)}
              (integer? a) {:node :float :value (double a)}
              :else (throw (err/lower-error (str "(f32 …) argument must be a number, found " (pr-str a)))))))
      ;; default: builtin op or user-defined call
      (let [lowered (mapv lower-expr args)]
        (if-let [op (get builtin-name->op (name head))]
          (do (check-builtin-arity op (count lowered))
              {:node :builtin :op op :args lowered})
          {:node :call :name (sym->qualified head) :args lowered})))))

(defn lower-expr
  "Mirrors `lower_expr` (ast.rs:741-753)."
  [v]
  (cond
    (boolean? v) {:node :int :value (if v 1 0)}
    (integer? v) {:node :int :value (long v)}
    (float? v) {:node :float :value (double v)}
    (string? v) {:node :str :value v}
    (symbol? v) {:node :var :name (sym->qualified v)}
    (seq? v) (lower-call v)
    :else (throw (err/lower-error (str "unsupported expression: " (pr-str v))))))

(ns kotoba.engine-clj.interp
  "Reference interpreter for `kotoba.engine-clj.codegen`'s instruction IR.

  Stands in for `kami-engine-clj`'s Rust `src/run.rs` (a thin wasmtime
  runner used by `tests/exec.rs` and, alongside `wasmi`, by
  `tests/parity.rs`). Since this port's `codegen/compile` intentionally
  stops at a pre-byte-emission instruction IR rather than real `.wasm` bytes
  (see `kotoba.engine-clj.codegen`'s docstring — the byte-emission step is
  mechanical and left to a future host-adapter package), there is no
  `wasmtime`/`wasmi` to hand that IR to. This namespace closes that gap for
  testing purposes: it is a small stack-machine interpreter that executes
  the SAME instruction IR codegen produces, so the ported test suite proves
  codegen's control-flow lowering (block+loop+br for `loop`/`recur`,
  i64<->f32 boxing, comparison chains, `defatom` globals, …) actually
  computes the right values — not just that codegen didn't throw.

  ## Honest scope

  This is ONE reference implementation, not two independent backends. The
  original Rust `tests/parity.rs` proved wasmtime (JIT) and wasmi
  (interpreter) agree bit-for-bit on the SAME compiled bytes — a genuine
  two-backend hardware/dispatch-strategy parity check this port cannot
  reproduce (there is only one JVM interpreter here). What this namespace
  DOES prove, ported faithfully from `tests/exec.rs`'s and
  `tests/parity.rs`'s actual assertions, is that the compiler's *per-op
  semantics* — the exact expression each op was designed to compute — are
  correct. Host imports (scene/physics/input/render/audio/steam) are NOT
  implemented (`:kind :host-import` calls always throw); no test in this
  port's suite needs one, since the original `tests/exec.rs`/`tests/
  parity.rs` only ever exercised pure-guest expressions and `defatom`
  (no host calls either).

  ## Branch-depth semantics

  WASM's `br N` counts outward through EVERY enclosing structured
  construct — block, loop, AND `if` — not just block/loop (this compiler's
  `if`/`and`/`or`/`abs` lowering all open an `if` block that participates in
  this counting, matching `codegen.rs`'s `ctrl_depth` bookkeeping exactly).
  `exec-if` below therefore always decrements-and-rethrows a passing branch
  signal (this compiler never targets an `if`'s own label directly — only
  `recur` branches, always to an enclosing `loop`), `exec-loop` restarts the
  loop body when the signal's depth reaches 0, and `exec-block` delivers the
  carried value and exits when its depth reaches 0."
  (:require [kotoba.engine-clj.ast :as ast]
            [kotoba.engine-clj.codegen :as codegen]
            [kotoba.engine-clj.errors :as err]
            [kotoba.engine-clj.numerics :as num]))

;; ---------------------------------------------------------------------------
;; Flat instruction list -> nested structured tree
;;
;; A small, generic, reusable utility: group `:block`/`:loop`/`:if` … `:else`
;; … `:end` runs into nested tagged vectors. This is exactly the kind of
;; "mechanical instruction encoding" step this port's docs describe as
;; adapter-only — a real WASM binary reader does the same structuring when
;; decoding bytecode back into a control-flow tree. It carries no
;; language-specific semantic decisions of its own.
;; ---------------------------------------------------------------------------

(defn- parse-seq
  "Parse `instrs` until `:end`, `:else`, or exhaustion. Returns
  `[ops terminator rest]` where `terminator` is `:end`, `:else`, or `nil`."
  [instrs]
  (loop [instrs (seq instrs) ops []]
    (if (empty? instrs)
      [ops nil nil]
      (let [instr (first instrs) more (next instrs) op (first instr)]
        (case op
          :end  [ops :end more]
          :else [ops :else more]
          :block (let [[body _term rest2] (parse-seq more)]
                   (recur rest2 (conj ops [:block (second instr) body])))
          :loop  (let [[body _term rest2] (parse-seq more)]
                   (recur rest2 (conj ops [:loop (second instr) body])))
          :if (let [[then-body term1 rest2] (parse-seq more)]
                (if (= term1 :else)
                  (let [[else-body _term2 rest3] (parse-seq rest2)]
                    (recur rest3 (conj ops [:if (second instr) then-body else-body])))
                  (recur rest2 (conj ops [:if (second instr) then-body []]))))
          (recur more (conj ops instr)))))))

(defn structure
  "Flat instruction vector -> nested structured op tree."
  [instrs]
  (let [[ops term rest] (parse-seq instrs)]
    (when (or term (seq rest))
      (throw (err/run-error "unbalanced block/loop/if structure in instruction IR")))
    ops))

;; ---------------------------------------------------------------------------
;; Instance — globals (global 0 = heap pointer, 1.. = defatom cells),
;; byte-addressable linear memory (pre-seeded with the string-literal data
;; segment), and the WASM function-index space (host-imports, then guest
;; functions, then cabi_realloc — in exactly the order `codegen/compile`
;; assigned indices).
;; ---------------------------------------------------------------------------

(def ^:private memory-pages 4) ;; 4 x 64KiB — generous headroom for alloc/vec/map-prelude use

(defn- seed-memory [blob]
  (let [buf (vec (repeat (* memory-pages codegen/wasm-page) 0))]
    (if (seq blob)
      (reduce (fn [m [i b]] (assoc m (+ codegen/data-base i) b)) buf (map-indexed vector blob))
      buf)))

(defn instantiate
  "Instantiate a Module IR (`kotoba.engine-clj.codegen/compile` output) for
  execution.

  `host-fns` binds the `kami:engine@1.0.0` imports the module declares: a map
  from a host-import kind (`:host-import/scene-spawn`, ...) to a function of
  the instance and the popped arguments. Omit it and the interpreter behaves
  as before -- every host call raises. Any real game uses host imports, so a
  module compiled from a `logic.cljc` cannot run without this map; that is why
  it exists rather than being a stub.

  The number of arguments a host call pops comes from the import own
  `:param-kinds`, so an arity is never assumed."
  ([module] (instantiate module {}))
  ([module host-fns]
   {:module module
    :host-fns host-fns
    :globals (atom (into [(:heap-start module)] (map :init (:atoms module))))
    :memory  (atom (seed-memory (:blob (:literals module))))
    :call-table (into (into (mapv (fn [hi] {:kind :host-import
                                            :imp (:kind hi)
                                            :param-kinds (:param-kinds hi)
                                            :return-kind (:return-kind hi)})
                                  (:host-imports module))
                             (mapv (fn [f] {:kind :guest :name (:name f)}) (:functions module)))
                       [{:kind :cabi-realloc}])}))

(defn- find-function [module name]
  (or (first (filter #(= (:name %) name) (:functions module)))
      (throw (err/run-error (str "no such export: " name)))))

;; ---------------------------------------------------------------------------
;; Linear memory (little-endian, matching WASM)
;; ---------------------------------------------------------------------------

(defn- mem-read-bytes [instance addr n]
  (let [m @(:memory instance)]
    (mapv #(nth m (+ (long addr) %) 0) (range n))))

(defn- bytes->uint [bs]
  (reduce (fn [acc [i b]] (bit-or acc (bit-shift-left (long b) (* 8 (long i)))))
          0 (map-indexed vector bs)))

(defn- uint->bytes [v n]
  (mapv (fn [i] (bit-and (unsigned-bit-shift-right (long v) (* 8 i)) 0xff)) (range n)))

(defn- mem-write-bytes! [instance addr bs]
  (swap! (:memory instance)
         (fn [m] (reduce (fn [m [i b]] (assoc m (+ (long addr) (long i)) (long b))) m (map-indexed vector bs)))))

(defn- load-i32    [instance stack offset] (let [a (peek stack)] (conj (pop stack) (bytes->uint (mem-read-bytes instance (+ a offset) 4)))))
(defn- load-i32-u8 [instance stack offset] (let [a (peek stack)] (conj (pop stack) (long (nth @(:memory instance) (+ (long a) offset) 0)))))
(defn- load-i64    [instance stack offset] (let [a (peek stack)] (conj (pop stack) (bytes->uint (mem-read-bytes instance (+ a offset) 8)))))

(defn- store-i32    [instance stack offset]
  (let [v (peek stack) s1 (pop stack) a (peek s1) s2 (pop s1)]
    (mem-write-bytes! instance (+ a offset) (uint->bytes v 4)) s2))
(defn- store-i32-u8 [instance stack offset]
  (let [v (peek stack) s1 (pop stack) a (peek s1) s2 (pop s1)]
    (mem-write-bytes! instance (+ a offset) [(bit-and (long v) 0xff)]) s2))
(defn- store-i64    [instance stack offset]
  (let [v (peek stack) s1 (pop stack) a (peek s1) s2 (pop s1)]
    (mem-write-bytes! instance (+ a offset) (uint->bytes v 8)) s2))

;; ---------------------------------------------------------------------------
;; Value-stack helpers
;; ---------------------------------------------------------------------------

(defn- bin [stack f]
  (let [b (peek stack) s1 (pop stack) a (peek s1) s2 (pop s1)]
    (conj s2 (f a b))))

(defn- un [stack f]
  (conj (pop stack) (f (peek stack))))

(declare exec-seq invoke)

(defn host-arity
  "Stack slots a host import consumes. Every kind is one i64 slot except
  :string-handle, which the codegen passes as (ptr, len) — two slots."
  [param-kinds]
  (reduce + 0 (map #(if (= :string-handle %) 2 1) param-kinds)))

(defn- exec-simple
  "Execute one non-structural instruction, returning the updated stack."
  [instance locals instr stack]
  (case (first instr)
    :i64-const (conj stack (long (second instr)))
    :i32-const (conj stack (bit-and (long (second instr)) 0xFFFFFFFF))
    :f32-const (conj stack (float (second instr)))
    :local-get (conj stack (nth @locals (second instr)))
    :local-set (do (swap! locals assoc (second instr) (peek stack)) (pop stack))
    :local-tee (do (swap! locals assoc (second instr) (peek stack)) stack)
    :global-get (conj stack (nth @(:globals instance) (second instr)))
    :global-set (do (swap! (:globals instance) assoc (second instr) (peek stack)) (pop stack))
    :drop (pop stack)
    :unreachable (throw (err/run-error "unreachable instruction executed"))
    :i64-add (bin stack unchecked-add)
    :i64-sub (bin stack unchecked-subtract)
    :i64-mul (bin stack unchecked-multiply)
    :i64-div-s (bin stack (fn [a b] (if (zero? b) (throw (err/run-error "i64.div_s by zero")) (quot (long a) (long b)))))
    :i64-rem-s (bin stack (fn [a b] (if (zero? b) (throw (err/run-error "i64.rem_s by zero")) (rem (long a) (long b)))))
    ;; 64-bit, not 32: on ClojureScript the bitwise operators coerce to 32
    ;; bits and drop the high half silently. See kotoba.engine-clj.numerics.
    :i64-and (bin stack num/and64)
    :i64-or  (bin stack num/or64)
    :i64-xor (bin stack num/xor64)
    :i64-shl (bin stack num/shl64)
    :i64-shr-s (bin stack num/shr-s64)
    :i64-shr-u (bin stack num/shr-u64)
    :i64-eq (bin stack (fn [a b] (if (= a b) 1 0)))
    :i64-ne (bin stack (fn [a b] (if (not= a b) 1 0)))
    :i64-lt-s (bin stack (fn [a b] (if (< (long a) (long b)) 1 0)))
    :i64-gt-s (bin stack (fn [a b] (if (> (long a) (long b)) 1 0)))
    :i64-le-s (bin stack (fn [a b] (if (<= (long a) (long b)) 1 0)))
    :i64-ge-s (bin stack (fn [a b] (if (>= (long a) (long b)) 1 0)))
    :i64-eqz (un stack (fn [a] (if (zero? a) 1 0)))
    :i64-extend-i32-u stack ;; identity — our i32 repr is already zero-extended
    :i32-wrap-i64 (un stack (fn [a] (bit-and (long a) 0xFFFFFFFF)))
    :i32-add (bin stack (fn [a b] (bit-and (+ (long a) (long b)) 0xFFFFFFFF)))
    :i32-sub (bin stack (fn [a b] (bit-and (- (long a) (long b)) 0xFFFFFFFF)))
    :i32-and (bin stack (fn [a b] (bit-and (long a) (long b))))
    :i32-load    (load-i32    instance stack (nth instr 1))
    :i32-load8-u (load-i32-u8 instance stack (nth instr 1))
    :i32-store   (store-i32   instance stack (nth instr 1))
    :i32-store8  (store-i32-u8 instance stack (nth instr 1))
    :i64-load    (load-i64    instance stack (nth instr 1))
    :i64-store   (store-i64   instance stack (nth instr 1))
    :f32-reinterpret-i32 (un stack (fn [a] (num/bits->f32 a)))
    :i32-reinterpret-f32 (un stack (fn [a] (num/f32-bits a)))
    :f32-add (bin stack (fn [a b] (float (+ (double a) (double b)))))
    :f32-sub (bin stack (fn [a b] (float (- (double a) (double b)))))
    :f32-mul (bin stack (fn [a b] (float (* (double a) (double b)))))
    :f32-div (bin stack (fn [a b] (float (/ (double a) (double b)))))
    :f32-lt (bin stack (fn [a b] (if (< (double a) (double b)) 1 0)))
    :f32-gt (bin stack (fn [a b] (if (> (double a) (double b)) 1 0)))
    :f32-le (bin stack (fn [a b] (if (<= (double a) (double b)) 1 0)))
    :f32-ge (bin stack (fn [a b] (if (>= (double a) (double b)) 1 0)))
    :f32-eq (bin stack (fn [a b] (if (= (double a) (double b)) 1 0)))
    :call (let [idx (second instr)
                entry (nth (:call-table instance) idx)
                arity (case (:kind entry)
                        :guest (count (:params (find-function (:module instance) (:name entry))))
                        :cabi-realloc 4
                        ;; was hard-coded 0, which popped no arguments and
                        ;; silently handed the host an empty list. Note a
                        ;; :string-handle occupies TWO stack slots (ptr, len),
                        ;; so this is not `count`: getting that wrong pops one
                        ;; value too few and the imbalance only shows up at the
                        ;; end of the enclosing function, far from the call.
                        :host-import (host-arity (:param-kinds entry)))
                n (count stack)
                args (subvec stack (max 0 (- n arity)))
                stack' (subvec stack 0 (max 0 (- n arity)))
                r (invoke instance idx (vec args))]
            ;; a void call pushes nothing, exactly as in wasm. Pushing a
            ;; placeholder here is what left extra values on the stack and
            ;; made every real game fail `run-body` -- the failure surfaced
            ;; far from the cause, at the end of the function.
            (if (and (= :host-import (:kind entry)) (= :void (:return-kind entry)))
              stack'
              (conj stack' r)))
    :br (throw (ex-info "branch" {::branch-depth (second instr) ::branch-value (peek stack)}))
    (throw (err/run-error (str "unimplemented instruction in reference interpreter: " (first instr))))))

;; ---------------------------------------------------------------------------
;; Structured control-flow execution
;; ---------------------------------------------------------------------------

#?(:clj (def ^:private ex-info-class clojure.lang.ExceptionInfo)
   :cljs (def ^:private ex-info-class ExceptionInfo))

(defn- branch-depth [e]
  (when (instance? ex-info-class e) (::branch-depth (ex-data e))))

(defn- exec-if [instance locals _ty then-body else-body stack]
  (let [cond-val (peek stack) stack' (pop stack)
        body (if (not (zero? cond-val)) then-body else-body)]
    (try
      (exec-seq instance locals body stack')
      (catch #?(:clj Throwable :cljs :default) e
        (if-let [_d (branch-depth e)]
          (throw (ex-info "branch" (update (ex-data e) ::branch-depth dec)))
          (throw e))))))

(defn- exec-block [instance locals _ty body stack]
  (try
    (exec-seq instance locals body stack)
    (catch #?(:clj Throwable :cljs :default) e
      (if-let [d (branch-depth e)]
        (if (zero? d)
          (conj stack (::branch-value (ex-data e)))
          (throw (ex-info "branch" (update (ex-data e) ::branch-depth dec))))
        (throw e)))))

(defn- exec-loop [instance locals _ty body stack]
  (loop []
    (let [outcome (try {:stack (exec-seq instance locals body stack)}
                        (catch #?(:clj Throwable :cljs :default) e
                          (if-let [d (branch-depth e)]
                            (if (zero? d)
                              {:continue true}
                              (throw (ex-info "branch" (update (ex-data e) ::branch-depth dec))))
                            (throw e))))]
      (if (:continue outcome) (recur) (:stack outcome)))))

(defn- exec-op [instance locals op stack]
  (case (first op)
    :block (exec-block instance locals (second op) (nth op 2) stack)
    :loop  (exec-loop  instance locals (second op) (nth op 2) stack)
    :if    (exec-if    instance locals (second op) (nth op 2) (nth op 3) stack)
    (exec-simple instance locals op stack)))

(defn- exec-seq [instance locals ops stack]
  (reduce (fn [stack op] (exec-op instance locals op stack)) stack ops))

;; ---------------------------------------------------------------------------
;; Function invocation
;; ---------------------------------------------------------------------------

(defn- run-body [instance locals structured]
  (let [stack (exec-seq instance locals structured [])]
    (if (= (count stack) 1)
      (first stack)
      (throw (err/run-error (str "function body left " (count stack) " values on the stack, expected 1"))))))

(defn- invoke [instance idx args]
  (let [entry (nth (:call-table instance) idx)]
    (case (:kind entry)
      :guest (let [f (find-function (:module instance) (:name entry))
                   locals (atom (into (vec args) (repeat (- (:locals-count f) (count args)) 0)))]
               (run-body instance locals (structure (:body f))))
      :cabi-realloc (let [locals (atom (vec args))]
                       (run-body instance locals (structure (:body (:cabi-realloc (:module instance))))))
      :host-import (if-let [f (get (:host-fns instance) (:imp entry))]
                     (apply f instance args)
                     (throw (err/run-error
                              (str "host import " (:imp entry) " was called but no host function "
                                   "is bound for it -- pass one to `instantiate`")))))))

(defn call-export
  "Execute exported function `name` with i64 `args`, returning its i64
  result. The primary entry point — general (any exported function), unlike
  Rust's `run::eval_i64` (which only ever wraps a single probe expression)."
  [instance name args]
  (let [f (find-function (:module instance) name)]
    (when-not (= (count args) (count (:params f)))
      (throw (err/run-error
              (str "function `" name "` called with " (count args) " args, expected " (count (:params f))))))
    (let [locals (atom (into (vec args) (repeat (- (:locals-count f) (count args)) 0)))]
      (run-body instance locals (structure (:body f))))))

(defn read-global
  "Read exported WASM global `name` (a `defatom` cell) by name — mirrors
  `wasmtime::Instance::get_global`, used by the `defatom`-export test."
  [instance name]
  (let [module (:module instance)
        idx (get (:export-globals module) name)]
    (when (nil? idx)
      (throw (err/run-error (str "no such exported global: " name))))
    (nth @(:globals instance) idx)))

(defn run-init-headless
  "Instantiate `module` and call its `init` export (if present) with no host
  imports bound. Mirrors `run::run_init_headless` (run.rs:13-28). Modules
  whose `init` calls a host import will throw (unimplemented import) here,
  matching the Rust original's \"expected trap for full-engine-only modules\"
  caveat."
  [module]
  (let [instance (instantiate module)]
    (when (some #(= (:name %) "init") (:functions module))
      (call-export instance "init" []))
    nil))

;; ---------------------------------------------------------------------------
;; Execution-grade test seam — mirrors `run::eval_i64` / `run::eval_f32`
;; (run.rs:36-61). JVM-only: relies on `ast/parse-program-str`'s reader.
;; ---------------------------------------------------------------------------

#?(:clj
   (defn eval-i64
     "Compile `(defn __probe [] <expr>)` and run it, returning the i64 it
     computes. The difference between \"the compiler emitted some
     instructions\" and \"the compiled program computes the right value\" —
     the latter is what catches codegen bugs like an unsound multi-arg `=`
     or a comparison chain that drops its tail operands."
     [expr-src]
     (let [program (ast/parse-program-str (str "(defn __probe [] " expr-src ")"))
           module (codegen/compile program)
           instance (instantiate module)]
       (call-export instance "__probe" []))))

#?(:clj
   (defn eval-f32
     "Like `eval-i64`, but decode the result as the f32 bit-pattern it
     boxes — for asserting the value of guest float expressions
     (`+f`/`-f`/`*f`/`/f`)."
     [expr-src]
     (num/bits->f32 (eval-i64 expr-src))))

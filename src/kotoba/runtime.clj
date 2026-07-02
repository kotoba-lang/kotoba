(ns kotoba.runtime
  "Small CLJ-owned Kotoba execution core.

  This is the first Rust-free executable slice: it reads Kotoba-family source
  with an explicit reader target, checks a strict pure subset, emits deterministic
  EDN IR, and can run a zero-arity `main` function."
  (:require [clojure.java.io :as io]
            [clojure.string :as str]
            [kotoba.core.contracts :as core-contracts]
            [kotoba.lang.capability-values :as capability-values]
            [clojure.tools.reader :as reader]
            [clojure.tools.reader.reader-types :as reader-types]))

(def builtin-fns
  {'+ +
   '- -
   '* *
   '/ /
   'quot quot
   'mod mod
   'rem rem
   'inc inc
   'dec dec
   'min min
   'max max
   'i64 long
   'i64+ +
   'i64- -
   'i64* *
   'host-i64-roundtrip identity
   'call-indirect (fn [_idx arg] arg)
   '= =
   '< <
   '> >
   '<= <=
   '>= >=
   'zero? zero?
   'pos? pos?
   'neg? neg?
   'not not
   'alloc (constantly 0)
   'alloc-checked (constantly 0)
   'str-ptr (constantly 0)
   'bytes-ptr (constantly 0)
   'str-len (fn [s] (count (.getBytes (str s) "UTF-8")))
   'bytes-len count
   'memory-pages (constantly 1)
   'memory-grow (fn [pages] 1)
   'mem-byte-at (fn [_ptr _idx] 0)
   'mem-i32-at (fn [_ptr _offset] 0)
   'byte-store! (fn [_ptr _idx value] value)
   'i32-store! (fn [_ptr _offset value] value)
   'result-ok? (fn [value] (not (neg? value)))
   'result-err? neg?
   'result-write! (fn [record-ptr value] record-ptr)
   'result-status (fn [_record-ptr] 0)
   'result-value (fn [_record-ptr] 0)
   'byte-at (fn [value idx]
              (let [bytes (if (string? value)
                            (mapv #(bit-and % 0xff) (.getBytes value "UTF-8"))
                            (vec value))]
                (nth bytes idx)))
   'str str
   'count count
   'keyword keyword
   'name name})

(def capability-contract
  (core-contracts/capability-contract))

(def special-forms
  (:special-forms capability-contract))

(defn read-forms
  "Read every form from source using a concrete CLJC reader target."
  [source reader-target]
  (let [rdr (reader-types/string-push-back-reader source)
        opts {:read-cond :allow
              :features #{reader-target}
              :eof ::eof}]
    (loop [forms []]
      (let [form (reader/read opts rdr)]
        (if (= ::eof form)
          forms
          (recur (conj forms form)))))))

(defn read-file
  [path reader-target]
  (read-forms (slurp (io/file path)) reader-target))

(defn list-head
  [form]
  (when (seq? form)
    (first form)))

(defn walk-forms
  [f form]
  (f form)
  (cond
    (seq? form) (doseq [x form] (walk-forms f x))
    (map? form) (doseq [[k v] form]
                  (walk-forms f k)
                  (walk-forms f v))
    (coll? form) (doseq [x form] (walk-forms f x))))

(defn capability-name
  [value]
  (core-contracts/capability-name value))

(defn capability-id
  [value]
  (core-contracts/capability-id capability-contract value))

(def cap-passing-imports
  "S4b capability-passing extension of the host-import surface, owned by this
  launcher slice (the core capability contract stays authoritative for the
  base ops). `cap-acquire` intersects policy ∩ grants ∩ requested ONCE at the
  host boundary and returns an opaque i64 capability handle; the single
  demonstration use shape `host-i64-roundtrip-with` threads that handle as a
  first-class argument through compiled wasm and is resolved back to the
  stored concrete capability at host-call time."
  {'cap-acquire {:module "kotoba"
                 :field "cap_acquire"
                 :params [:i32 :i32 :i32]
                 :result :i64}
   'host-i64-roundtrip-with {:module "kotoba"
                             :field "host_i64_roundtrip_with"
                             :capability "ledger/append"
                             :params [:i64 :i64]
                             :result :i64}})

(def host-imports
  (merge (core-contracts/host-imports capability-contract)
         cap-passing-imports))

(def host-import-order
  (into (core-contracts/host-import-order capability-contract)
        ['cap-acquire 'host-i64-roundtrip-with]))

(def op->kind
  "Host-import op (capability contract symbol) -> capability kind understood
  by kotoba.lang.capability-values/effect-for-kind."
  {'notify-show :host/notify
   'clipboard-read :host/clipboard-read
   'clipboard-write :host/clipboard-write
   'clipboard-write-str :host/clipboard-write
   'http-fetch :host/http
   'keychain-read :host/keychain-read
   'keychain-write :host/keychain-write
   'fs-read :host/fs-read
   'fs-write :host/fs-write
   'host-i64-roundtrip :host/ledger-append})

(def with-op->op
  "Capability-passing use variant (`<op>-with`, leading argument a capability
  handle from `cap-acquire`) -> base host-import op."
  (into {} (map (fn [[op _]] [(symbol (str op "-with")) op])) op->kind))

(def op->with-op
  "Base host-import op -> its capability-passing `<op>-with` use variant."
  (into {} (map (fn [[with-op op]] [op with-op])) with-op->op))

(def kind->capability
  "Capability kind -> contract capability name, derived from op->kind and the
  host-import contract."
  (into {}
        (keep (fn [[op kind]]
                (when-let [cap (get-in host-imports [op :capability])]
                  [kind cap])))
        op->kind))

(defn policy-capabilities
  [policy]
  (core-contracts/policy-capabilities policy))

(defn required-capabilities
  [forms]
  (let [caps (atom [])]
    (doseq [form forms]
      (walk-forms
       (fn [node]
         (when (seq? node)
           (let [op (first node)]
             (cond
               (= 'has-capability? op)
               (swap! caps conj (second node))

               (= 'cap-acquire op)
               (when-let [cap (get kind->capability (second node))]
                 (swap! caps conj cap))

               (contains? with-op->op op)
               (swap! caps conj (get-in host-imports
                                        [(get with-op->op op) :capability]))

               (get-in host-imports [op :capability])
               (swap! caps conj (get-in host-imports [op :capability]))))))
       form))
    (vec @caps)))

(defn required-host-imports
  [forms]
  (let [imports (atom #{})]
    (doseq [form forms]
      (walk-forms
       (fn [node]
         (when (and (seq? node) (contains? host-imports (first node)))
           (swap! imports conj (first node))))
       form))
    (vec (filter @imports host-import-order))))

(defn source-problems
  "Return safety/type problems for the current executable subset."
  ([safe-facts forms] (source-problems safe-facts forms nil))
  ([safe-facts forms policy]
  (let [denied (set (remove #{"ns"} (:non-executable-forms safe-facts)))
        effect-ops (set (:effect-ops safe-facts))
        allowed-caps (policy-capabilities policy)
        problems (atom [])]
    (doseq [form forms]
      (walk-forms
       (fn [node]
         (when-let [head (some-> node list-head str)]
           (cond
             (denied head)
             (swap! problems conj {:kotoba.runtime/problem :denied-form
                                   :kotoba.runtime/form head})

             (= "cap-acquire" head)
             (let [kind (second node)
                   cap-name (get kind->capability kind)]
               (cond
                 (nil? cap-name)
                 (swap! problems conj {:kotoba.runtime/problem :unknown-capability-kind
                                       :kotoba.runtime/kind (pr-str kind)})

                 (not (contains? allowed-caps cap-name))
                 (swap! problems conj {:kotoba.runtime/problem :capability-not-granted
                                       :kotoba.runtime/capability cap-name})))

             (contains? with-op->op (first node))
             (let [cap-name (get-in host-imports
                                    [(get with-op->op (first node)) :capability])]
               (when-not (contains? allowed-caps cap-name)
                 (swap! problems conj {:kotoba.runtime/problem :capability-not-granted
                                       :kotoba.runtime/capability cap-name})))

             (contains? host-imports (first node))
             (let [op (first node)
                   cap (or (get-in host-imports [op :capability])
                           (second node))
                   cap-name (capability-name cap)]
               (cond
                 (nil? (capability-id cap))
                 (swap! problems conj {:kotoba.runtime/problem :unknown-capability
                                       :kotoba.runtime/capability cap-name})

                 (not (contains? allowed-caps cap-name))
                 (swap! problems conj {:kotoba.runtime/problem :capability-not-granted
                                       :kotoba.runtime/capability cap-name})))

             (effect-ops head)
             (swap! problems conj {:kotoba.runtime/problem :host-effect-requires-capability
                                   :kotoba.runtime/form head}))))
       form))
    @problems)))

(declare eval-form)

(defn truthy?
  [value]
  (not (or (false? value) (nil? value))))

(defn bind-params
  [params args]
  (when-not (= (count params) (count args))
    (throw (ex-info "arity mismatch" {:params params :args args})))
  (zipmap params args))

(defn eval-body
  [forms env fns]
  (reduce (fn [_ form] (eval-form form env fns)) nil forms))

(defn call-fn
  [f args fns]
  (cond
    (and (map? f) (= :kotoba.runtime/fn (:kind f)))
    (eval-body (:body f) (bind-params (:params f) args) fns)

    (ifn? f)
    (apply f args)

    :else
    (throw (ex-info "not callable" {:callee f :args args}))))

(defn eval-form
  [form env fns]
  (cond
    (symbol? form)
    (cond
      (contains? env form) (get env form)
      (contains? fns form) (get fns form)
      (contains? builtin-fns form) (get builtin-fns form)
      :else (throw (ex-info "unknown symbol" {:symbol form})))

    (or (number? form) (string? form) (keyword? form) (boolean? form) (nil? form))
    form

    (vector? form)
    (mapv #(eval-form % env fns) form)

    (map? form)
    (into {} (map (fn [[k v]] [(eval-form k env fns) (eval-form v env fns)])) form)

    (seq? form)
    (let [[op & args] form]
      (case op
        ns nil
        quote (first args)
        do (eval-body args env fns)
        let (let [[bindings & body] args
                  env' (reduce (fn [acc [k v]]
                                 (assoc acc k (eval-form v acc fns)))
                               env
                               (partition 2 bindings))]
              (eval-body body env' fns))
        if (let [[test then else] args]
             (if (truthy? (eval-form test env fns))
               (eval-form then env fns)
               (eval-form else env fns)))
        def (let [[_name value] args]
              (eval-form value env fns))
        defn nil
        (call-fn (eval-form op env fns)
                 (mapv #(eval-form % env fns) args)
                 fns)))

    :else
    (throw (ex-info "unsupported literal" {:form form}))))

(defn function-def
  [form]
  (when (and (seq? form) (= 'defn (first form)))
    (let [[_ name params & body] form]
      [name {:kind :kotoba.runtime/fn
             :name name
             :params (vec params)
             :body (vec body)}])))

(defn compile-forms
  "Compile checked forms to deterministic EDN IR."
  [source-plan forms]
  (let [fns (into {} (keep function-def forms))
        expressions (vec (remove #(and (seq? %) (#{'ns 'defn} (first %))) forms))]
    {:schema "kotoba.runtime.edn-ir.v0"
     :kotoba.runtime/source-plan source-plan
     :kotoba.runtime/exports (vec (sort (map (comp str key) fns)))
     :kotoba.runtime/forms (pr-str forms)
     :kotoba.runtime/expression-count (count expressions)
     :kotoba.runtime/fn-count (count fns)}))

(defn- acquired-kinds
  "Capability kinds acquired (`cap-acquire`) or used through a capability
  handle (`<op>-with`) anywhere inside FORM."
  [form]
  (let [kinds (atom [])]
    (walk-forms
     (fn [node]
       (when (seq? node)
         (let [op (first node)]
           (cond
             (= 'cap-acquire op)
             (swap! kinds conj (second node))

             (contains? with-op->op op)
             (swap! kinds conj (get op->kind (get with-op->op op)))))))
     form)
    (vec (distinct @kinds))))

;; ---------------------------------------------------------------------------
;; Typed capability parameters (S4b)

(defn cap-param-kind
  "Capability kind declared on a parameter symbol through the canonical
  `^{:cap <kind-kw>}` metadata form (e.g.
  `(defn use-ledger [^{:cap :host/ledger-append} c ^:i64 code] ...)`),
  or nil for an untyped parameter. This is the ONE metadata form: kind
  keywords are themselves namespaced (`:host/ledger-append`), so a
  `^:cap/<kind>` reader shorthand cannot spell them and is not accepted."
  [sym]
  (:cap (meta sym)))

(declare function-defs symbol-key)

(defn- cap-expr-kind
  "Static capability kind of EXPR under CAP-ENV (local symbol -> kind), or
  nil when EXPR is not statically known to carry a capability. Recognized
  cap-typed expressions in this slice: the direct result of
  `(cap-acquire <kind> ...)`, a `^{:cap <kind>}` typed parameter, and a
  let-bound alias of either."
  [cap-env expr]
  (cond
    (and (seq? expr) (= 'cap-acquire (first expr))) (second expr)
    (symbol? expr) (get cap-env (symbol-key expr))
    :else nil))

(defn- cap-arg-problem
  "Problem for one call-site argument position that requires a capability of
  EXPECTED kind, or nil when ARG statically satisfies it."
  [fn-name op cap-env expected arg]
  (let [actual (cap-expr-kind cap-env arg)]
    (cond
      (nil? actual)
      {:kotoba.runtime/problem :cap-arg-not-capability
       :kotoba.runtime/fn (str fn-name)
       :kotoba.runtime/op (str op)
       :kotoba.runtime/arg (pr-str arg)}

      (not= expected actual)
      {:kotoba.runtime/problem :cap-kind-mismatch
       :kotoba.runtime/fn (str fn-name)
       :kotoba.runtime/op (str op)
       :kotoba.runtime/expected expected
       :kotoba.runtime/actual actual})))

(defn- cap-use-problems
  "Static typed-capability problems inside EXPR (one expression of FN-NAME's
  body). CAP-ENV maps local symbols to capability kinds; FN-PARAM-KINDS maps
  user fn name -> vector of its declared param cap kinds (nil entries for
  untyped params), so the checks hold across the direct call graph."
  [fn-name cap-env fn-param-kinds expr]
  (letfn [(check-all [cap-env exprs]
            (vec (mapcat #(check cap-env %) exprs)))
          (check [cap-env expr]
            (if-not (seq? expr)
              []
              (let [[op & args] expr]
                (case op
                  (quote ns defn) []
                  def (check-all cap-env (rest args))
                  (do if) (check-all cap-env args)
                  let (let [[bindings & body] args]
                        (loop [pairs (partition 2 bindings)
                               cap-env cap-env
                               problems []]
                          (if-let [[binding value] (first pairs)]
                            (recur (next pairs)
                                   (if-let [kind (cap-expr-kind cap-env value)]
                                     (assoc cap-env (symbol-key binding) kind)
                                     (dissoc cap-env (symbol-key binding)))
                                   (into problems (check cap-env value)))
                            (into problems (check-all cap-env body)))))
                  ;; call site
                  (let [problems (check-all cap-env args)]
                    (cond
                      ;; `<op>-with` first argument must be cap-typed and of
                      ;; the op's kind.
                      (contains? with-op->op op)
                      (if-let [problem (cap-arg-problem
                                        fn-name op cap-env
                                        (get op->kind (get with-op->op op))
                                        (first args))]
                        (conj problems problem)
                        problems)

                      ;; direct call to a user fn: cap-typed params require
                      ;; cap-typed arguments of the same kind.
                      (contains? fn-param-kinds op)
                      (into problems
                            (remove nil?)
                            (map (fn [expected arg]
                                   (when expected
                                     (cap-arg-problem fn-name op cap-env
                                                      expected arg)))
                                 (get fn-param-kinds op)
                                 args))

                      :else problems))))))]
    (check cap-env expr)))

(defn cap-typed-problems
  "Static S4b typed-capability-parameter checks, run at check/emit time next
  to the effect gate:

  - a `^{:cap <kind>}` param kind must be a known capability kind
    (:unknown-capability-kind — kotoba.lang.capability-values/effect-for-kind
    is the vocabulary);
  - the first argument of every `<op>-with` use must be cap-typed — the
    direct result of `(cap-acquire ...)`, a cap-typed param, or a let-bound
    alias — never an untyped/forgeable integer (:cap-arg-not-capability);
  - the cap-typed value's kind must match the op's kind, and a cap-typed
    argument passed to a user fn must match the callee's declared param kind
    (:cap-kind-mismatch), across the direct call graph."
  [forms]
  (let [defs (function-defs forms)
        fn-param-kinds (into {}
                             (map (fn [[fname f]]
                                    [fname (mapv cap-param-kind (:params f))]))
                             defs)
        param-problems
        (vec (for [[fname f] defs
                   param (:params f)
                   :let [kind (cap-param-kind param)]
                   :when (and (some? kind)
                              (not (contains? capability-values/effect-for-kind
                                              kind)))]
               {:kotoba.runtime/problem :unknown-capability-kind
                :kotoba.runtime/fn (str fname)
                :kotoba.runtime/kind (pr-str kind)}))
        body-problems
        (vec (mapcat
              (fn [form]
                (if-let [[fname f] (function-def form)]
                  (let [cap-env (into {}
                                      (keep (fn [param]
                                              (when-let [kind (cap-param-kind param)]
                                                [(symbol-key param) kind])))
                                      (:params f))]
                    (mapcat #(cap-use-problems fname cap-env fn-param-kinds %)
                            (:body f)))
                  (cap-use-problems 'top-level {} fn-param-kinds form)))
              forms))]
    (into param-problems body-problems)))

(defn- direct-callees
  "User fn names (from FN-NAMES) called anywhere inside BODY."
  [fn-names body]
  (let [found (atom #{})]
    (doseq [form body]
      (walk-forms
       (fn [node]
         (when (and (seq? node) (contains? fn-names (first node)))
           (swap! found conj (first node))))
       form))
    @found))

(defn fn-required-cap-kinds
  "Map of user fn name -> set of capability kinds the fn requires: kinds its
  body acquires (`cap-acquire`) or uses through a handle (`<op>-with`), kinds
  of its `^{:cap <kind>}` typed params, plus — interprocedurally, closing a
  fixpoint over direct calls — everything its callees require. A caller
  passing its own cap param through to a callee therefore inherits the
  requirement."
  [forms]
  (let [defs (function-defs forms)
        names (set (map first defs))
        own (into {}
                  (map (fn [[fname f]]
                         [fname (into (set (acquired-kinds (:body f)))
                                      (keep cap-param-kind)
                                      (:params f))]))
                  defs)
        callees (into {}
                      (map (fn [[fname f]]
                             [fname (direct-callees names (:body f))]))
                      defs)]
    (loop [required own]
      (let [advanced (into {}
                           (map (fn [[fname kinds]]
                                  [fname (into kinds
                                               (mapcat #(get required % #{}))
                                               (get callees fname))]))
                           required)]
        (if (= advanced required)
          required
          (recur advanced))))))

(defn cap-effect-problems
  "S4b effect/capability consistency: when a `defn` declares an :effects row
  (metadata on the function name), every capability kind it requires — body
  `cap-acquire`/`<op>-with` kinds, `^{:cap <kind>}` typed param kinds, and,
  through the fn-required-cap-kinds fixpoint over direct calls, everything
  its callees require — must be covered by the row
  (kotoba.lang.capability-values/effects-consistent?). Under-declaration is
  rejected; functions without a declared row are not checked by this slice."
  [forms]
  (let [required (fn-required-cap-kinds forms)]
    (vec
     (for [form forms
           :when (and (seq? form) (= 'defn (first form)))
           :let [[_ fn-name] form
                 row (:effects (meta fn-name))]
           :when (some? row)
           :let [kinds (get required fn-name)
                 checked (capability-values/effects-consistent?
                          row (map (fn [kind] {:cap/kind kind}) kinds))]
           :when (not (:ok? checked))]
       {:kotoba.runtime/problem :cap-effect-under-declared
        :kotoba.runtime/fn (str fn-name)
        :kotoba.runtime/missing (:missing checked)}))))

(defn check
  ([safe-facts source-plan forms] (check safe-facts source-plan forms nil))
  ([safe-facts source-plan forms policy]
  (let [problems (vec (concat (source-problems safe-facts forms policy)
                              (cap-typed-problems forms)
                              (cap-effect-problems forms)))
        ir (when (empty? problems)
             (compile-forms source-plan forms))]
    {:kotoba.runtime/ok? (empty? problems)
     :kotoba.runtime/problems problems
     :kotoba.runtime/ir ir})))

(defn- guarded-host-fns
  "Interpreter bindings routing every capability-bearing host-import op used
  by FORMS through HOST-CALL (fn [op args] result)."
  [forms host-call]
  (into {}
        (keep (fn [op]
                (when (and (get-in host-imports [op :capability])
                           (not (contains? with-op->op op)))
                  [op (fn [& args] (host-call op (vec args)))])))
        (required-host-imports forms)))

(defn run
  "Run FORMS through the CLJ interpreter slice.

  The optional OPTS map enables the capability-guarded host path (issue #263):
  {:policy           <policy EDN, used for the static capability check>
   :host-call        <fn [op args] -> result; every capability-bearing
                      host-import op is dispatched through it>
   :capability-query <fn [cap] -> boolean, bound as has-capability?>
   :host-fns         <map of extra interpreter bindings (symbol -> fn), used
                      by the S4b capability-passing surface: cap-acquire and
                      the <op>-with use variants>}

  Without OPTS behavior is unchanged: host-import ops are statically rejected
  as :capability-not-granted. With a guard installed, a denied host call
  (ex-info carrying :kotoba.host/denied) fails the run closed with a
  :host-call-denied problem; the provider is never invoked."
  ([safe-facts source-plan forms] (run safe-facts source-plan forms nil))
  ([safe-facts source-plan forms {:keys [policy host-call capability-query host-fns]}]
   (let [{:kotoba.runtime/keys [ok? problems ir]} (check safe-facts source-plan forms policy)
         fns (into {} (keep function-def forms))
         env-fns (cond-> fns
                   host-call (merge (guarded-host-fns forms host-call))
                   host-fns (merge host-fns)
                   (and host-call capability-query)
                   (assoc 'has-capability? capability-query))]
     (if-not ok?
       {:kotoba.runtime/ok? false
        :kotoba.runtime/problems problems
        :kotoba.runtime/ir ir}
       (try
         (let [expressions (vec (remove #(and (seq? %) (#{'ns 'defn} (first %))) forms))
               value (cond
                       (contains? fns 'main)
                       (call-fn (get fns 'main) [] env-fns)

                       (seq expressions)
                       (eval-body expressions {} env-fns)

                       :else
                       nil)]
           {:kotoba.runtime/ok? true
            :kotoba.runtime/value value
            :kotoba.runtime/ir ir})
         (catch clojure.lang.ExceptionInfo e
           (if (and host-call (:kotoba.host/denied (ex-data e)))
             {:kotoba.runtime/ok? false
              :kotoba.runtime/problems [{:kotoba.runtime/problem :host-call-denied
                                         :kotoba.runtime/call (:kotoba.host/call (ex-data e))
                                         :kotoba.runtime/denied (:kotoba.host/denied (ex-data e))}]
              :kotoba.runtime/ir ir}
             (throw e))))))))

(defn wasm-artifact
  "Emit deterministic bytes for the current IR contract.

  This is intentionally labeled as EDN IR, not a WebAssembly binary. A later
  emitter can replace the payload while keeping the checked source contract.
  "
  [ir]
  (.getBytes (pr-str ir) "UTF-8"))

(defn uleb
  "Unsigned LEB128 encoding."
  [n]
  (loop [value (long n)
         out []]
    (let [byte (bit-and value 0x7f)
          next-value (unsigned-bit-shift-right value 7)]
      (if (zero? next-value)
        (conj out byte)
        (recur next-value (conj out (bit-or byte 0x80)))))))

(defn sleb32
  "Signed LEB128 encoding for i32 constants."
  [n]
  (loop [value (long n)
         out []]
    (let [byte (bit-and value 0x7f)
          shifted (bit-shift-right value 7)
          sign-set? (pos? (bit-and byte 0x40))
          done? (or (and (zero? shifted) (not sign-set?))
                    (and (= -1 shifted) sign-set?))]
      (if done?
        (conj out byte)
        (recur shifted (conj out (bit-or byte 0x80)))))))

(defn bcat
  [& parts]
  (vec (mapcat identity parts)))

(defn utf8-bytes
  [s]
  (mapv #(bit-and % 0xff) (.getBytes (str s) "UTF-8")))

(defn literal-bytes
  [value]
  (cond
    (string? value) (utf8-bytes value)
    (and (vector? value)
         (seq value)
         (every? integer? value)) (mapv #(bit-and % 0xff) value)
    :else nil))

(defn collect-memory-literals
  [forms]
  (let [literals (atom [])]
    (doseq [form forms]
      (walk-forms
       (fn [node]
         (when (or (string? node)
                   (vector? node))
           (when (literal-bytes node)
             (swap! literals conj node))))
       form))
    (vec (distinct @literals))))

(defn memory-layout
  [forms]
  (loop [literals (collect-memory-literals forms)
         offset 1024
         layout {}]
    (if-let [literal (first literals)]
      (let [bs (literal-bytes literal)]
        (recur (next literals)
               (+ offset (count bs))
               (assoc layout literal {:offset offset
                                      :bytes bs
                                      :length (count bs)})))
      layout)))

(defn align-to
  [n alignment]
  (let [rem (mod n alignment)]
    (if (zero? rem)
      n
      (+ n (- alignment rem)))))

(defn heap-base
  [layout]
  (align-to
   (reduce max 2048 (map (fn [[_ entry]]
                           (+ (:offset entry) (:length entry)))
                         layout))
   16))

(def wasm-cap-kind-ids
  "Capability kind -> deterministic i32 id for the `cap_acquire` wasm import.
  Only kinds whose contract capability maps to exactly one kind are exposed
  (the id reuses the contract capability id, keeping the boundary 1:1);
  many-kind capabilities (clipboard, keychain, fs) stay interpreter-only in
  this slice."
  (let [kinds-by-cap (reduce (fn [acc [kind cap]]
                               (update acc cap (fnil conj #{}) kind))
                             {}
                             kind->capability)]
    (into {}
          (keep (fn [[kind cap]]
                  (when (= 1 (count (get kinds-by-cap cap)))
                    [kind (capability-id cap)])))
          kind->capability)))

(defn vec-bytes
  [items]
  (bcat (uleb (count items)) (mapcat identity items)))

(defn section
  [id payload]
  (bcat [id] (uleb (count payload)) payload))

(declare compile-wasm-fold compile-wasm-fold-type compiled-result-type local-index
         local-type merge-local-types local-decls function-param-types
         function-result-type symbol-key)

(defn compile-wasm-expr
  ([form locals] (compile-wasm-expr form locals {}))
  ([form locals fns]
  (cond
    (integer? form)
    {:bytes (bcat [0x41] (sleb32 form))
     :result-type :i32}

    (symbol? form)
    (if-let [entry (get locals (symbol-key form))]
      {:bytes (bcat [0x20] (uleb (local-index entry)))
       :result-type (local-type entry)}
      {:problem {:kotoba.wasm/problem :unknown-local
                 :kotoba.wasm/symbol (str form)}})

    (seq? form)
    (let [[op & args] form]
      (case op
        do (loop [remaining args
                  out []
                  local-types []]
             (if-let [expr (first remaining)]
               (let [compiled (compile-wasm-expr expr locals fns)]
                 (if (:problem compiled)
                   compiled
                   (if (next remaining)
                     (recur (next remaining)
                            (bcat out (:bytes compiled) [0x1a])
                            (into local-types (merge-local-types compiled)))
                     {:bytes (bcat out (:bytes compiled))
                      :local-count (+ (count local-types)
                                      (count (merge-local-types compiled)))
                      :local-types (into local-types (merge-local-types compiled))
                      :result-type (compiled-result-type compiled)})))
               {:bytes out
                :local-count (count local-types)
                :local-types local-types}))

        let (let [[bindings & body] args
                  pairs (partition 2 bindings)
                  base-local-count (count locals)]
              (loop [pairs pairs
                     locals locals
                     next-local (count locals)
                     local-types []
                     out []]
                (if-let [[name value] (first pairs)]
                  (let [compiled (compile-wasm-expr value locals fns)]
                    (if (:problem compiled)
                      compiled
                      (recur (next pairs)
                             (assoc locals (symbol-key name)
                                    {:idx next-local
                                     :type (compiled-result-type compiled)})
                             (inc next-local)
                             (conj (into local-types (merge-local-types compiled))
                                   (compiled-result-type compiled))
                             (bcat out (:bytes compiled) [0x21] (uleb next-local)))))
                  (let [compiled (compile-wasm-expr (cons 'do body) locals fns)]
                    (if (:problem compiled)
                      compiled
                      {:bytes (bcat out (:bytes compiled))
                       :local-count (+ (count local-types)
                                       (count (merge-local-types compiled)))
                       :local-types (into local-types (merge-local-types compiled))
                       :result-type (compiled-result-type compiled)})))))

        if (let [[test then else] args
                 test-compiled (compile-wasm-expr test locals fns)
                 then-compiled (compile-wasm-expr then locals fns)
                 else-compiled (compile-wasm-expr else locals fns)]
             (cond
               (:problem test-compiled) test-compiled
               (:problem then-compiled) then-compiled
               (:problem else-compiled) else-compiled
               :else {:bytes (bcat (:bytes test-compiled)
                                   [0x04 0x7f]
                                   (:bytes then-compiled)
                                   [0x05]
                                   (:bytes else-compiled)
                                   [0x0b])
                      :local-count (max (:local-count test-compiled 0)
                                        (:local-count then-compiled 0)
                                        (:local-count else-compiled 0))
                      :local-types (merge-local-types test-compiled then-compiled else-compiled)
                      :result-type (compiled-result-type then-compiled)}))

        + (compile-wasm-fold 0x6a args locals fns)
        - (compile-wasm-fold 0x6b args locals fns)
        * (compile-wasm-fold 0x6c args locals fns)
        quot (compile-wasm-fold 0x6d args locals fns)
        / (compile-wasm-fold 0x6d args locals fns)
        rem (compile-wasm-fold 0x6f args locals fns)
        mod (compile-wasm-fold 0x6f args locals fns)
        = (compile-wasm-fold 0x46 args locals fns)
        < (compile-wasm-fold 0x48 args locals fns)
        > (compile-wasm-fold 0x4a args locals fns)
        <= (compile-wasm-fold 0x4c args locals fns)
        >= (compile-wasm-fold 0x4e args locals fns)
        i64 (let [value (first args)]
              (cond
                (not= 1 (count args))
                {:problem {:kotoba.wasm/problem :arity
                           :kotoba.wasm/op "i64"
                           :kotoba.wasm/expected 1
                           :kotoba.wasm/actual (count args)}}

                (integer? value)
                {:bytes (bcat [0x42] (sleb32 value))
                 :result-type :i64}

                :else
                {:problem {:kotoba.wasm/problem :unsupported-i64-literal
                           :kotoba.wasm/form (pr-str value)}}))
        i64+ (compile-wasm-fold-type 0x7c args locals fns :i64)
        i64- (compile-wasm-fold-type 0x7d args locals fns :i64)
        i64* (compile-wasm-fold-type 0x7e args locals fns :i64)
        call-indirect (let [[idx arg] args
                            idx-compiled (compile-wasm-expr idx locals fns)
                            arg-compiled (compile-wasm-expr arg locals fns)]
                        (cond
                          (not= 2 (count args))
                          {:problem {:kotoba.wasm/problem :arity
                                     :kotoba.wasm/op "call-indirect"
                                     :kotoba.wasm/expected 2
                                     :kotoba.wasm/actual (count args)}}

                          (:problem idx-compiled)
                          idx-compiled

                          (:problem arg-compiled)
                          arg-compiled

                          (not= :i32 (compiled-result-type idx-compiled))
                          {:problem {:kotoba.wasm/problem :type-mismatch
                                     :kotoba.wasm/op "call-indirect"
                                     :kotoba.wasm/expected :i32}}

                          (not= :i32 (compiled-result-type arg-compiled))
                          {:problem {:kotoba.wasm/problem :type-mismatch
                                     :kotoba.wasm/op "call-indirect"
                                     :kotoba.wasm/expected :i32}}

                          :else
                          {:bytes (bcat (:bytes arg-compiled)
                                        (:bytes idx-compiled)
                                        [0x11]
                                        (uleb (:indirect-type-index fns 0))
                                        [0x00])
                           :local-count (+ (count (merge-local-types idx-compiled))
                                           (count (merge-local-types arg-compiled)))
                           :local-types (merge-local-types idx-compiled arg-compiled)
                           :result-type :i32}))
        alloc (let [size (first args)
                    size-compiled (compile-wasm-expr size locals fns)]
                (cond
                  (not= 1 (count args))
                  {:problem {:kotoba.wasm/problem :arity
                             :kotoba.wasm/op "alloc"
                             :kotoba.wasm/expected 1
                             :kotoba.wasm/actual (count args)}}

                  (:problem size-compiled)
                  size-compiled

                  :else
                  {:bytes (bcat [0x23 0x00 0x23 0x00]
                                (:bytes size-compiled)
                                [0x6a 0x24 0x00])
                   :local-count (:local-count size-compiled 0)}))
        alloc-checked (let [size (first args)
                            size-for-check (compile-wasm-expr size locals fns)
                            allocation (compile-wasm-expr (list 'alloc size) locals fns)]
                        (cond
                          (not= 1 (count args))
                          {:problem {:kotoba.wasm/problem :arity
                                     :kotoba.wasm/op "alloc-checked"
                                     :kotoba.wasm/expected 1
                                     :kotoba.wasm/actual (count args)}}

                          (:problem size-for-check)
                          size-for-check

                          (:problem allocation)
                          allocation

                          :else
                          {:bytes (bcat [0x23 0x00]
                                        (:bytes size-for-check)
                                        [0x6a 0x3f 0x00 0x41]
                                        (sleb32 65536)
                                        [0x6c 0x4c 0x04 0x7f]
                                        (:bytes allocation)
                                        [0x05 0x41]
                                        (sleb32 -1)
                                        [0x0b])
                           :local-count (max (:local-count size-for-check 0)
                                             (:local-count allocation 0))}))
        str-len (let [value (first args)]
                  (if-let [bytes (and (string? value) (literal-bytes value))]
                    {:bytes (bcat [0x41] (sleb32 (count bytes)))}
                    {:problem {:kotoba.wasm/problem :unsupported-string-op
                               :kotoba.wasm/op "str-len"}}))
        str-ptr (let [value (first args)
                      entry (get (:memory fns) value)]
                  (if (and (string? value) entry)
                    {:bytes (bcat [0x41] (sleb32 (:offset entry)))}
                    {:problem {:kotoba.wasm/problem :unsupported-string-op
                               :kotoba.wasm/op "str-ptr"}}))
        bytes-ptr (let [value (first args)
                        entry (get (:memory fns) value)]
                    (if (and (vector? value) entry)
                      {:bytes (bcat [0x41] (sleb32 (:offset entry)))}
                      {:problem {:kotoba.wasm/problem :unsupported-bytes-op
                                 :kotoba.wasm/op "bytes-ptr"}}))
        bytes-len (let [value (first args)]
                    (if-let [bytes (and (vector? value) (literal-bytes value))]
                      {:bytes (bcat [0x41] (sleb32 (count bytes)))}
                      {:problem {:kotoba.wasm/problem :unsupported-bytes-op
                                 :kotoba.wasm/op "bytes-len"}}))
        memory-pages (if (empty? args)
                       {:bytes [0x3f 0x00]}
                       {:problem {:kotoba.wasm/problem :arity
                                  :kotoba.wasm/op "memory-pages"
                                  :kotoba.wasm/expected 0
                                  :kotoba.wasm/actual (count args)}})
        memory-grow (let [pages (first args)
                          pages-compiled (compile-wasm-expr pages locals fns)]
                      (cond
                        (not= 1 (count args))
                        {:problem {:kotoba.wasm/problem :arity
                                   :kotoba.wasm/op "memory-grow"
                                   :kotoba.wasm/expected 1
                                   :kotoba.wasm/actual (count args)}}

                        (:problem pages-compiled)
                        pages-compiled

                        :else
                        {:bytes (bcat (:bytes pages-compiled) [0x40 0x00])
                         :local-count (:local-count pages-compiled 0)}))
        mem-byte-at (let [[ptr idx] args
                          addr-compiled (compile-wasm-expr (list '+ ptr idx) locals fns)]
                      (if (:problem addr-compiled)
                        addr-compiled
                        {:bytes (bcat (:bytes addr-compiled) [0x2d 0x00 0x00])
                         :local-count (:local-count addr-compiled 0)}))
        mem-i32-at (let [[ptr offset] args
                         addr-compiled (compile-wasm-expr (list '+ ptr offset) locals fns)]
                     (if (:problem addr-compiled)
                       addr-compiled
                       {:bytes (bcat (:bytes addr-compiled) [0x28 0x02 0x00])
                        :local-count (:local-count addr-compiled 0)}))
        byte-store! (let [[ptr idx value] args
                          addr-compiled (compile-wasm-expr (list '+ ptr idx) locals fns)
                          value-compiled (compile-wasm-expr value locals fns)]
                      (cond
                        (:problem addr-compiled) addr-compiled
                        (:problem value-compiled) value-compiled
                        :else {:bytes (bcat (:bytes addr-compiled)
                                            (:bytes value-compiled)
                                            [0x3a 0x00 0x00]
                                            (:bytes value-compiled))
                               :local-count (max (:local-count addr-compiled 0)
                                                 (:local-count value-compiled 0))}))
        i32-store! (let [[ptr offset value] args
                         addr-compiled (compile-wasm-expr (list '+ ptr offset) locals fns)
                         value-compiled (compile-wasm-expr value locals fns)]
                     (cond
                       (:problem addr-compiled) addr-compiled
                       (:problem value-compiled) value-compiled
                       :else {:bytes (bcat (:bytes addr-compiled)
                                           (:bytes value-compiled)
                                           [0x36 0x02 0x00]
                                           (:bytes value-compiled))
                              :local-count (max (:local-count addr-compiled 0)
                                                (:local-count value-compiled 0))}))
        byte-at (let [[value idx] args
                      bytes (literal-bytes value)]
                  (cond
                    (nil? bytes)
                    {:problem {:kotoba.wasm/problem :unsupported-bytes-op
                               :kotoba.wasm/op "byte-at"}}

                    (not (integer? idx))
                    {:problem {:kotoba.wasm/problem :unsupported-bytes-index
                               :kotoba.wasm/op "byte-at"}}

                    (or (neg? idx) (<= (count bytes) idx))
                    {:problem {:kotoba.wasm/problem :bytes-index-out-of-bounds
                               :kotoba.wasm/op "byte-at"
                               :kotoba.wasm/index idx
                               :kotoba.wasm/length (count bytes)}}

                    :else
                    {:bytes (bcat [0x41] (sleb32 (nth bytes idx)))}))
        cap-acquire (let [[kind resource] args
                          kind-id (get wasm-cap-kind-ids kind)
                          entry (get (:memory fns) resource)]
                      (cond
                        (not= 2 (count args))
                        {:problem {:kotoba.wasm/problem :arity
                                   :kotoba.wasm/op "cap-acquire"
                                   :kotoba.wasm/expected 2
                                   :kotoba.wasm/actual (count args)}}

                        (nil? kind-id)
                        {:problem {:kotoba.wasm/problem :unsupported-capability-kind
                                   :kotoba.wasm/op "cap-acquire"
                                   :kotoba.wasm/kind (pr-str kind)}}

                        (not (and (string? resource) entry))
                        {:problem {:kotoba.wasm/problem :unsupported-cap-resource
                                   :kotoba.wasm/op "cap-acquire"}}

                        :else
                        {:bytes (bcat [0x41] (sleb32 kind-id)
                                      [0x41] (sleb32 (:offset entry))
                                      [0x41] (sleb32 (:length entry))
                                      [0x10] (uleb (get fns 'cap-acquire)))
                         :result-type :i64}))
        has-capability? (let [cap (first args)]
                          (if-let [id (capability-id cap)]
                            {:bytes (bcat [0x41] (sleb32 id)
                                          [0x10] (uleb (get fns 'has-capability? 0)))}
                            {:problem {:kotoba.wasm/problem :unknown-capability
                                       :kotoba.wasm/capability (capability-name cap)}}))
        zero? (let [compiled (compile-wasm-expr (first args) locals fns)]
                (if (:problem compiled)
                  compiled
                  {:bytes (bcat (:bytes compiled) [0x45])
                   :local-count (:local-count compiled 0)}))
        not (let [compiled (compile-wasm-expr (first args) locals fns)]
              (if (:problem compiled)
                compiled
                {:bytes (bcat (:bytes compiled) [0x45])
                 :local-count (:local-count compiled 0)}))
        result-ok? (compile-wasm-expr (list '>= (first args) 0) locals fns)
        result-err? (compile-wasm-expr (list '< (first args) 0) locals fns)
        result-write! (let [[record-ptr value] args
                            record-for-status (compile-wasm-expr record-ptr locals fns)
                            record-for-value (compile-wasm-expr (list '+ record-ptr 4) locals fns)
                            record-for-return (compile-wasm-expr record-ptr locals fns)
                            status (compile-wasm-expr (list 'if (list 'result-err? value) 1 0) locals fns)
                            raw-value (compile-wasm-expr value locals fns)]
                        (cond
                          (:problem record-for-status) record-for-status
                          (:problem record-for-value) record-for-value
                          (:problem record-for-return) record-for-return
                          (:problem status) status
                          (:problem raw-value) raw-value
                          :else {:bytes (bcat (:bytes record-for-status)
                                              (:bytes status)
                                              [0x36 0x02 0x00]
                                              (:bytes record-for-value)
                                              (:bytes raw-value)
                                              [0x36 0x02 0x00]
                                              (:bytes record-for-return))
                                 :local-count (reduce max 0 (map #(:local-count % 0)
                                                                  [record-for-status
                                                                   record-for-value
                                                                   record-for-return
                                                                   status
                                                                   raw-value]))}))
        result-status (compile-wasm-expr (list 'mem-i32-at (first args) 0) locals fns)
        result-value (compile-wasm-expr (list 'mem-i32-at (first args) 4) locals fns)
        inc (compile-wasm-expr `(+ ~(first args) 1) locals fns)
        dec (compile-wasm-expr `(- ~(first args) 1) locals fns)
        (if-let [import (get host-imports op)]
          (let [arity (count (:params import))]
            (if (not= arity (count args))
              {:problem {:kotoba.wasm/problem :arity
                         :kotoba.wasm/op (str op)
                         :kotoba.wasm/expected arity
                         :kotoba.wasm/actual (count args)}}
              (loop [remaining args
                     out []
                     local-types []]
                (if-let [arg (first remaining)]
                  (let [compiled (compile-wasm-expr arg locals fns)]
                    (if (:problem compiled)
                      compiled
                      (recur (next remaining)
                             (bcat out (:bytes compiled))
                             (into local-types (merge-local-types compiled)))))
                  {:bytes (bcat out [0x10] (uleb (get fns op)))
                   :local-count (count local-types)
                   :local-types local-types
                   :result-type (:result import)}))))
          (if-let [fn-index (get fns op)]
            (loop [remaining args
                   out []
                   local-types []]
              (if-let [arg (first remaining)]
                (let [compiled (compile-wasm-expr arg locals fns)]
                  (if (:problem compiled)
                    compiled
                    (recur (next remaining)
                           (bcat out (:bytes compiled))
                           (into local-types (merge-local-types compiled)))))
                {:bytes (bcat out [0x10] (uleb fn-index))
                 :local-count (count local-types)
                 :local-types local-types
                 :result-type (get-in fns [:fn-result-types op] :i32)}))
            {:problem {:kotoba.wasm/problem :unsupported-op
                       :kotoba.wasm/op (str op)}}))))

    :else
    {:problem {:kotoba.wasm/problem :unsupported-form
               :kotoba.wasm/form (pr-str form)}})))

(defn compile-wasm-fold
  ([opcode args locals] (compile-wasm-fold opcode args locals {}))
  ([opcode args locals fns]
  (cond
    (empty? args)
    {:problem {:kotoba.wasm/problem :arity
               :kotoba.wasm/message "numeric wasm op requires at least one argument"}}

    (= 1 (count args))
    (compile-wasm-expr (first args) locals fns)

    :else
    (loop [remaining (rest args)
           compiled (compile-wasm-expr (first args) locals fns)
           local-types (merge-local-types compiled)]
      (if (:problem compiled)
        compiled
        (if-let [arg (first remaining)]
          (let [next-compiled (compile-wasm-expr arg locals fns)]
            (if (:problem next-compiled)
              next-compiled
              (recur (next remaining)
                     {:bytes (bcat (:bytes compiled) (:bytes next-compiled) [opcode])}
                     (into local-types (merge-local-types next-compiled)))))
          (assoc compiled
                 :local-count (count local-types)
                 :local-types local-types)))))))

(defn compile-wasm-fold-type
  [opcode args locals fns result-type]
  (let [compiled (compile-wasm-fold opcode args locals fns)]
    (cond
      (:problem compiled) compiled
      (not-every? #(= result-type (or (:result-type %) :i32))
                  (map #(compile-wasm-expr % locals fns) args))
      {:problem {:kotoba.wasm/problem :type-mismatch
                 :kotoba.wasm/expected result-type}}
      :else (assoc compiled :result-type result-type))))

(defn main-function
  [forms]
  (get (into {} (keep function-def forms)) 'main))

(defn function-defs
  [forms]
  (vec (keep function-def forms)))

(defn uses-call-indirect?
  [forms]
  (let [found? (atom false)]
    (doseq [form forms]
      (walk-forms
       (fn [node]
         (when (and (seq? node) (= 'call-indirect (first node)))
           (reset! found? true)))
       form))
    @found?))

(def wasm-valtypes
  {:i32 0x7f
   :i64 0x7e})

(defn symbol-key
  [sym]
  (symbol (name sym)))

(defn annotated-wasm-type
  "Wasm value type for a param symbol: `^:i64` params and `^{:cap <kind>}`
  typed capability params (whose runtime representation is the opaque i64
  handle) lower to :i64; everything else is :i32."
  [sym]
  (if (or (:i64 (meta sym)) (some? (cap-param-kind sym))) :i64 :i32))

(defn function-result-type
  [[name _f]]
  (if (:i64 (meta name)) :i64 nil))

(defn function-param-types
  [[_name f]]
  (mapv annotated-wasm-type (:params f)))

(defn compiled-result-type
  [compiled]
  (or (:result-type compiled) :i32))

(defn local-index
  [entry]
  (if (map? entry) (:idx entry) entry))

(defn local-type
  [entry]
  (if (map? entry) (:type entry) :i32))

(defn local-decls
  [types]
  (if (seq types)
    (let [groups (partition-by identity types)]
      (bcat (uleb (count groups))
            (mapcat (fn [group]
                      (bcat (uleb (count group))
                            [(wasm-valtypes (first group))]))
                    groups)))
    [0x00]))

(defn merge-local-types
  [& compiled-values]
  (vec (mapcat #(or (:local-types %) (repeat (:local-count % 0) :i32))
               compiled-values)))

(defn wasm-fn-type
  [{:keys [params result]}]
  (bcat [0x60]
        (uleb (count params))
        (map wasm-valtypes params)
        (if result
          [0x01 (wasm-valtypes result)]
          [0x00])))

(def wasm-magic-version
  [0x00 0x61 0x73 0x6d 0x01 0x00 0x00 0x00])

(defn import-entry
  [module field type-index]
  (let [module-bytes (utf8-bytes module)
        field-bytes (utf8-bytes field)]
    (bcat (uleb (count module-bytes))
          module-bytes
          (uleb (count field-bytes))
          field-bytes
          [0x00]
          (uleb type-index))))

(defn export-entry
  [name kind index]
  (let [name-bytes (utf8-bytes name)]
    (bcat (uleb (count name-bytes))
          name-bytes
          [kind]
          (uleb index))))

(defn global-entry
  [initial-value]
  (bcat [0x7f 0x01 0x41]
        (sleb32 initial-value)
        [0x0b]))

(defn table-entry
  [size]
  [0x70 0x00 size])

(defn element-segment
  [function-indexes]
  (bcat [0x00 0x41 0x00 0x0b]
        (uleb (count function-indexes))
        (mapcat uleb function-indexes)))

(defn data-segment
  [offset bs]
  (bcat [0x00 0x41]
        (sleb32 offset)
        [0x0b]
        (uleb (count bs))
        bs))

(defn wasm-binary
  "Compile integer functions to a WebAssembly MVP binary and export `main`."
  ([forms] (wasm-binary forms nil))
  ([forms policy]
  (let [defs (function-defs forms)
        indirect? (uses-call-indirect? forms)
        imports (required-host-imports forms)
        import-count (count imports)
        import-indexes (into {} (map-indexed (fn [idx op] [op idx]) imports))
        layout (memory-layout forms)
        heap-start (heap-base layout)
        fn-indexes (merge import-indexes
                          (into {} (map-indexed (fn [idx [name _]]
                                                   [name (+ import-count idx)])
                                                 defs)))
        declared-fn-result-types (into {} (map (fn [[name :as def]]
                                                 [name (or (function-result-type def) :i32)])
                                               defs))
        compile-context (assoc fn-indexes
                               :memory layout
                               :fn-result-types declared-fn-result-types
                               :indirect-type-index 0)
        main (get (into {} defs) 'main)]
    (cond
      (nil? main)
      {:kotoba.wasm/ok? false
       :kotoba.wasm/problems [{:kotoba.wasm/problem :missing-main}]}

      (seq (:params main))
      {:kotoba.wasm/ok? false
       :kotoba.wasm/problems [{:kotoba.wasm/problem :main-arity
                               :kotoba.wasm/expected 0
                               :kotoba.wasm/actual (count (:params main))}]}

      :else
      (let [compiled-fns
            (mapv (fn [[name f]]
                    (let [locals (into {} (map-indexed (fn [idx param]
                                                         [(symbol-key param)
                                                          {:idx idx
                                                           :type (annotated-wasm-type param)}])
                                                       (:params f)))
                          compiled (compile-wasm-expr (cons 'do (:body f)) locals compile-context)]
                      (assoc compiled
                             :name name
                             :param-count (count (:params f)))))
                  defs)]
        (if-let [problem (some :problem compiled-fns)]
          {:kotoba.wasm/ok? false
           :kotoba.wasm/problems [problem]}
          (let [import-metadata (mapv host-imports imports)
                import-signatures (mapv (fn [import]
                                           {:params (:params import)
                                            :result (:result import)})
                                         import-metadata)
                fn-signatures (mapv (fn [compiled]
                                       {:params (function-param-types
                                                (some #(when (= (:name compiled) (first %)) %) defs))
                                        :result (compiled-result-type compiled)})
                                     compiled-fns)
                indirect-signatures (when indirect?
                                      [{:params [:i32] :result :i32}])
                signatures (vec (distinct (concat indirect-signatures
                                                  import-signatures
                                                  fn-signatures)))
                type-index-by-signature (into {} (map-indexed (fn [idx signature]
                                                                [signature idx])
                                                              signatures))
                compiled-fns (mapv (fn [compiled signature]
                                     (assoc compiled :type-index
                                            (get type-index-by-signature signature)))
                                   compiled-fns
                                   fn-signatures)
                type-section (section 1 (vec-bytes (mapv wasm-fn-type signatures)))
                import-section (when (seq imports)
                                 (section 2
                                          (vec-bytes
                                           (mapv (fn [import]
                                                   (import-entry (:module import)
                                                                 (:field import)
                                                                 (get type-index-by-signature
                                                                      {:params (:params import)
                                                                       :result (:result import)})))
                                                 import-metadata))))
                function-section (section 3 (vec-bytes (mapv (comp uleb :type-index) compiled-fns)))
                indirect-target-indexes (when indirect?
                                          (mapv #(get fn-indexes (first %))
                                                (remove #(= 'main (first %)) defs)))
                table-section (when indirect?
                                (section 4 (vec-bytes [(table-entry (count indirect-target-indexes))])))
                memory-section (section 5 (vec-bytes [[0x00 0x01]]))
                global-section (section 6 (vec-bytes [(global-entry heap-start)]))
                export-section (section 7 (vec-bytes [(export-entry "main" 0x00 (get fn-indexes 'main))
                                                       (export-entry "memory" 0x02 0)]))
                bodies (mapv (fn [compiled]
                               (let [decls (local-decls (merge-local-types compiled))
                                     body (bcat decls (:bytes compiled) [0x0b])]
                                 (bcat (uleb (count body)) body)))
                             compiled-fns)
                code-section (section 10 (vec-bytes bodies))
                element-section (when indirect?
                                  (section 9 (vec-bytes [(element-segment indirect-target-indexes)])))
                data-section (when (seq layout)
                               (section 11
                                        (vec-bytes
                                         (mapv (fn [[_ entry]]
                                                 (data-segment (:offset entry) (:bytes entry)))
                                               layout))))
                module-bytes (bcat wasm-magic-version
                                   type-section
                                   import-section
                                   function-section
                                   table-section
                                   memory-section
                                   global-section
                                   export-section
                                   element-section
                                   code-section
                                   data-section)]
            {:kotoba.wasm/ok? true
             :kotoba.wasm/binary (byte-array (map unchecked-byte module-bytes))
             :kotoba.wasm/byte-count (count module-bytes)
             :kotoba.wasm/export "main"
             :kotoba.wasm/result-type (compiled-result-type (some #(when (= 'main (:name %)) %) compiled-fns))
             :kotoba.wasm/function-count (count compiled-fns)
             :kotoba.wasm/import-count import-count
             :kotoba.wasm/imports import-metadata
             :kotoba.wasm/memory? true
             :kotoba.wasm/memory-min-pages 1
             :kotoba.wasm/heap-base heap-start
             :kotoba.wasm/data-segment-count (count layout)
             :kotoba.wasm/local-count (reduce max 0 (map #(:local-count % 0) compiled-fns))})))))))

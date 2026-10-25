(ns kotoba.codebase.evaluation-portable-test
  "Run a stored definition from its CID alone, on ClojureScript.

  This is the half `semantic-code-portable-test` never covered. That test
  proves the two runtimes AGREE ON A HASH; this one proves the hash is
  runnable on the side kotobase actually deploys to. Until now the evaluation
  layer was `.clj`, so a definition could be identified in a Worker and only
  executed on a JVM.

  There is no filesystem here on purpose. The store is an `ICodebaseStore`
  implemented in ClojureScript, which is the thing the backend seam exists to
  make possible — `backend/coerce` refuses a path on this platform rather than
  reaching for `java.nio`."
  (:require [ipld.core :as ipld]
            [ipld.value :as value]
            [kotoba.codebase.actor :as actor]
            [kotoba.codebase.backend :as backend]
            [kotoba.codebase.evaluator :as evaluator]
            [kotoba.codebase.semantic-code :as semantic]
            [kotoba.codebase.store :as store]
            [kotoba.codebase.typed-eval :as typed-eval]))

(defn- byte-vec
  "Bytes as a comparable value. `-put-bytes!` has to distinguish `:identical`
  from `:conflict`, and two `Uint8Array`s holding the same bytes are not `=`."
  [b]
  (cond
    (vector? b) b
    (nil? b) nil
    :else (vec (js/Array.from b))))

(defn memory-store
  "The whole backend contract over two atoms. Every integrity rule lives in
  `store`, so a provider this dumb is the intended shape rather than a stub."
  []
  (let [spaces (atom {})
        heads (atom {})
        ready (atom false)]
    (reify backend/ICodebaseStore
      (-initialize! [_] (reset! ready true) {:schema backend/store-schema})
      (-initialized? [_] @ready)
      (-put-bytes! [_ space key value]
        (let [existing (get-in @spaces [space key])]
          (cond
            (nil? existing) (do (swap! spaces assoc-in [space key] value) :written)
            (= (byte-vec existing) (byte-vec value)) :identical
            :else :conflict)))
      (-get-bytes [_ space key] (get-in @spaces [space key]))
      (-list-keys [_ space] (vec (keys (get @spaces space))))
      (-read-head [_ namespace] (get @heads namespace))
      (-swap-head! [_ namespace expected next-cid]
        (let [actual (get @heads namespace)]
          (if (= actual expected)
            (do (swap! heads assoc namespace next-cid) {:ok? true})
            {:ok? false :actual actual}))))))

(defn- store-definitions!
  "Compile FORMS and persist every produced block, returning name -> CID.
  The JVM `evaluator-test` helper, unchanged apart from running here."
  [root forms]
  (let [compiled (semantic/compile-definitions forms)]
    (into {}
          (map (fn [[name {:keys [cid block type-cid type-block
                                  group-cid group-block]}]]
                 (when type-cid (store/put-block! root type-cid type-block))
                 (when group-cid (store/put-block! root group-cid group-block))
                 (store/put-block! root cid block)
                 [(str name) cid]))
          (:definitions compiled))))

(defn- check! [label expected actual]
  (when-not (= expected actual)
    (throw (js/Error. (str label ": expected " (pr-str expected)
                           " got " (pr-str actual)))))
  actual)

(defn- evaluates-from-its-cid-alone []
  (let [root (memory-store)]
    (store/initialize! root)
    (let [cids (store-definitions! root '[(defn increment [x] (+ x 1))])
          cid (get cids "increment")
          {:keys [value]} (evaluator/evaluate root cid)]
      (when-not (fn? value)
        (throw (js/Error. "increment did not evaluate to a function")))
      (check! "increment 3" 4 (value 3))
      cid)))

(defn- hydrates-transitive-dependencies-by-cid []
  (let [root (memory-store)]
    (store/initialize! root)
    (let [cids (store-definitions! root '[(defn twice [x] (* x 2))
                                          (defn quadruple [x] (twice (twice x)))])
          result (evaluator/invoke root (get cids "quadruple") [3])]
      (check! "quadruple 3" 12 (:value result))
      ;; The dependency is reached by hash with no name bound to it anywhere.
      (check! "no head is set" nil (store/head root "any-namespace")))))

(defn- a-missing-dependency-fails-closed []
  (let [root (memory-store)]
    (store/initialize! root)
    ;; Only the LAST block is stored, so the dependency this definition names
    ;; is genuinely absent rather than merely unnamed.
    (let [compiled (semantic/compile-definitions
                    '[(defn twice [x] (* x 2))
                      (defn quadruple [x] (twice (twice x)))])
          {:keys [cid block type-cid type-block]}
          (get (:definitions compiled) 'quadruple)]
      (when type-cid (store/put-block! root type-cid type-block))
      (store/put-block! root cid block)
      ;; `evaluate` SUCCEEDS here, and that is correct rather than a gap: a
      ;; `defn` evaluates to a closure, and the `reference` node sits inside
      ;; its body, so nothing hydrates the dependency until the closure is
      ;; applied. The failure is at call time -- which is where it has to be
      ;; asserted, or the test passes for the wrong reason.
      (let [closure (:value (evaluator/evaluate root cid))]
        (when-not (fn? closure)
          (throw (js/Error. "quadruple did not evaluate to a closure")))
        (let [failed? (try (closure 3) false (catch :default _ true))]
          (check! "a missing dependency fails closed when the body runs"
                  true failed?))))))

(defn- capabilities-are-refused-not-dispatched []
  (let [root (memory-store)]
    (store/initialize! root)
    ;; `intrinsic` resolves by stable id, and the effect intrinsics resolve to
    ;; a thrower. The prefix check behind this used `.startsWith`, which is the
    ;; single line that kept this namespace on the JVM.
    (let [refused? (try (#'evaluator/intrinsic "not.a.kotoba.intrinsic/nope") false
                        (catch :default _ true))]
      (check! "an unknown intrinsic is refused" true refused?))))

(defn- scalar-decoding-is-exact []
  ;; The three sites that were `bigint` / `Float/intBitsToFloat` /
  ;; `Double/longBitsToDouble`. A canonical form carries a float as its INTEGER
  ;; BIT PATTERN, so these are reinterpretations and a near-enough answer is a
  ;; wrong one. Called directly because reaching them through `assemble` needs
  ;; a typed block with a float literal in it, and the thing under test is the
  ;; bit conversion rather than the path to it.
  (check! "f64 bits of 1.0"   1.0  (#'typed-eval/f64-from-bits 4607182418800017408))
  (check! "f64 bits of -2.0" -2.0  (#'typed-eval/f64-from-bits -4611686018427387904))
  (check! "f64 bits of 0.5"   0.5  (#'typed-eval/f64-from-bits 4602678819172646912))
  (check! "f32 bits of 1.0"   1.0  (#'typed-eval/f32-from-bits 1065353216))
  (check! "f32 bits of -0.5" -0.5  (#'typed-eval/f32-from-bits -1090519040))
  ;; i64 is a JS bigint on this side, which is what kotoba.kir uses for i64 --
  ;; and precisely why: 2^53+1 is not representable as a plain cljs number.
  (check! "i64 42" (js/BigInt 42) (#'typed-eval/->i64 42))
  (check! "i64 beyond 2^53" (js/BigInt "9007199254740993")
          (#'typed-eval/->i64 (js/BigInt "9007199254740993"))))

(defn- typed-eval-loads []
  ;; typed-eval moved to .cljc alongside the evaluator; its float decoding had
  ;; to stop being `Double/longBitsToDouble`. Reaching the namespace at all is
  ;; what proves the reader conditionals compile on this side.
  (check! "typed-eval default-fuel" 100000 typed-eval/default-fuel))

(defn- coerce-refuses-a-path []
  (let [refused? (try (backend/coerce "/tmp/not-a-backend") false
                      (catch :default _ true))]
    (check! "coerce refuses a path on cljs" true refused?)))

(defn- the-actor-loader-runs-on-this-side []
  ;; superproject ADR-2608059000: `code` is a CID that RUNS, and the runtime it
  ;; has to run on is this one. The JVM suite covers the same seam; a seam that
  ;; only works there is the exact gap step 2 existed to close.
  (let [root (memory-store)
        blocks (atom {})]
    (store/initialize! root)
    (let [cids (store-definitions!
                root '[(defn credit [state message] (if state (+ state 1) 1))])
          invoke (actor/invoke-fn
                  {:codebase root
                   :get-fn (fn [cid] (get @blocks cid))
                   :put! (fn [cid bytes] (swap! blocks assoc cid bytes))})
          call (fn [state] (invoke {:address "alice" :caller "alice"
                                    :code (get cids "credit") :state state
                                    :method "credit" :args []}))
          first-call (call nil)
          second-call (call (:state first-call))]
      (check! "an actor with no state starts" 1
              (value/decode-value (get @blocks (:state first-call))))
      (check! "and the next call sees what it wrote" 2
              (value/decode-value (get @blocks (:state second-call))))
      ;; Totality is the property a consensus machine cannot check for itself:
      ;; a replica that throws here produces no root while its peers produce one.
      (check! "an absent definition refuses rather than throwing"
              {:refused :no-code}
              (invoke {:address "alice" :caller "alice"
                       :code (ipld/cid (ipld/encode {"absent" true}))
                       :state nil :method "credit" :args []})))))

(defn -main []
  (let [cid (evaluates-from-its-cid-alone)]
    (hydrates-transitive-dependencies-by-cid)
    (a-missing-dependency-fails-closed)
    (capabilities-are-refused-not-dispatched)
    (scalar-decoding-is-exact)
    (typed-eval-loads)
    (coerce-refuses-a-path)
    (the-actor-loader-runs-on-this-side)
    (println "codebase CLJS evaluation: ran a definition from its CID alone —" cid)))

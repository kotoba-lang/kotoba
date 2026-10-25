(ns run
  "Async conformance suite, verified against its own oracles.

  The JVM half races real threads, so interleaving is guaranteed. The async
  half races promises on one event loop, where it is NOT: if every
  `-read-ref` resolved before any write ran, four writers would serialize
  and the race would pass trivially against a store enforcing nothing. So
  this file does not merely run the suite -- it runs it against stores that
  must be REJECTED, and requires the rejection to come from the check that
  is supposed to catch each one.

  The store that matters is `:toctou`. It is sequentially correct -- it
  passes every check the old suite had -- and wrong only under concurrent
  writers, because it decides on a value it read a turn earlier and writes
  without re-checking. That is not a contrived shape: it is read-then-PUT
  over HTTP, which is what a provider without a conditional write can
  offer, and it is what the old suite could never distinguish from a real
  precondition."
  (:require [kotobase.storage.async-contract :as contract]
            [kotobase.storage.core :as storage]
            [kotobase.storage.memory :as mem]
            [kotobase.storage.object-memory :as omem]
            [kotobase.storage.observed-ref :as observed]
            [kotobase.storage.signed-head :as sh]
            [kotobase.storage.verify :as verify]))

(defn- resolved [value] (js/Promise.resolve value))

(defrecord AsyncMemory [state profile mode]
  storage/IBlockStore
  (-put-blocks! [_ blocks]
    (resolved (do (swap! state update :blocks into (map (juxt :cid :bytes)) blocks)
                  (mapv :cid blocks))))
  (-get-blocks [_ cids] (resolved (select-keys (:blocks @state) cids)))

  storage/IRefStore
  (-read-ref [_ name] (resolved (get-in @state [:refs name])))
  (-compare-and-set-ref! [this name expected next]
    (let [publish! (fn [] (swap! state assoc-in [:refs name]
                                 {:cid next :version next})
                     {:published? true :current next :version next})
          lose (fn [current] {:published? false :current (:cid current)
                              :version (:version current)})]
      (-> (storage/-read-ref this name)
          (.then
           (fn [read-at-call-time]
             (case mode
               ;; The store evaluates the precondition itself, at write
               ;; time. What R2's `onlyIf` and a SQL transaction give you.
               :enforced (let [current (get-in @state [:refs name])]
                           (if (= expected (:cid current)) (publish!) (lose current)))

               ;; Decide on the earlier read, write a turn later. Correct
               ;; for one writer; loses updates for two.
               :toctou (if (not= expected (:cid read-at-call-time))
                         (lose read-at-call-time)
                         (-> (resolved nil) (.then (fn [_] (publish!)))))

               ;; No precondition at all.
               :ignored (publish!)))))))

  storage/IBackendCapabilities
  (-capabilities [_] (conj storage/required-capabilities profile)))

(defn- store [profile mode]
  (->AsyncMemory (atom {:blocks {} :refs {}}) profile mode))

(def ^:private failures
  "Counted here rather than in `process.exitCode`, which `cljs.main -m run`
  resets when its own REPL turn finishes -- a failing run exited 0, so any
  CI gating on the exit code would have been green forever. Verified by
  breaking an oracle on purpose."
  (atom 0))

(defn- expect-rejection
  "Run the suite and require it to reject, for the stated reason."
  [backend label match]
  (-> (contract/verify backend)
      (.then (fn [result]
               (js/console.error
                (str "FAIL: " label " -- the suite accepted a store it must reject: "
                     (pr-str result)))
               (swap! failures inc)))
      (.catch (fn [error]
                (if (re-find match (.-message error))
                  (println (str "ok  - " label))
                  (do (js/console.error
                       (str "FAIL: " label " -- rejected for the wrong reason: "
                            (.-message error)))
                      (swap! failures inc)))))))

(defn- expect-pass [backend label expected]
  (-> (contract/verify backend)
      (.then (fn [result]
               (if (= expected result)
                 (println (str "ok  - " label ": " (pr-str result)))
                 (do (js/console.error (str "FAIL: " label " -- got " (pr-str result)))
                     (swap! failures inc)))))
      (.catch (fn [error]
                (js/console.error (str "FAIL: " label " -- " (.-message error)))
                (swap! failures inc)))))

;; ── the signed head, on the side it actually ships on ───────────────────────
;;
;; `signed_head_test.cljc` runs on the JVM and exercises the SYNCHRONOUS store.
;; That store cannot be attached to a single host this namespace exists for:
;; B2, IPNS, S3 and a content-addressed network are all reached over the
;; network, and on the Worker runtime that means a Promise. So the sync
;; implementation was the whole ref plane, and it was untestable against every
;; intended deployment. `async-open` is the half that ships; this is where it
;; gets held to the same contract as every other backend.

(defn- async-pointer
  "The dumb unconditional pointer, answering with Promises -- an S3 PUT, an
  IPNS publish.

  The write LANDS A TURN LATER, deliberately. A pointer that applied the swap
  before returning its promise would be updated whether the caller awaited it
  or not, and the re-read-after-publish check -- the thing that lets a losing
  writer discover it lost -- would pass with the await removed. Deferring it
  is what makes that assertion mean anything, and it is also what a real
  network PUT does."
  []
  (let [state (atom {})]
    {:read-head! (fn [n] (resolved (get @state n)))
     :write-head! (fn [n head]
                    ;; several turns, not one. A single `.then` still lands
                    ;; before the caller's next read even when the promise is
                    ;; dropped, so a one-turn defer cannot tell an awaited
                    ;; write from an ignored one -- measured: removing the
                    ;; await left the suite green. A real PUT is many turns.
                    (-> (reduce (fn [p _] (.then p identity))
                                (resolved nil)
                                (range 8))
                        (.then (fn [_] (swap! state assoc n head)))))}))

(defn- async-signed-head-backend
  "Blocks on a store with no conditional write, refs on a signed head -- the
  composition the split exists to make expressible."
  []
  (let [k "alice"
        sign-fn (fn [record] (resolved [k (hash record)]))
        verify-fn (fn [record sig issuer]
                    (resolved (and (= sig [k (hash record)]) (= issuer k))))]
    (storage/compose
     {:blocks (store :single-writer-ref :ignored)
      :refs (sh/async-open (assoc (async-pointer)
                                  :sign-fn sign-fn
                                  :verify-fn verify-fn
                                  :issuer k))})))

;; ── a head is addressed, on the side it actually ships on (ADR-2608047000) ──
;;
;; The JVM suite covers cross-ref substitution and an unaccepted issuer. This
;; namespace's own principle is that "passes on the JVM" is not evidence for
;; the Worker path, and `verify-chain-async` is a second copy of the check --
;; the exact shape that drifts. Both heads below are genuinely signed; nothing
;; here forges anything.

(declare expect)

(defn- async-addressing-oracles []
  (let [state (atom {})
        pointer {:read-head! (fn [n] (resolved (get @state n)))
                 :write-head! (fn [n head] (resolved (swap! state assoc n head)))}
        ;; the NATURAL verify-fn: valid for the key it names, issuer unpinned
        sign-fn (fn [record] (resolved ["sig" (hash record)]))
        verify-fn (fn [record sig _issuer] (resolved (= sig ["sig" (hash record)])))
        refs (sh/async-open (assoc pointer :sign-fn sign-fn :verify-fn verify-fn
                                   :issuer "alice"))]
    (-> (storage/-compare-and-set-ref! refs "main" nil "cid-a")
        (.then (fn [_]
                 ;; the host answers a read for `other` with `main`'s real head
                 (swap! state assoc "other" (get @state "main"))
                 (storage/-read-ref refs "other")))
        (.then (fn [head]
                 (expect (nil? head)
                         "async: a head addressed to another ref is not this ref's head")
                 (let [record (sh/head-record {:ref-name "main" :seq 99
                                               :cid "cid-mallory" :prev "cid-a"
                                               :issuer "mallory"})]
                   (swap! state assoc "main"
                          (assoc record "sig" ["sig" (hash record)]))
                   (storage/-read-ref refs "main"))))
        (.then (fn [head]
                 (expect (nil? head)
                         "async: a valid signature by an unaccepted issuer is not authority"))))))

;; ── the verifying decorator, on the side it actually ships on ───────────────
;;
;; `verify_test.cljc` runs on the JVM, where `-get-blocks` returns a map. The
;; async decorator returns a PROMISE, and the read path the decorator exists
;; for -- the peer Worker's `get-node!` -- is on this side. Untested here it
;; would ship with no coverage at all on the only runtime it is for.

(defn- expect [ok? label]
  (if ok?
    (println (str "ok  - " label))
    (do (js/console.error (str "FAIL: " label)) (swap! failures inc))))

(defn- cause-data
  "`ex-data`, looking through SCI's wrapper.

  nbb interprets this file, so an exception thrown by an interpreted fn that
  a JS `.then` callback invokes comes back re-wrapped as `{:type :sci/error}`
  with the original hung off the cause. A compiled ClojureScript build -- the
  Worker path this suite stands in for -- rejects with the ExceptionInfo
  directly. Asserting on the wrapper would make this oracle a statement about
  the test runner rather than about the store."
  [error]
  (let [data (ex-data error)]
    (if (= :sci/error (:type data)) (recur (ex-cause error)) data)))

;; ── durable last-seen rollback guard, on the Worker path ───────────────────

(defrecord AsyncObservations [state]
  observed/IObservationStore
  (-read-observation [_ name] (resolved (get @state name)))
  (-compare-and-set-observation! [_ name expected next]
    (let [current (get @state name)]
      (if (= expected current)
        (do (swap! state assoc name next)
            (resolved {:stored? true :current next}))
        (resolved {:stored? false :current current})))))

(defrecord AsyncSequencedRef [head]
  storage/IRefStore
  (-read-ref [_ _] (resolved @head))
  (-compare-and-set-ref! [_ _ expected next]
    (let [current @head]
      (if (= expected (:cid current))
        (let [candidate {:cid next :version (inc (or (:version current) -1))}]
          (reset! head candidate)
          (resolved {:published? true :current next
                     :version (:version candidate)}))
        (resolved {:published? false :current (:cid current)
                   :version (:version current)}))))
  storage/IBackendCapabilities
  (-capabilities [_] #{:conditional-ref :single-writer-ref}))

(defn- expect-observation-rejection [promise problem label]
  (-> promise
      (.then (fn [value]
               (js/console.error
                (str "FAIL: " label " -- resolved: " (pr-str value)))
               (swap! failures inc)))
      (.catch (fn [error]
                (expect (= problem (:problem (cause-data error))) label)))))

(defn- record-accessor-oracles
  "The test-support accessors, called on THIS runtime.

  `snapshot`, `ranges-served` and `reset-ranges!` read a defrecord field.
  They were written as host interop -- `(.-state store)` -- which resolves on
  the JVM and returns `undefined` under SCI, so `@(.-state store)` threw
  `No protocol method IDeref.-deref defined for type undefined`. Nothing here
  caught it: the JVM suite was green because the JVM was never broken, and
  this async suite was green because it never called them. A downstream repo
  (kotobase-storage-pack) found it, 25 errors at once, on the day its own nbb
  runner was first compared against its JVM one.

  Keyword access works on every runtime because these are records. These four
  lines exist so the next `.-` cannot come back unnoticed."
  []
  (let [o (omem/memory-object-store)
        m (mem/memory-store)]
    (expect (= {} (omem/snapshot o)) "object-memory snapshot reads its field on this runtime")
    (expect (= [] (omem/ranges-served o)) "object-memory ranges-served reads its field on this runtime")
    (expect (nil? (do (omem/reset-ranges! o) nil)) "object-memory reset-ranges! writes its field on this runtime")
    (expect (map? (mem/snapshot m)) "memory snapshot reads its field on this runtime")))

(defn- observed-ref-oracles []
  (let [remote (atom {:cid "cid-7" :version 7})
        guarded (observed/async-open
                 {:inner (->AsyncSequencedRef remote)
                  :observations (->AsyncObservations (atom {}))})]
    (-> (storage/-read-ref guarded "main")
        (.then (fn [head]
                 (expect (= {:cid "cid-7" :version 7} head)
                         "async observed ref initializes durable last-seen")
                 (reset! remote {:cid "cid-3" :version 3})
                 (expect-observation-rejection
                  (storage/-read-ref guarded "main") :rollback
                  "async observed ref rejects a valid older sequence")))
        (.then (fn [_]
                 (reset! remote {:cid "cid-fork" :version 7})
                 (expect-observation-rejection
                  (storage/-read-ref guarded "main") :equivocation
                  "async observed ref rejects same-sequence equivocation")))
        (.then (fn [_]
                 (reset! remote {:cid "cid-8" :version 8})
                 (storage/-read-ref guarded "main")))
        (.then (fn [head]
                 (expect (= {:cid "cid-8" :version 8} head)
                         "async observed ref advances on a verified higher sequence")
                 ;; The CID still matches the caller's expected value, but the
                 ;; signed sequence was replayed. Rejection must precede CAS.
                 (reset! remote {:cid "cid-8" :version 2})
                 (expect-observation-rejection
                  (storage/-compare-and-set-ref! guarded "main" "cid-8" "cid-9")
                  :rollback
                  "async observed ref rejects rollback before write")))
        (.then (fn [_]
                 (expect (= {:cid "cid-8" :version 2} @remote)
                         "async rejected rollback write has no remote side effect"))))))

(defn- expect-mismatch
  "A tampered block must REJECT the promise. Resolving without it would look
  to a tree walk exactly like a missing node."
  [promise label]
  (-> promise
      (.then (fn [found]
               (js/console.error
                (str "FAIL: " label " -- resolved instead of rejecting: "
                     (pr-str found)))
               (swap! failures inc)))
      (.catch (fn [error]
                (if (= verify/mismatch-type (:type (cause-data error)))
                  (println (str "ok  - " label))
                  (do (js/console.error
                       (str "FAIL: " label " -- rejected for the wrong reason: "
                            (.-message error)))
                      (swap! failures inc)))))))

;; Content addressing reduced to its only load-bearing property: the same
;; bytes always name themselves the same way, different bytes do not.
(defn- name-of [bytes] (str "cid:" (vec bytes)))

(defrecord AsyncBlocks [blocks]
  storage/IBlockStore
  (-put-blocks! [_ bs] (resolved (mapv :cid bs)))
  (-get-blocks [_ cids] (resolved (select-keys blocks cids)))
  storage/IBackendCapabilities
  (-capabilities [_] storage/block-capabilities))

(defn- verify-oracles []
  (let [a [1 2 3]
        honest (verify/async-verifying-block-store
                (->AsyncBlocks {(name-of a) a}) name-of)
        lying (verify/async-verifying-block-store
               (->AsyncBlocks {(name-of a) [9 9 9]}) name-of)
        wrapped (verify/async-verifying-block-store
                 (store :linearizable-ref :enforced) name-of)]
    (expect (contains? (storage/-capabilities wrapped) :linearizable-ref)
            "async verify: the wrapped store's capabilities are delegated")
    (expect (contains? (storage/-capabilities wrapped) verify/verified-capability)
            "async verify: and :verified-blocks is declared, not implied")
    (expect (storage/ref-store? wrapped)
            "async verify: wrapping a full backend keeps its ref plane")
    (expect (not (storage/ref-store? honest))
            "async verify: wrapping a block-only store does not invent one")
    (-> (storage/-get-blocks honest [(name-of a) "cid:absent"])
        (.then (fn [found]
                 (expect (= {(name-of a) a} found)
                         "async verify: a matching block passes through and a missing CID stays missing")))
        (.then (fn [_]
                 (expect-mismatch
                  (storage/-get-blocks lying [(name-of a)])
                  "async verify: a tampered block rejects rather than vanishing")))
        (.then (fn [_] (storage/-compare-and-set-ref! wrapped "verified" nil "cid-a")))
        (.then (fn [published]
                 (expect (:published? published)
                         "async verify: the ref plane is delegated, promise and all")
                 (storage/-read-ref wrapped "verified")))
        (.then (fn [head]
                 (expect (= "cid-a" (:cid head))
                         "async verify: and the delegated ref reads back"))))))

(defn -main [& _]
  (-> (expect-pass (store :linearizable-ref :enforced)
                   "an enforcing store passes, race included"
                   {:checks 14 :profile :linearizable-ref :concurrency :verified})
      (.then (fn [_]
               ;; The load-bearing oracle: sequentially indistinguishable
               ;; from the enforcing store, caught only by the race. If
               ;; promise interleaving did not really happen, this passes
               ;; and the whole concurrent half is decoration.
               (expect-rejection (store :linearizable-ref :toctou)
                                 "read-then-write is caught, and only by the race"
                                 #"concurrent writers all published")))
      (.then (fn [_]
               (expect-rejection (store :linearizable-ref :ignored)
                                 "a store with no precondition at all is caught earlier"
                                 #"stale CAS must lose")))
      (.then (fn [_]
               (expect-rejection (->AsyncMemory (atom {:blocks {} :refs {}})
                                                :no-such-profile :enforced)
                                 "an undeclared ref profile is refused"
                                 #"exactly one ref profile")))
      (.then (fn [_]
               ;; Declaring :single-writer-ref is not a loophole: the
               ;; sequential half still applies. The same store passes it
               ;; and is simply not asked about concurrent writers.
               (expect-pass (store :single-writer-ref :toctou)
                            "a single-writer store passes without being raced"
                            {:checks 8 :profile :single-writer-ref
                             :concurrency :not-claimed})))
      (.then (fn [_]
               ;; :not-claimed, not :verified. A signature proves authorship,
               ;; not exclusivity -- if this ever reported :verified the suite
               ;; would be lending the store the one guarantee it refuses.
               (expect-pass (async-signed-head-backend)
                            "async signed head satisfies the shared contract"
                            {:checks 8 :profile :single-writer-ref
                             :concurrency :not-claimed})))
      (.then (fn [_] (async-addressing-oracles)))
      (.then (fn [_] (verify-oracles)))
      (.then (fn [_] (observed-ref-oracles)))
      (.then (fn [_] (record-accessor-oracles)))
      (.then (fn [_]
               (if (zero? @failures)
                 (println "async contract oracles: all green")
                 (println (str "async contract oracles: " @failures " FAILURE(S) above")))
               (.exit js/process (if (zero? @failures) 0 1))))
      (.catch (fn [error]
                (js/console.error error)
                (.exit js/process 1)))))

(-main)

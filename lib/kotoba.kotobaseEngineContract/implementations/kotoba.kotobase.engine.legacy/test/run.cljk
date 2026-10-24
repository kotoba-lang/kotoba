(ns run
  "Smoke for the ClojureScript facade.

  This file previously required `kotobase.core`, a namespace that does not
  exist -- so it could not load, let alone pass. It had been dead since the
  rename, and with no CI nothing said so. That matters more than a stale
  import usually would: `kotobase.engine` has a `.clj` and a `.cljs`
  implementation, the JVM suite covers only the first, and the second is
  the one every Worker deployment runs.

  Kept deliberately small. It is a smoke test for the async facade -- open,
  transact, read the published ref, query it back -- not a second copy of
  the JVM suite. The storage backends carry the deep round trips against
  their own stores."
  (:require [kotobase.datomic :as d]
            [kotobase.engine :as engine]
            [kotobase.storage.core :as storage]
            [kotobase.storage.memory :as memory]))

(def ^:private failures (atom 0))

(defn- expect [ok? message]
  (if ok?
    (println (str "ok  - " message))
    (do (js/console.error (str "FAIL: " message)) (swap! failures inc))))

(defn -main [& _]
  (let [backend (memory/memory-store)
        ;; The four controls must return Promises here. The seam is
        ;; synchronous on the JVM and Promise-returning on cljs, and a
        ;; plain `identity` fails from deep inside kotobase-peer rather
        ;; than at the call site.
        conn (engine/open {:storage backend
                           :encrypt-fn #(js/Promise.resolve %)
                           :decrypt-fn #(js/Promise.resolve %)
                           :blind-fn #(js/Promise.resolve (pr-str %))
                           :visible? (constantly true)})]
    (-> (d/transact conn [{:db/id "alice" :person/role "admin"}
                          {:db/id "bob" :person/role "member"}])
        (.then (fn [report]
                 (expect (some? report) "transact returns a report")
                 (js/Promise.resolve (storage/-read-ref backend "main"))))
        (.then (fn [ref]
                 (expect (some? (:cid ref))
                         "the transaction published a ref")
                 (-> (d/transact conn
                                 [{:db/id "carol"
                                   :person/role "guest"}])
                     (.then (fn [_]
                              (d/q
                               '[:find ?r :where [?e :person/role ?r]]
                               (d/at-cid conn (:cid ref))))))))
        (.then (fn [rows]
                 (expect (= #{["admin"] ["member"]} (set (map vec rows)))
                         (str "q stays pinned to the exact commit: "
                              (pr-str rows)))
                 (engine/commit-at! conn nil [["branch" "kind" "root"]])))
        (.then (fn [branch-cid]
                 (-> (storage/-read-ref backend "main")
                     js/Promise.resolve
                     (.then
                      (fn [ref]
                        (expect (not= branch-cid (:cid ref))
                                "canonical commit does not publish a mutable ref")
                        (engine/q (engine/at-cid conn branch-cid)
                                  ["branch" "kind" nil]))))))
        (.then (fn [rows]
                 (expect (= #{{:s "branch" :p "kind" :o "root"}} rows)
                         "canonical commit is readable at its returned CID")))
        (.catch (fn [error]
                  (js/console.error (str "FAIL: " (.-message error)))
                  (swap! failures inc)))
        (.then (fn [_]
                 (if (zero? @failures)
                   (println "kotobase-engine (cljs facade): all green")
                   (println (str "kotobase-engine (cljs facade): " @failures
                                 " FAILURE(S) above")))
                 (.exit js/process (if (zero? @failures) 0 1)))))))

(-main)

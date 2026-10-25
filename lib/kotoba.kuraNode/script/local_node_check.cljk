(ns local-node-check
  "Run the async shard-store contract against a real directory on this machine.

  The point: a self-hosted node is the only third failure domain that can be
  added without opening an account with anybody. This proves the backend works
  before anyone is asked to run one."
  (:require ["node:fs/promises" :as fsp]
            ["node:os" :as os]
            ["node:path" :as path]
            [kura.node.async :as async]
            [kura.node.fs :as fs]
            [kura.node.store :as store]))

(defn -main []
  (let [root (path/join (os/tmpdir) (str "kura-fs-check-" (js/Date.now)))
        s (fs/open {:node-id "fs-local"
                    :root root
                    :failure-domain {:operator "self-hosted" :site "local"}
                    :independence :independent
                    :availability :always-on})]
    (-> (async/run> s)
        (.then (fn [r]
                 (println "backend :" "kura.node.fs ->" root)
                 (println "descriptor:" (pr-str (store/-descriptor s)))
                 (println "result  :" (:passed r) "/" (:total r)
                          (if (zero? (:failed r)) "PASS" (str "FAIL " (:failures r))))
                 ;; What a real placement looks like: the shards of one object
                 ;; dealt across the domains, not one descriptor per domain.
                 ;; Counting domains without counting shards per domain is how
                 ;; a fleet looks survivable and is not.
                 (let [doms [(store/-descriptor s)
                             (store/descriptor {:node-id "r2" :independence :shared-substrate
                                                :availability :always-on
                                                :failure-domain {:provider "cloudflare-r2" :bucket "kura-phase0"}})
                             (store/descriptor {:node-id "b2" :independence :shared-provider
                                                :availability :always-on
                                                :failure-domain {:provider "backblaze-b2"}})]
                       spread (fn [shards]
                                (mapv (fn [i] (let [d (nth doms (mod i (count doms)))]
                                                (assoc d :node-id (str (:node-id d) "-" i))))
                                      (range shards)))]
                   (println)
                   (println "with the two rented backends, a real placement would be:")
                   (doseq [[lbl shards tol] [["launch" 32 13] ["target" 26 7]]]
                     (let [a (store/audit (spread shards) tol)]
                       (println (str "  " lbl "  " shards " shards, tolerates " tol
                                     " -> domains " (:effective-domains a)
                                     ", largest " (:largest-domain a)
                                     ", survivable " (:survivable? a))))))
                 (when-not (zero? (:failed r))
                   (set! (.-exitCode js/process) 1))
                 r))
        ;; Second round: exactly what a crashed run leaves behind. The suite
        ;; must clear its own fixtures at the START, or a node that failed once
        ;; reports two false "absent" failures forever after — pointing the
        ;; operator away from the real defect at the moment they are debugging.
        ;; Observed for real on Node 18.19 at a second site.
        (.then (fn [_]
                 (println)
                 (println "poison round: leaving a crashed run's fixtures in place")
                 (-> (async/-put-shard!> s "obj-async/0/0" (js/Uint8Array. #js [1 2 3 4 5 6 7 8]))
                     (.then (fn [_] (async/-put-shard!> s "obj-async/0/1" (js/Uint8Array. #js [250 251 252]))))
                     (.then (fn [_] (async/run> s)))
                     (.then (fn [r2]
                              (println "  re-run  :" (:passed r2) "/" (:total r2)
                                       (if (zero? (:failed r2)) "PASS" (str "FAIL " (:failures r2))))
                              (when-not (zero? (:failed r2))
                                (set! (.-exitCode js/process) 1)))))))
        (.then (fn [_] (fsp/rm root #js {:recursive true :force true})))
        (.catch (fn [e]
                  (println "ERROR" (.-message e))
                  (set! (.-exitCode js/process) 1))))))

;; A check you have to invoke by hand from -e is a check nobody runs.
(-main)

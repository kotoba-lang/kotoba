(require '[clojure.string :as str] '[clojure.edn :as edn] '[kotobase-peer.policy :as policy])
(let [s (slurp ".agent-output/prolly-disk-oracle.clj") i (str/index-of s "(case (first *command-line-args*)")]
  (when-not i (throw (ex-info "missing fixture helpers" {})))
  (load-string (subs s 0 i)))
(case (first *command-line-args*)
  "write" (let [old (:root2 (edn/read-string (slurp (str (path "basis.edn")))))
                e (engine) s (eng/restore-state e old)
                r (eng/transact e s {:database-id "oracle/db" :request-id "policy-tx"
                     :tx-data [[:db/add "kotobase.policy/read" :kotobase.policy/protected-prefixes "[\":chunk/\"]"]]})
                cid (get-in r [:receipt :physical-root])]
            (spit (str (path "policy-basis.edn")) (pr-str {:root cid}))
            (prn {:phase :write :root cid}))
  "read" (let [root-cid (:root (edn/read-string (slurp (str (path "policy-basis.edn")))))
               e (engine) s (eng/restore-state e root-cid) snap (eng/open-snapshot e s)
               rows (eng/scan e snap ["kotobase.policy/read" nil nil])
               graph-rows (mapv (fn [{:keys [e a v]}] {:e e :a (str a) :v_edn (pr-str v)}) rows)
               p (policy/policy-of graph-rows)
               visible (fn [caps] (let [f (policy/visible-for p caps)]
                                    (fn [row] (f (update row :p str)))))
               src (datalog-source e snap)
               denied (datalog/q src query (visible #{}))
               allowed (datalog/q src query (visible #{policy/read-protected-capability}))]
           (when-not (and (= [":chunk/"] (:protected-prefixes p)) (empty? denied) (= #{[logical-root chunk-cid]} allowed))
             (throw (ex-info "unexpected policy query" {:policy p :denied denied :allowed allowed})))
           (prn {:phase :read :policy p :policy-cid (policy/policy-cid p) :denied denied :allowed allowed :pass true}))
  (throw (ex-info "expected write/read" {})))

(require '[clojure.string :as str] '[clojure.edn :as edn] '[kotobase-peer.policy :as policy]
         '[dango.chain :as chain] '[ed25519.sign :as ed])
(let [s (slurp ".agent-output/prolly-disk-oracle.clj") i (str/index-of s "(case (first *command-line-args*)")]
  (when-not i (throw (ex-info "missing fixture helpers" {})))
  (load-string (subs s 0 i)))
(let [root-cid (:root (edn/read-string (slurp (str (path "policy-basis.edn")))))
      resource (str "kotoba://basis/" root-cid) seed (vec (repeat 32 1))
      token (chain/root {:issuer-seed seed :grant {:caps #{[:datom/read-protected resource]} :before 1800000000}
                         :caveats [] :next-seed (vec (repeat 32 2))})
      presentation (chain/present token)
      request {:req/kind :datom/read-protected :req/resource resource :req/now 1700000000}
      decide (fn [present req] (chain/verify present {:roots #{(ed/public-key seed)} :request req}))
      valid (decide presentation request)
      wrong-basis (decide presentation (assoc request :req/resource "kotoba://basis/bafywrong"))
      expired (decide presentation (assoc request :req/now 1800000000))
      tampered (decide (assoc presentation :seal (vec (repeat 64 0))) request)
      e (engine) s (eng/restore-state e root-cid) snap (eng/open-snapshot e s)
      rows (eng/scan e snap ["kotobase.policy/read" nil nil])
      p (policy/policy-of (mapv (fn [{:keys [e a v]}] {:e e :a (str a) :v_edn (pr-str v)}) rows))
      run (fn [decision]
            (let [caps (if (:dango/allowed? decision) #{policy/read-protected-capability} #{})
                  visible (policy/visible-for p caps)]
              (datalog/q (datalog-source e snap) query #(visible (update % :p str)))))
      allow (run valid) reject (mapv run [wrong-basis expired tampered])]
  (when-not (and (= :granted (:dango/reason valid))
                 (= :dango/not-covered (:dango/reason wrong-basis))
                 (= :dango/expired (:dango/reason expired))
                 (= :dango/bad-seal (:dango/reason tampered))
                 (= #{[logical-root chunk-cid]} allow) (every? empty? reject))
    (throw (ex-info "unexpected signed policy result" {:valid valid :wrong-basis wrong-basis :expired expired :tampered tampered :reject reject})))
  (prn {:basis root-cid :valid (:dango/reason valid) :wrong-basis (:dango/reason wrong-basis)
        :expired (:dango/reason expired) :tampered (:dango/reason tampered)
        :allowed allow :denied-counts (mapv count reject) :pass true}))

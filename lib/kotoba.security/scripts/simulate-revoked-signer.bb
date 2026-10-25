#!/usr/bin/env kbb
;; Technical monitoring simulation: compromised/revoked signer (R-005 / R-002).
;;
;; Builds a synthetic register with a revoked package-signing key, runs the
;; new-artifact trust check (must DENY), and emits a continuous-monitoring
;; alert sample to evidence/<date>/ if --write is given.
;;
;; Usage (repo root):
;;   bb scripts/simulate-revoked-signer.bb
;;   bb scripts/simulate-revoked-signer.bb --write [evidence/YYYY-MM-DD]
(require '[babashka.classpath :refer [add-classpath]]
         '[clojure.edn :as edn]
         '[clojure.java.io :as io]
         '[clojure.string :as str]
         '[cheshire.core :as json])

(def script-dir (-> *file* io/file .getAbsoluteFile .getParentFile))
(def root (.getParentFile script-dir))
(add-classpath (str (io/file root "src")))

(require '[kotoba.security.key-lifecycle :as kl])

(def args (vec *command-line-args*))
(def write? (boolean (some #{"--write"} args)))
(def out-dir
  (let [rest-args (vec (remove #{"--write"} args))]
    (if (first rest-args)
      (io/file (first rest-args))
      (io/file root "evidence" "2026-07-17"))))

(def run-id "sim-revoked-signer-2026-07-17")
(def observed-at "2026-07-17T12:00:00Z")

(def sim-register
  {:register/type :kotoba.security/key-register
   :register/version 1
   :keys
   [{:key/id "sim-compromised-package-signer-2026q3"
     :key/class :package-signing
     :key/algorithm :ed25519
     :key/status :revoked
     :key/owner :package-owner
     :key/created-at "2026-07-01"
     :key/active-from "2026-07-01"
     :key/storage :placeholder
     :key/public "ed25519:1111111111111111111111111111111111111111111111111111111111111111"
     :key/pq-status :classical-only
     :key/intent :research-demo
     :key/notes "Synthetic revoked key for technical IR simulation only."}
    {:key/id "sim-active-replacement-2026q3"
     :key/class :package-signing
     :key/algorithm :ed25519
     :key/status :active
     :key/owner :package-owner
     :key/created-at "2026-07-17"
     :key/storage :placeholder
     :key/public "ed25519:2222222222222222222222222222222222222222222222222222222222222222"
     :key/pq-status :classical-only
     :key/intent :research-demo
     :key/notes "Synthetic replacement key (not production)."}]})

(def decision
  (kl/check-signer-for-new-artifact
   sim-register
   "sim-compromised-package-signer-2026q3"))

(when (:valid? decision)
  (println "FAIL expected denial for revoked signer")
  (System/exit 1))

(def alert
  (kl/emit-alert
   {:alert "trusted-signer-verification-failure"
    :severity :SEV-1
    :signal :package-verification
    :source "scripts/simulate-revoked-signer.bb"
    :run-id run-id
    :component "kotoba-lang/security"
    :package "sim.example/package@bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
    :key-id "sim-compromised-package-signer-2026q3"
    :reason (:message decision)
    :policy "key-lifecycle/new-artifact"
    :decision :deny
    :evidence-id "EV-0009"
    :observed-at observed-at
    :extra {:alert/simulation? true
            :alert/decision-data (:data decision)
            :alert/related-rule "continuous-monitoring.md#alert-rules"}}))

(def host-denial-alert
  (kl/emit-alert
   {:alert "host-capability-denial-spike"
    :severity :SEV-2
    :signal :capability-denial
    :source "scripts/simulate-revoked-signer.bb"
    :run-id (str run-id "-host-denial")
    :component "aiueos/sim-component"
    :package nil
    :key-id nil
    :reason "synthetic spike: 50 denials of host/fs.write in 60s window"
    :policy "aiueos/manifest-capability"
    :decision :deny
    :evidence-id "EV-0009"
    :observed-at observed-at
    :extra {:alert/simulation? true
            :alert/denial-count 50
            :alert/window-seconds 60
            :alert/capability "host/fs.write"
            :alert/related-rule "continuous-monitoring.md#alert-rules"}}))

(println "ok denied revoked signer:" (:message decision) (pr-str (:data decision)))
(println "ok alert" (:alert/name alert) (:alert/severity alert) (:alert/run-id alert))
(println "ok alert" (:alert/name host-denial-alert) (:alert/severity host-denial-alert))

(when write?
  (.mkdirs out-dir)
  (spit (io/file out-dir "alert-compromised-signer.edn") (pr-str alert))
  (spit (io/file out-dir "alert-compromised-signer.json")
        (json/generate-string alert {:pretty true}))
  (spit (io/file out-dir "alert-host-denial-spike.edn") (pr-str host-denial-alert))
  (spit (io/file out-dir "alert-host-denial-spike.json")
        (json/generate-string host-denial-alert {:pretty true}))
  (spit (io/file out-dir "revoked-signer-simulation.edn")
        (pr-str {:simulation/id run-id
                 :simulation/kind :revoked-signer-new-artifact
                 :simulation/observed-at observed-at
                 :simulation/register sim-register
                 :simulation/decision decision
                 :simulation/result :denied-as-expected
                 :simulation/alerts [(:alert/id alert)
                                     (:alert/id host-denial-alert)]}))
  (println "wrote" (str out-dir)))

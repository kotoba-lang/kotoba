#!/usr/bin/env kbb
;; Emit structured continuous-monitoring alert samples (R-005).
;; Prefer simulate-revoked-signer.bb --write for the technical path; this
;; script re-emits pure samples without re-running the trust check.
(require '[babashka.classpath :refer [add-classpath]]
         '[clojure.java.io :as io]
         '[clojure.string :as str]
         '[cheshire.core :as json])

(def script-dir (-> *file* io/file .getAbsoluteFile .getParentFile))
(def root (.getParentFile script-dir))
(add-classpath (str (io/file root "src")))

(require '[kotoba.security.key-lifecycle :as kl])

(def out-dir (io/file root "evidence" "2026-07-17"))
(.mkdirs out-dir)

(def observed-at "2026-07-17T12:00:00Z")

(def alerts
  [(kl/emit-alert
    {:alert "trusted-signer-verification-failure"
     :severity :SEV-1
     :signal :package-verification
     :source "scripts/emit-alert-sample.bb"
     :run-id "sample-compromised-signer-2026-07-17"
     :component "kotoba-lang/security"
     :package "sim.example/package@bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
     :key-id "sim-compromised-package-signer-2026q3"
     :reason "signer key not trusted for new artifacts"
     :policy "key-lifecycle/new-artifact"
     :decision :deny
     :evidence-id "EV-0009"
     :observed-at observed-at
     :extra {:alert/simulation? true}})
   (kl/emit-alert
    {:alert "host-capability-denial-spike"
     :severity :SEV-2
     :signal :capability-denial
     :source "scripts/emit-alert-sample.bb"
     :run-id "sample-host-denial-2026-07-17"
     :component "aiueos/sim-component"
     :reason "synthetic spike: 50 denials of host/fs.write in 60s window"
     :policy "aiueos/manifest-capability"
     :decision :deny
     :evidence-id "EV-0009"
     :observed-at observed-at
     :extra {:alert/simulation? true
             :alert/denial-count 50
             :alert/window-seconds 60
             :alert/capability "host/fs.write"}})])

(doseq [a alerts]
  (let [stem (str/replace (:alert/name a) #"[^a-zA-Z0-9-]+" "-")]
    (spit (io/file out-dir (str "alert-" stem ".edn")) (pr-str a))
    (spit (io/file out-dir (str "alert-" stem ".json"))
          (json/generate-string a {:pretty true}))
    (println "ok" stem)))

(println "wrote" (str out-dir))

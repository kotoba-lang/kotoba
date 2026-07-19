#!/usr/bin/env bb

(require '[clojure.edn :as edn]
         '[clojure.java.io :as io])
(import '(java.security MessageDigest)
        '(java.time Instant Duration))

(def evidence-path "qualification/q9-provider-soak.edn")
(def artifact-paths
  ["providers/http_transport.kotoba"
   "providers/db_transport.kotoba"
   "providers/pg_scram.kotoba"
   "test/kotoba/transport_component_test.clj"])

(defn sha256 [path]
  (let [digest (.digest (MessageDigest/getInstance "SHA-256")
                        (java.nio.file.Files/readAllBytes (.toPath (io/file path))))]
    (apply str (map #(format "%02x" (bit-and % 0xff)) digest))))

(defn expected-artifacts []
  (into (sorted-map) (map (juxt identity sha256) artifact-paths)))

(defn valid-instant? [value]
  (try
    (Instant/parse value)
    true
    (catch Exception _ false)))

(defn valid-run? [run]
  (and (= :success (:conclusion run))
       (string? (:github-run-id run))
       (boolean (re-matches #"[0-9]+" (:github-run-id run)))
       (string? (:head-sha run))
       (boolean (re-matches #"[0-9a-f]{40}" (:head-sha run)))
       (string? (:observed-at run))
       (valid-instant? (:observed-at run))
       (= (expected-artifacts) (:artifacts run))))

(defn qualification [record]
  (let [runs (filter valid-run? (:runs record))
        unique-runs (vals (into {} (map (juxt :github-run-id identity) runs)))
        instants (sort (map #(Instant/parse (:observed-at %)) unique-runs))
        days (if (seq instants)
               (.toDays (Duration/between (first instants) (last instants)))
               0)
        required (:required record)]
    {:successful-runs (count unique-runs)
     :rejected-runs (- (count (:runs record)) (count runs))
     :calendar-days days
     :qualified? (and (>= (count unique-runs) (:successful-runs required))
                      (>= days (:calendar-days required)))}))

(defn record-run []
  (let [run-id (System/getenv "GITHUB_RUN_ID")
        head-sha (System/getenv "GITHUB_SHA")]
    (when-not (and (seq run-id) (re-matches #"[0-9]+" run-id)
                   (seq head-sha) (re-matches #"[0-9a-f]{40}" head-sha))
      (throw (ex-info "GITHUB_RUN_ID and GITHUB_SHA are required" {})))
    (prn {:github-run-id run-id
          :head-sha head-sha
          :observed-at (str (Instant/now))
          :conclusion :success
          :artifacts (expected-artifacts)})))

(defn status [strict?]
  (let [record (edn/read-string (slurp evidence-path))
        result (qualification record)]
    (println (pr-str result))
    (when (and strict? (not (:qualified? result)))
      (System/exit 1))))

(case (first *command-line-args*)
  "record" (record-run)
  "status" (status false)
  "check" (status true)
  (throw (ex-info "usage: q9-provider-soak.bb record|status|check" {})))

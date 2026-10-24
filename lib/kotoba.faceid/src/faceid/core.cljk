(ns faceid.core
  (:require [faceid.model :as m]
            [faceid.ports :as p]))

(defn- contains-forbidden? [x]
  (cond
    (map? x) (or (boolean (some m/forbidden-keys (keys x)))
                 (boolean (some contains-forbidden? (vals x))))
    (sequential? x) (boolean (some contains-forbidden? x))
    :else false))

(defn problems [record]
  (cond-> []
    (not (contains? m/purposes (:faceid/purpose record)))
    (conj {:faceid.problem/code :unknown-purpose})
    (contains-forbidden? record)
    (conj {:faceid.problem/code :raw-biometric-material})))

(defn attest [port request]
  (when-let [ps (seq (problems request))]
    (throw (ex-info "invalid FaceID request" {:faceid/problems ps})))
  (let [out (p/attest! port request)]
    (when-let [ps (seq (problems out))]
      (throw (ex-info "invalid FaceID attestation" {:faceid/problems ps})))
    out))

(defn attest-once! [challenge-store port request]
  (when-not (p/consume-challenge! challenge-store (:faceid/challenge request))
    (throw (ex-info "FaceID challenge replay" {:faceid/challenge (:faceid/challenge request)})))
  (attest port request))

(defn attest-and-store! [attestation-store attestation]
  (when-not (:faceid/ok? attestation)
    (throw (ex-info "FaceID attestation not successful"
                    {:faceid/id (:faceid/id attestation)})))
  (when-not (:faceid/device-id attestation)
    (throw (ex-info "FaceID attestation missing device binding"
                    {:faceid/id (:faceid/id attestation)})))
  (p/put-attestation! attestation-store attestation))

(defn attest-once-and-store! [challenge-store attestation-store port request]
  (let [attestation (attest-once! challenge-store port request)]
    (attest-and-store! attestation-store attestation)))

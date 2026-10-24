(ns touchid.core
  (:require [touchid.model :as m]
            [touchid.ports :as p]))

(defn- contains-forbidden? [x]
  (cond
    (map? x) (or (boolean (some m/forbidden-keys (keys x)))
                 (boolean (some contains-forbidden? (vals x))))
    (sequential? x) (boolean (some contains-forbidden? x))
    :else false))

(defn problems [record]
  (cond-> []
    (not (contains? m/purposes (:touchid/purpose record)))
    (conj {:touchid.problem/code :unknown-purpose})
    (contains-forbidden? record)
    (conj {:touchid.problem/code :raw-biometric-material})))

(defn attest [port request]
  (when-let [ps (seq (problems request))]
    (throw (ex-info "invalid TouchID request" {:touchid/problems ps})))
  (let [out (p/attest! port request)]
    (when-let [ps (seq (problems out))]
      (throw (ex-info "invalid TouchID attestation" {:touchid/problems ps})))
    out))

(defn attest-once! [challenge-store port request]
  (when-not (p/consume-challenge! challenge-store (:touchid/challenge request))
    (throw (ex-info "TouchID challenge replay" {:touchid/challenge (:touchid/challenge request)})))
  (attest port request))

(defn attest-and-store! [attestation-store attestation]
  (when-not (:touchid/ok? attestation)
    (throw (ex-info "TouchID attestation not successful"
                    {:touchid/id (:touchid/id attestation)})))
  (when-not (:touchid/device-id attestation)
    (throw (ex-info "TouchID attestation missing device binding"
                    {:touchid/id (:touchid/id attestation)})))
  (p/put-attestation! attestation-store attestation))

(defn attest-once-and-store! [challenge-store attestation-store port request]
  (let [attestation (attest-once! challenge-store port request)]
    (attest-and-store! attestation-store attestation)))

(ns cae.adapter
  "Explicit boundary for replacing portable reference kernels with validated external solvers."
  (:require [cae.solver :as solver]))

(defn- require! [m k]
  (when-not (some? (get m k))
    (throw (ex-info "external backend descriptor is missing a required field" {:field k}))))

(defmethod solver/solve :external-backend [{:keys [backend domain version input-format case-id command result] :as payload}]
  (doseq [k [:backend :domain :version :input-format]] (require! {:backend backend :domain domain :version version :input-format input-format} k))
  {:solver :external-backend :backend backend :domain domain :version version :input-format input-format :case/id case-id :command command :input (dissoc payload :solver) :result result :execution :host-adapter :fidelity (if (:validated? payload) :external-validated :external-pending-validation) :status (cond (nil? result) :adapter-pending (:validated? payload) :validated :else :completed-unverified) :provenance {:adapter :cae.adapter :backend backend :version version}})

(defn descriptor
  "Create a serializable external solver descriptor without executing a process."
  [{:keys [backend domain version input-format command]}]
  (doseq [k [backend domain version input-format] :when (nil? k)]
    (throw (ex-info "backend descriptor values must be non-nil" {})))
  {:backend backend :domain domain :version version :input-format input-format :command command :transport :host-process-or-mpi})

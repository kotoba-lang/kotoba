(ns lg-curpus2skill.audit
  "Fire-and-forget BPMN generic.audit.emit shim (clj port of the wave-1 audit
  pattern; the Python server gated audit via LG_AUDIT_DISABLED).

  JSON → cheshire. The host supplies the purpose-bound HTTP capability and
  configuration. The portable default is disabled and network-incapable."
  (:require [cheshire.core :as json]
            [kotoba.lang.text :as str]))

(def ^:dynamic *config*
  {:disabled? true
   :dispatcher-url "http://bpmn-dispatcher.mitama-udf.svc.cluster.local:8080"
   :internal-secret ""
   :timeout-ms 3000})

(def ^:dynamic *post!*
  (fn [& _]
    (throw (ex-info "explicit audit HTTP capability required"
                    {:capability :audit-http}))))

(defn audit-disabled? [] (true? (:disabled? *config*)))

(defn emit-audit!
  "Synchronous best-effort emit. Returns nil. Never throws."
  [{:keys [actor activity object-id object-type attributes]}]
  (when-not (audit-disabled?)
    (try
      (let [dispatcher-url (str/replace (:dispatcher-url *config*) #"/+$" "")
            internal-secret (str/trim (:internal-secret *config*))
            payload {:actor actor :activity activity :objectId object-id
                     :objectType object-type :attributes (or attributes {})}
            headers (cond-> {"Content-Type" "application/json"}
                      (seq internal-secret) (assoc "x-internal-trust" internal-secret))]
        (*post!* (str dispatcher-url "/xrpc/com.etzhayyim.generic.audit.emit")
                 {:headers headers
                  :body (json/generate-string payload)
                  :timeout (:timeout-ms *config*)
                  :throw false}))
      (catch Exception e
        (binding [*out* *err*]
          (println "audit.emit failed (non-fatal):" (.getMessage e) "| activity=" activity))))
    nil))

(defn emit-audit-bg
  "Fire-and-forget: schedules emit-audit! on a future."
  [m]
  (future (emit-audit! m)))

(ns lgx.audit
  "Fire-and-forget BPMN `generic.audit.emit` shim — clj port of `lg_x/audit.py`.

  Per the original (user choice 2026-05-08): keep the OCEL audit trail by
  dispatching `generic.audit.emit` to bpmn-dispatcher from each LangGraph node.
  Preserves `vertex_repo_commit` OCEL traces / process-mining dashboards / RACI
  evidence without re-implementing the OCEL schema.

  Port notes (ADR-2606280030 / #2612 httpx→bb):
    - httpx.AsyncClient → babashka.http-client (`http/post`)
    - JSON               → cheshire (`json/generate-string`)
    - asyncio.create_task fire-and-forget → `future` (best-effort, never blocks)

  The dispatch is fire-and-forget: a failure to emit MUST NOT block the node.
  Audit loss is logged (to *err*) but never raised."
  (:require [cheshire.core :as json]
            [kotoba.lang.text :as str]))

(def default-config
  {:app-did "did:web:x.etzhayyim.com"
   :rw-url ""
   :dispatcher-url "http://bpmn-dispatcher.mitama-udf.svc.cluster.local:8080"
   :internal-secret ""
   :audit-timeout-ms 3000
   :llm {:base-url "http://127.0.0.1:4000/v1"
         :model "tier0-general"
         :timeout-ms 60000}})

(defn config [state] (merge default-config (or (:host-config state) {})))

(defn http-emit-with [http-post host-config payload]
  (when-not (fn? http-post)
    (throw (ex-info "X audit requires an explicit HTTP POST capability"
                    {:capability :x/audit-http-post})))
  (let [{:keys [dispatcher-url internal-secret audit-timeout-ms]}
        (merge default-config (or host-config {}))
        dispatcher-url (str/replace dispatcher-url #"/+$" "")
        headers (cond-> {"Content-Type" "application/json"}
                  (seq internal-secret) (assoc "x-internal-trust" internal-secret))]
    (http-post (str dispatcher-url "/xrpc/com.etzhayyim.generic.audit.emit")
               {:headers headers :body (json/generate-string payload)
                :timeout audit-timeout-ms :throw false})))

(def ^:dynamic *emit* (fn [_host-config _payload] nil))

(defn emit-audit
  "Send one OCEL event to BPMN dispatcher's `generic.audit.emit` (synchronous,
  best-effort). Failure is logged, never raised — the LangGraph state checkpoint
  is the source of truth for resumability."
  [host-config {:keys [actor activity object-id object-type attributes]}]
  (let [payload {:actor actor
                   :activity activity
                   :objectId object-id
                   :objectType object-type
                   :attributes (or attributes {})}]
    (try (*emit* host-config payload)
         (catch Exception exc
           (binding [*out* *err*]
             (println (str "audit.emit failed (non-fatal): " (.getMessage exc)
                           " | activity=" activity " id=" object-id)))
           nil))))

(defn emit-audit-bg
  "Schedule `emit-audit` on a background thread without awaiting it (the clj
  analogue of asyncio.create_task). Returns the future."
  [state m]
  (future (emit-audit (config state) m)))

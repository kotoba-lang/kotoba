(ns kotoba.capability.http.fetch.provider
  "JVM reference host provider for actor:host field \"http_fetch\".

  The core in `artifacts/provider.core.wasm` returns -3 from every call: a
  network read has no in-wasm implementation, so the artifact's job is to make
  the UNBOUND state loud. This namespace is what an embedder binds over it.

  ## The policy is not a parameter the guest can pass

  `provider` closes over the allowlist. The guest hands in a URL and nothing
  else — it cannot widen its own egress, and there is no field in the ABI
  through which it could try. That is the whole reason the policy is taken at
  construction rather than read from guest memory.

  ## Return codes are the contract

     >= 0  bytes written
     -1    refused by policy      (a decision was made; see the receipt)
     -2    transport failed       (a request went out and did not come back)
     -3    no host provider bound (nothing was attempted)

  -1 and -2 must not collapse. `bin/itonami` keeps the same two apart in its
  exit codes and says why: \"'The server said no' is a measurement; 'nothing was
  listening' is not, and an operator sent to read a refusal that never happened
  debugs the wrong thing\" (ADR-2608136000)."
  (:require [kotoba.capability.http.fetch.egress :as egress])
  (:import [java.net URI]
           [java.net.http HttpClient HttpClient$Redirect HttpRequest
                          HttpRequest$BodyPublishers HttpResponse$BodyHandlers]
           [java.nio.charset StandardCharsets]
           [java.time Duration]))

(def code-refused -1)
(def code-transport -2)
(def code-unbound -3)

(def default-limits
  {:timeout-seconds 20
   ;; A cap the CALLER cannot raise. Without one, a capability whose whole
   ;; point is bounded authority hands an unbounded read to whoever holds it.
   :max-bytes (* 1024 1024)})

(defn- client ^HttpClient [{:keys [timeout-seconds]}]
  (-> (HttpClient/newBuilder)
      (.connectTimeout (Duration/ofSeconds (long (or timeout-seconds 20))))
      ;; Redirects are NEVER followed. A 302 to a host outside the allowlist
      ;; would carry the request there with the policy already satisfied --
      ;; the decision was made about the first URL and executed against the
      ;; second. Following redirects would make `admit` advisory.
      (.followRedirects HttpClient$Redirect/NEVER)
      (.build)))

(defn fetch
  "Fetch `url` under `policy`, returning a receipt. Never throws.

  The receipt always says which of the four outcomes happened, because a
  caller that cannot tell a refusal from a timeout cannot act on either."
  [policy url & [{:keys [method] :as opts}]]
  (let [limits (merge default-limits opts)
        m (or method "GET")
        decision (egress/admit policy url m)]
    (if-not (:allowed? decision)
      {:schema egress/schema :ok? false :code code-refused
       :reason (:reason decision) :message (:message decision)}
      (try
        (let [req (-> (HttpRequest/newBuilder (URI/create (str url)))
                      (.timeout (Duration/ofSeconds (long (:timeout-seconds limits))))
                      (.method m (HttpRequest$BodyPublishers/noBody))
                      (.build))
              resp (.send (client limits) req (HttpResponse$BodyHandlers/ofByteArray))
              body (.body resp)
              n (alength ^bytes body)]
          (if (> n (long (:max-bytes limits)))
            {:schema egress/schema :ok? false :code code-refused
             :reason :egress/body-too-large
             :message (str "本文が上限を超えました: " n " > " (:max-bytes limits))}
            {:schema egress/schema :ok? true :code n
             :status (.statusCode resp)
             :host (:host decision)
             :body body}))
        (catch Exception e
          ;; A request that went out and did not come back. NOT -1: nothing
          ;; refused it.
          {:schema egress/schema :ok? false :code code-transport
           :reason :http/transport-failed
           :message (str (.getMessage e))})))))

(defn provider
  "A host provider bound to one egress `policy`.

  With no policy this still returns a provider — one that refuses every call
  with `:egress/no-policy`. Refusing to CONSTRUCT would push the failure to
  startup, where it reads as a broken embedder rather than as an unconfigured
  capability; refusing to CALL keeps the fact where an operator can see it."
  [policy]
  {:schema egress/schema
   :policy policy
   :fetch (fn [url & [opts]] (fetch policy url opts))})

(defn host-export
  "The actor:host binding an embedder installs over the core's -3."
  [policy]
  {:module "kotoba"
   :field "http_fetch"
   :params [:i32 :i32 :i32 :i32]
   :result :i32
   :fn (:fetch (provider policy))})

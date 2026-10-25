(ns example.worker
  "How a Worker wires the gate in. Illustrative -- this repo builds no Worker
  of its own; consumers bring their own shadow-cljs build and wrangler config.

  Two habits are worth copying:

  1. `preflight` runs once at module scope, not per request. A deployment
     whose bindings do not match its policy should be loud immediately, not on
     the first write of the day.

  2. `now` comes from the request, and receipts are emitted for every attempt
     including denials. A denial that only shows up as a 403 to the caller is
     a denial the operator never sees."
  (:require [cloudflare.workers.provider :as provider]
            [cloudflare.workers.receipt :as receipt]))

;; Host-owned policy. In a real Worker this is a resource compiled into the
;; bundle or fetched from a signed source -- never anything a request body,
;; a guest, or an LLM can influence.
(def policy
  {:policy/bindings
   {"SESSIONS" {:kind :kv
                :caps #{:cf/kv-read :cf/kv-write}
                :key-prefixes #{"user:"}
                :max-value-bytes 4096
                :min-ttl 60
                :max-ttl 3600}
    "APP_DB" {:kind :d1
              :caps #{:cf/d1-read :cf/d1-write}
              :statements
              {"order-by-id" {:sql "select id, qty from orders where id = ?1"
                              :arity 1 :mode :read}
               "insert-order" {:sql "insert into orders (id, qty) values (?1, ?2)"
                               :arity 2 :mode :write}}}}
   :policy/quota {:max-commands 16 :max-write-bytes 65536}})

(defn- audit!
  [receipts]
  (doseq [r receipts]
    (js/console.log (receipt/summarize r))))

(defn- plan
  "Whatever produces commands: a compiled `.kotoba` guest, or plain
  ClojureScript today. Either way the output is inert data until the gate
  admits it."
  [order-id qty]
  [{:cmd :cf.d1/exec :binding "APP_DB" :statement "insert-order"
    :params [order-id qty]}
   {:cmd :cf.kv/put :binding "SESSIONS" :key (str "user:" order-id)
    :value "pending" :ttl 300}])

(def ^:private startup-problems (atom nil))

(defn handle-request
  [request env]
  (let [now (.toISOString (js/Date.))]
    (when (nil? @startup-problems)
      (reset! startup-problems (provider/preflight env policy))
      (doseq [p @startup-problems]
        (js/console.error "policy/deployment mismatch:" (pr-str p))))
    (if (seq @startup-problems)
      (js/Promise.resolve (js/Response. "misconfigured" #js {:status 500}))
      (-> (provider/execute! {:env env
                              :policy policy
                              :commands (plan "o-1" 2)
                              :now now})
          (.then (fn [result]
                   (audit! (:receipts result))
                   (case (:outcome result)
                     :allowed (js/Response. (js/JSON.stringify
                                             (clj->js (:events result)))
                                            #js {:status 200})
                     ;; A denial is a bug in the plan or a gap in the policy.
                     ;; It is never retried with a wider policy at runtime.
                     :denied (js/Response. "forbidden" #js {:status 403})
                     :failed (js/Response. "storage unavailable"
                                           #js {:status 503}))))))))

(def handler
  #js {:fetch (fn [request env _ctx] (handle-request request env))})

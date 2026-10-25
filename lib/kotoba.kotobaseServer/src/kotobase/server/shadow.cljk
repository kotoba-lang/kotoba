(ns kotobase.server.shadow
  "Failure-isolated shadow routing for engine migrations.

  This namespace knows nothing about kotobase-peer or IEngine. A deployment
  injects two handlers with the same wire contract. Primary always owns the
  response; shadow work is scheduled for comparison and can never change a
  successful primary result. This keeps XRPC translation outside either
  storage engine and lets a Worker pass the task to `waitUntil`."
  (:require [kotoba.lang.text :as str]))

(defn- valid-config!
  [{:keys [primary-handle shadow-handle schedule! observe! normalize eligible?]}]
  (doseq [[key value] [[:primary-handle primary-handle]
                       [:shadow-handle shadow-handle]
                       [:schedule! schedule!]
                       [:observe! observe!]
                       [:normalize normalize]
                       [:eligible? eligible?]]]
    (when-not (ifn? value)
      (throw (ex-info "shadow router requires an injected function"
                      {:type :kotobase.server.shadow/invalid-config
                       :key key}))))
  true)

(defn- observe-safely! [observe! event]
  (try
    (observe! event)
    (catch #?(:clj Throwable :cljs :default) _ nil)))

(defn- comparison-event [normalize method primary shadow]
  (let [primary* (normalize primary)
        shadow* (normalize shadow)]
    {:shadow/status (if (= primary* shadow*) :match :mismatch)
     :method method
     :primary primary*
     :shadow shadow*}))

(defn- run-shadow!
  [shadow-handle observe! normalize method body auth primary]
  #?(:clj
     (try
       (observe-safely!
        observe! (comparison-event normalize method primary
                                   (shadow-handle method body auth)))
       (catch Throwable error
         (observe-safely!
          observe! {:shadow/status :failed :method method
                    :error-class (.getName (class error))
                    :error-message (.getMessage error)})))
     :cljs
     (try
       (-> (js/Promise.resolve (shadow-handle method body auth))
           (.then (fn [shadow]
                    (observe-safely!
                     observe! (comparison-event normalize method primary shadow))))
           (.catch (fn [error]
                     (observe-safely!
                      observe! {:shadow/status :failed :method method
                                :error-name (.-name error)
                                :error-message (.-message error)}))))
       (catch :default error
         (observe-safely!
          observe! {:shadow/status :failed :method method
                    :error-name (.-name error)
                    :error-message (.-message error)})))))

(defn wrap-handler
  "Return a `(fn [method body auth])` migration handler.

  `schedule!` receives a zero-argument task. A Cloudflare shell should call
  the task and register its Promise with `ctx.waitUntil`; tests or JVM hosts
  may use `(fn [task] (task))`. `normalize` removes expected physical
  differences (for example engine-specific roots) before equality. `eligible?`
  supports per-method or sampled rollout. Neither shadow nor observer failure
  is allowed to affect the primary response."
  [{:keys [primary-handle shadow-handle schedule! observe! normalize eligible?]
    :or {schedule! (fn [task] (task))
         observe! (constantly nil)
         normalize identity
         eligible? (constantly true)}
    :as config}]
  (valid-config! (assoc config
                        :schedule! schedule! :observe! observe!
                        :normalize normalize :eligible? eligible?))
  (fn [method body auth]
    (when-not (and (string? method) (not (str/blank? method)))
      (throw (ex-info "shadow router requires a method"
                      {:type :kotobase.server.shadow/invalid-method})))
    #?(:clj
       (let [primary (primary-handle method body auth)]
         (when (eligible? method body auth)
           (try
             (schedule! #(run-shadow! shadow-handle observe! normalize
                                      method body auth primary))
             (catch Throwable _ nil)))
         primary)
       :cljs
       (-> (js/Promise.resolve (primary-handle method body auth))
           (.then
            (fn [primary]
              (when (eligible? method body auth)
                (try
                  (schedule! #(run-shadow! shadow-handle observe! normalize
                                           method body auth primary))
                  (catch :default _ nil)))
              primary))))))

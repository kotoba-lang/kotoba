(ns authentication.kv-smoke
  (:require [authentication.adapters.cloudflare-kv :as cf]
            [authentication.identity-ports :as ports]))

(def values (atom {}))
(def kv
  #js {:get (fn [key] (js/Promise.resolve (get @values key)))
       :put (fn [key value _] (swap! values assoc key value) (js/Promise.resolve nil))
       :delete (fn [key] (swap! values dissoc key) (js/Promise.resolve nil))})

(defn fail! [error] (js/console.error error) (set! (.-exitCode js/process) 1))

(defn ^:export main []
  (let [store (cf/store {:kv kv :prefix "test:" :random-id (constantly "v1")})]
    (-> (ports/-put-once! store "oauth:state" {:provider :google} 300)
        (.then (fn [version]
                 (when-not (= "v1" version) (throw (js/Error. "put-once failed")))
                 (ports/-get-value store "oauth:state")))
        (.then (fn [record]
                 (when-not (= "google" (get-in record [:value :provider]))
                   (throw (js/Error. "KV decode failed")))
                 (ports/-consume! store "oauth:state" (:version record))))
        (.then (fn [value]
                 (when-not (= "google" (:provider value))
                   (throw (js/Error. "consume failed")))
                 (ports/-get-value store "oauth:state")))
        (.then (fn [missing]
                 (when missing (throw (js/Error. "consume was not single-use")))
                 (js/console.log "ok - Cloudflare KV ephemeral adapter")))
        (.catch fail!))))

(main)

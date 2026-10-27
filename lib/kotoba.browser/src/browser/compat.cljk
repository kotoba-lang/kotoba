(ns browser.compat
  "Web compatibility adapter contract.

   A compat engine is a WASM component that receives no ambient DOM/network
   access. Browser-like Web APIs are represented as capability requests."
  (:require [browser.origin :as origin]))

(def capability-set
  #{:dom/query
    :dom/mutate
    :event/listen
    :event/remove
    :event/dispatch
    :console/log
    :net/fetch
    :storage/get
    :storage/put
    :storage/delete
    :cookie/get
    :cookie/set
    :clipboard/read
    :clipboard/write
    :window/open
    :location/assign
    :location/replace
    :location/reload
    :permissions/query
    :geolocation/read
    :notification/request-permission
    :notification/show
    :notification/close
    :fullscreen/request
    :fullscreen/exit
    :media/capture
    :websocket/connect
    :websocket/send
    :websocket/close
    :crypto/random-values
    :crypto/random-uuid
    :worker/create
    :worker/post-message
    :worker/terminate
    :broadcast/open
    :broadcast/post-message
    :broadcast/close
    :beacon/send
    :history/push-state
    :history/replace-state
    :history/traverse
    :timer/schedule
    :timer/cancel
    :timer/microtask
    :js/call})

(defn adapter
  [{:keys [engine wasm-component origin profile-id capabilities] :as opts}]
  {:compat/engine engine
   :compat/wasm-component wasm-component
   :compat/origin (origin/origin origin)
   :compat/profile-id profile-id
   :compat/capabilities (or capabilities capability-set)
   :compat/meta (dissoc opts :engine :wasm-component :origin :profile-id :capabilities)})

(defn allowed?
  [adapter capability]
  (contains? (:compat/capabilities adapter) capability))

(defn request
  [adapter capability payload]
  (if (allowed? adapter capability)
    (merge {:compat/request true
            :capability capability
            :origin (:compat/origin adapter)
            :profile/id (:compat/profile-id adapter)
            :engine (:compat/engine adapter)}
           payload)
    {:compat/request false
     :capability capability
     :origin (:compat/origin adapter)
     :profile/id (:compat/profile-id adapter)
     :engine (:compat/engine adapter)
     :error :capability/not-granted}))

(defn requests
  [adapter calls]
  (mapv (fn [[capability payload]]
          (request adapter capability payload))
        calls))

(ns browser.compat.webapi
  "Browser-like Web API shims expressed as capability requests."
  (:require [browser.compat :as compat]))

(defn document-create-element
  [adapter tag attrs]
  (compat/request adapter :dom/mutate
                  {:dom/op :create-element
                   :tag tag
                   :attrs (or attrs {})}))

(defn document-create-element-ns
  [adapter namespace-uri qualified-name attrs]
  (document-create-element adapter
                           qualified-name
                           (assoc (or attrs {}) :namespace-uri namespace-uri)))

(defn document-create-fragment
  [adapter]
  (compat/request adapter :dom/mutate
                  {:dom/op :create-fragment}))

(defn clone-node
  [adapter source-id deep?]
  (compat/request adapter :dom/mutate
                  {:dom/op :clone-node
                   :source/id source-id
                   :deep? (boolean deep?)}))

(defn set-inner-html
  [adapter node-id html]
  (compat/request adapter :dom/mutate
                  {:dom/op :set-inner-html
                   :node/id node-id
                   :html html}))

(defn set-outer-html
  [adapter node-id html]
  (compat/request adapter :dom/mutate
                  {:dom/op :set-outer-html
                   :node/id node-id
                   :html html}))

(defn set-text
  [adapter node-id text]
  (compat/request adapter :dom/mutate
                  {:dom/op :set-text
                   :node/id node-id
                   :text text}))

(defn split-text
  [adapter node-id offset]
  (compat/request adapter :dom/mutate
                  {:dom/op :split-text
                   :node/id node-id
                   :offset offset}))

(defn normalize-node
  [adapter node-id]
  (compat/request adapter :dom/mutate
                  {:dom/op :normalize
                   :node/id node-id}))

(defn query-selector
  [adapter selector]
  (compat/request adapter :dom/query
                  {:dom/query :query-selector
                   :selector selector}))

(defn query-selector-all
  [adapter selector]
  (compat/request adapter :dom/query
                  {:dom/query :query-selector-all
                   :selector selector}))

(defn get-element-by-id
  [adapter id]
  (compat/request adapter :dom/query
                  {:dom/query :get-element-by-id
                   :id id}))

(defn set-attribute
  [adapter node-id k v]
  (compat/request adapter :dom/mutate
                  {:dom/op :set-attribute
                   :node/id node-id
                   :attr k
                   :value v}))

(defn class-list-set
  [adapter node-id class-value]
  (set-attribute adapter node-id "class" class-value))

(defn append-child
  [adapter parent-id child-id]
  (compat/request adapter :dom/mutate
                  {:dom/op :append-child
                   :parent/id parent-id
                   :child/id child-id}))

(defn remove-child
  [adapter parent-id child-id]
  (compat/request adapter :dom/mutate
                  {:dom/op :remove-child
                   :parent/id parent-id
                   :child/id child-id}))

(defn insert-before
  [adapter parent-id child-id before-id]
  (compat/request adapter :dom/mutate
                  {:dom/op :insert-before
                   :parent/id parent-id
                   :child/id child-id
                   :before/id before-id}))

(defn replace-children
  [adapter node-id]
  (compat/request adapter :dom/mutate
                  {:dom/op :remove-children
                   :node/id node-id}))

(defn add-event-listener
  [adapter node-id event-type handler-id]
  (compat/request adapter :event/listen
                  {:node/id node-id
                   :event/type event-type
                   :handler/id handler-id}))

(defn remove-event-listener
  [adapter node-id event-type handler-id]
  (compat/request adapter :event/remove
                  {:node/id node-id
                   :event/type event-type
                   :handler/id handler-id}))

(defn dispatch-event
  [adapter node-id event]
  (compat/request adapter :event/dispatch
                  {:node/id node-id
                   :event event}))

(defn console-log
  [adapter level args]
  (compat/request adapter :console/log
                  {:console/level level
                   :args (vec args)}))

(defn fetch
  [adapter url opts]
  (compat/request adapter :net/fetch
                  {:url url
                   :request (merge {:method :get} opts)}))

(defn storage-get
  [adapter k]
  (compat/request adapter :storage/get
                  {:storage/key k}))

(defn storage-put
  [adapter k v]
  (compat/request adapter :storage/put
                  {:storage/key k
                   :storage/value v}))

(defn storage-delete
  [adapter k]
  (compat/request adapter :storage/delete
                  {:storage/key k}))

(defn cookie-get
  [adapter]
  (compat/request adapter :cookie/get
                  {:cookie/op :get}))

(defn cookie-set
  [adapter cookie]
  (compat/request adapter :cookie/set
                  {:cookie/op :set
                   :cookie/value (str cookie)}))

(defn clipboard-read-text
  [adapter]
  (compat/request adapter :clipboard/read
                  {:clipboard/format :text}))

(defn clipboard-write-text
  [adapter text]
  (compat/request adapter :clipboard/write
                  {:clipboard/format :text
                   :text (str text)}))

(defn window-open
  ([adapter url]
   (window-open adapter url "_blank" nil))
  ([adapter url target features]
   (compat/request adapter :window/open
                   (cond-> {:url (str url)
                            :target (str (or target "_blank"))}
                     (some? features)
                     (assoc :window/features (str features))))))

(defn location-assign
  [adapter url]
  (compat/request adapter :location/assign
                  {:url (str url)}))

(defn location-replace
  [adapter url]
  (compat/request adapter :location/replace
                  {:url (str url)}))

(defn location-reload
  [adapter]
  (compat/request adapter :location/reload
                  {:location/op :reload}))

(defn permission-query
  [adapter permission-name]
  (compat/request adapter :permissions/query
                  {:permission/name (str permission-name)}))

(defn geolocation-current-position
  ([adapter]
   (geolocation-current-position adapter nil))
  ([adapter opts]
   (compat/request adapter :geolocation/read
                   (cond-> {:geolocation/op :current-position}
                     (map? opts)
                     (assoc :geolocation/options opts)))))

(defn notification-request-permission
  [adapter]
  (compat/request adapter :notification/request-permission
                  {:notification/op :request-permission}))

(defn notification-show
  ([adapter title]
   (notification-show adapter title nil))
  ([adapter title opts]
   (compat/request adapter :notification/show
                   (cond-> {:title (str title)}
                     (map? opts)
                     (assoc :notification/options opts)))))

(defn fullscreen-request
  ([adapter node-id]
   (fullscreen-request adapter node-id nil))
  ([adapter node-id opts]
   (compat/request adapter :fullscreen/request
                   (cond-> {:node/id node-id}
                     (map? opts)
                     (assoc :fullscreen/options opts)))))

(defn fullscreen-exit
  [adapter]
  (compat/request adapter :fullscreen/exit
                  {:fullscreen/op :exit}))

(defn media-get-user-media
  [adapter constraints]
  (compat/request adapter :media/capture
                  {:media/op :get-user-media
                   :media/constraints (or constraints {})}))

(defn websocket-connect
  ([adapter url]
   (websocket-connect adapter url nil))
  ([adapter url protocols]
   (compat/request adapter :websocket/connect
                   (cond-> {:url (str url)}
                     (some? protocols)
                     (assoc :websocket/protocols protocols)))))

(defn websocket-send
  [adapter connection-id data]
  (compat/request adapter :websocket/send
                  {:websocket/id connection-id
                   :data (str data)}))

(defn websocket-close
  ([adapter connection-id]
   (websocket-close adapter connection-id nil nil))
  ([adapter connection-id code reason]
   (compat/request adapter :websocket/close
                   (cond-> {:websocket/id connection-id}
                     (some? code) (assoc :code code)
                     (some? reason) (assoc :reason (str reason))))))

(defn crypto-random-values
  [adapter length]
  (compat/request adapter :crypto/random-values
                  {:crypto/op :random-values
                   :length length}))

(defn crypto-random-uuid
  [adapter]
  (compat/request adapter :crypto/random-uuid
                  {:crypto/op :random-uuid}))

(defn worker-create
  ([adapter url]
   (worker-create adapter url nil))
  ([adapter url opts]
   (compat/request adapter :worker/create
                   (cond-> {:url (str url)}
                     (map? opts)
                     (assoc :worker/options opts)))))

(defn worker-post-message
  [adapter worker-id message]
  (compat/request adapter :worker/post-message
                  {:worker/id worker-id
                   :message message}))

(defn worker-terminate
  [adapter worker-id]
  (compat/request adapter :worker/terminate
                  {:worker/id worker-id}))

(defn broadcast-open
  [adapter channel-name]
  (compat/request adapter :broadcast/open
                  {:broadcast/name (str channel-name)}))

(defn broadcast-post-message
  [adapter channel-id message]
  (compat/request adapter :broadcast/post-message
                  {:broadcast/id channel-id
                   :message message}))

(defn broadcast-close
  [adapter channel-id]
  (compat/request adapter :broadcast/close
                  {:broadcast/id channel-id}))

(defn beacon-send
  ([adapter url]
   (beacon-send adapter url nil))
  ([adapter url data]
   (compat/request adapter :beacon/send
                   (cond-> {:url (str url)}
                     (some? data)
                     (assoc :data data)))))

(defn history-push-state
  [adapter state title url]
  (compat/request adapter :history/push-state
                  {:state state
                   :title (str (or title ""))
                   :url (str url)}))

(defn history-replace-state
  [adapter state title url]
  (compat/request adapter :history/replace-state
                  {:state state
                   :title (str (or title ""))
                   :url (str url)}))

(defn history-go
  [adapter delta]
  (compat/request adapter :history/traverse
                  {:delta delta}))

(defn history-back
  [adapter]
  (history-go adapter -1))

(defn history-forward
  [adapter]
  (history-go adapter 1))

(defn set-timeout
  [adapter callback-id delay-ms]
  (compat/request adapter :timer/schedule
                  {:timer/kind :timeout
                   :callback/id callback-id
                   :delay-ms delay-ms}))

(defn clear-timeout
  [adapter callback-id]
  (compat/request adapter :timer/cancel
                  {:timer/kind :timeout
                   :callback/id callback-id}))

(defn request-animation-frame
  [adapter callback-id]
  (compat/request adapter :timer/schedule
                  {:timer/kind :animation-frame
                   :callback/id callback-id
                   :delay-ms 0}))

(defn cancel-animation-frame
  [adapter callback-id]
  (compat/request adapter :timer/cancel
                  {:timer/kind :animation-frame
                   :callback/id callback-id}))

(defn queue-microtask
  [adapter callback-id]
  (compat/request adapter :timer/microtask
                  {:timer/kind :microtask
                   :callback/id callback-id}))

(def webapi-surface
  {:document [:body :documentElement :head :activeElement
              :URL :documentURI :baseURI :currentScript :readyState :title
              :createElement :createElementNS :createDocumentFragment
              :createTextNode :getElementById
              :querySelector :querySelectorAll
              :getElementsByTagName :getElementsByClassName
              :forms :images :links :scripts]
   :element [:setAttribute :appendChild :removeChild :insertBefore :replaceChild :replaceChildren
             :getAttribute :hasAttribute :removeAttribute
             :addEventListener :removeEventListener :dispatchEvent :textContent :nodeValue :data :classList
             :append :prepend :before :after :replaceWith :remove
             :insertAdjacentHTML :insertAdjacentElement :insertAdjacentText
             :cloneNode :innerHTML :outerHTML
             :appendData :deleteData :insertData :replaceData :substringData
             :splitText :normalize
             :querySelector :querySelectorAll :getElementsByTagName :getElementsByClassName
             :parentElement :firstChild :lastChild
             :firstElementChild :lastElementChild :previousSibling :nextSibling
             :previousElementSibling :nextElementSibling :nodeName :localName :namespaceURI
             :ownerDocument :isConnected :contains :toggleAttribute
             :dataset.delete :style.getPropertyValue :style.removeProperty
             :scrollTop :scrollLeft
             :focus :blur :form :labels :control :htmlFor
             :href :src :alt :async :defer :complete
             :options :selectedOptions :selectedIndex :selected
             :defaultSelected :checked :defaultChecked :defaultValue
             :disabled :required :readOnly :multiple]
   :window [:fetch :open :location :setTimeout :clearTimeout
            :requestAnimationFrame :cancelAnimationFrame
            :queueMicrotask :customElements
            :addEventListener :removeEventListener :dispatchEvent
            :console.log :console.info :console.warn :console.error :console.debug
            :Event :CustomEvent :MouseEvent :KeyboardEvent :MutationObserver
            :navigator.clipboard :navigator.permissions.query
            :navigator.geolocation.getCurrentPosition
            :Notification.requestPermission :Notification
            :Element.requestFullscreen :document.exitFullscreen]
   :media [:navigator.mediaDevices.getUserMedia]
   :network [:WebSocket]
   :beacon [:navigator.sendBeacon]
   :crypto [:crypto.getRandomValues :crypto.randomUUID]
   :worker [:Worker]
   :channel [:BroadcastChannel]
   :url [:URL :URLSearchParams]
   :storage [:localStorage.getItem :localStorage.setItem :localStorage.removeItem]})

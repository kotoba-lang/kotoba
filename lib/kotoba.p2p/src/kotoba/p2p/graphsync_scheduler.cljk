(ns kotoba.p2p.graphsync-scheduler
  "Pure bounded response scheduler for GraphSync v2 request lifecycles.

  Admission creates a read-free IPLD selection cursor. Scheduler steps advance
  it under an explicit CPU budget and read at most one new CID-verified block,
  so cancellation stops both future wire chunks and future storage reads."
  (:require [ipld.core :as ipld]
            [ipld.graph :as graph]
            [ipld.link :as link]
            [ipld.value :as value]
            [kotoba.p2p.graphsync :as gs]
            [kotoba.p2p.graphsync-extension :as extension]))

(def checkpoint-extension "kotoba.graphsync/checkpoint/1")

(defn- invalid! [message data]
  (throw (ex-info message (assoc data :type :graphsync/invalid-scheduler))))

(defn- positive! [config key]
  (let [value (get config key)]
    (when-not (and (integer? value) (pos? value))
      (invalid! "graphsync scheduler: positive limit required"
                {:limit key :value value}))
    value))

(defn new-scheduler
  "Create an empty scheduler. Required positive limits are `:max-active`,
  `:max-blocks-per-message`, `:max-block-bytes-per-message`, and
  `:max-traversal-work-per-step`."
  [config]
  (doseq [key [:max-active :max-blocks-per-message :max-block-bytes-per-message
               :max-traversal-work-per-step]]
    (positive! config key))
  (let [checkpoint-spec
        {:phases #{:update}
         :validate (fn [value]
                     (when-not (link/link? value)
                       (invalid! "graphsync scheduler: checkpoint extension must be an IPLD Link"
                                 {:value value}))
                     value)}
        registry (extension/registry
                  (positive! config :max-extensions)
                  (assoc (or (:extension-specs config) {})
                         checkpoint-extension checkpoint-spec))]
    {:config (assoc (select-keys config
                                 [:max-active :max-blocks-per-message
                                  :max-block-bytes-per-message
                                  :max-traversal-work-per-step])
                    :extension-registry registry)
   :active {}
   :next-order 0}))

(defn active-count [scheduler]
  (count (:active scheduler)))

(defn active-request-ids
  "Content-valued UUID byte vectors for active requests."
  [scheduler]
  (set (keys (:active scheduler))))

(defn checkpoint-request
  "Create content-addressed checkpoint bytes and a GraphSync extension value
  for one active request. The caller decides where to persist `:bytes`."
  [scheduler request-id]
  (let [key (vec request-id)
        entry (get-in scheduler [:active key])]
    (when-not entry
      (invalid! "graphsync scheduler: cannot checkpoint unknown request"
                {:id key}))
    (let [envelope {:request-id key
                    :root (get-in entry [:request :root])
                    :selector (get-in entry [:request :selector])
                    :limits (get-in entry [:cursor :limits])
                    :cursor-bytes (graph/checkpoint-cursor (:cursor entry))}
          bytes (value/encode-value envelope)
          cid (ipld/cid bytes)]
      {:cid cid :bytes bytes
       :extensions {checkpoint-extension (link/link cid)}})))

(defn persist-checkpoint!
  "Persist one active request checkpoint through caller-owned `put-fn` and
  return the CID extension plus the host receipt. `put-fn` receives CID, bytes."
  [scheduler request-id put-fn]
  (when-not (fn? put-fn)
    (invalid! "graphsync scheduler: checkpoint persistence requires put-fn" {}))
  (let [{:keys [cid bytes] :as checkpoint}
        (checkpoint-request scheduler request-id)]
    (assoc checkpoint :receipt (put-fn cid bytes))))

(defn restore-request
  "Restore an active request from CID-bound checkpoint bytes. Request id,
  root, selector, and traversal limits must all match the admitted request."
  [scheduler request-id checkpoint-cid bytes]
  (let [key (vec request-id)
        entry (get-in scheduler [:active key])]
    (when-not entry
      (invalid! "graphsync scheduler: cannot restore unknown request" {:id key}))
    (when-not (= checkpoint-cid (ipld/cid bytes))
      (invalid! "graphsync scheduler: checkpoint CID mismatch"
                {:id key :expected checkpoint-cid :actual (ipld/cid bytes)}))
    (let [envelope (value/decode-value bytes)
          cursor (graph/restore-cursor (:cursor-bytes envelope))
          expected {:request-id key
                    :root (get-in entry [:request :root])
                    :selector (get-in entry [:request :selector])
                    :limits (get-in entry [:cursor :limits])}
          actual (select-keys envelope [:request-id :root :selector :limits])]
      (when-not (= expected actual)
        (invalid! "graphsync scheduler: checkpoint request binding mismatch"
                  {:expected expected :actual actual}))
      (assoc-in scheduler [:active key :cursor] cursor))))

(defn- restore-from-extension [scheduler get-fn request]
  (if-let [checkpoint-link (get (:extensions request) checkpoint-extension)]
    (do
      (when-not (link/link? checkpoint-link)
        (invalid! "graphsync scheduler: checkpoint extension must be an IPLD Link"
                  {:value checkpoint-link}))
      (let [cid (link/link-cid checkpoint-link)
            bytes (or (ipld/get-verified-block get-fn cid)
                      (throw (ex-info "graphsync scheduler: checkpoint block is missing"
                                      {:type :ipld/missing-block :cid cid})))]
        (restore-request scheduler (:id request) cid bytes)))
    scheduler))

(defn- request-key [request]
  (vec (:id request)))

(defn- response [request status-code]
  {:id (:id request) :status status-code})

(defn- result-message [responses]
  (when (seq responses) {:responses (vec responses)}))

(defn- byte-length [bytes]
  #?(:clj (if (bytes? bytes) (alength ^bytes bytes) (count bytes))
     :cljs (if (vector? bytes) (count bytes) (.-length bytes))))

(defn- oversized-block? [scheduler block]
  (> (byte-length (:bytes block))
     (get-in scheduler [:config :max-block-bytes-per-message])))

(defn- admit-new [scheduler request traversal-limits]
  (let [key (request-key request)]
    (cond
      (contains? (:active scheduler) key)
      {:scheduler scheduler
       :response (response request (:rejected gs/status))
       :event {:type :request/rejected :reason :duplicate :id key}}

      (>= (active-count scheduler) (get-in scheduler [:config :max-active]))
      {:scheduler scheduler
       :response (response request (:failed-busy gs/status))
       :event {:type :request/rejected :reason :capacity :id key}}

      :else
      (try
        (let [extensions (extension/admit
                          (get-in scheduler [:config :extension-registry])
                          :new (:extensions request))
              request (assoc request :extensions extensions)
              entry {:request request
                     :priority (or (:priority request) 1)
                     :order (:next-order scheduler)
                     :extensions (or (:extensions request) {})
                     :cursor (graph/selection-cursor
                              (:root request) (:selector request) traversal-limits)}]
          {:scheduler (-> scheduler
                          (assoc-in [:active key] entry)
                          (update :next-order inc))
           :response (response request (:acknowledged gs/status))
           :event {:type :request/admitted :id key :reads 0}})
        (catch #?(:clj clojure.lang.ExceptionInfo :cljs :default) error
          (let [error-type (:type (ex-data error))
                status-code (case error-type
                              :ipld/missing-block (:content-not-found gs/status)
                              :ipld/resource-limit (:failed-unknown gs/status)
                              :graphsync/extension-rejected (:rejected gs/status)
                              (throw error))]
            {:scheduler scheduler
             :response (response request status-code)
             :event {:type :request/rejected :reason error-type :id key}}))))))

(defn- cancel [scheduler request]
  (let [key (request-key request)]
    (if (contains? (:active scheduler) key)
      {:scheduler (update scheduler :active dissoc key)
       :response (response request (:cancelled gs/status))
       :event {:type :request/cancelled :id key}}
      {:scheduler scheduler
       :event {:type :request/ignored :reason :unknown-cancel :id key}})))

(defn- update-extensions [scheduler get-fn request]
  (let [key (request-key request)]
    (if (contains? (:active scheduler) key)
      (let [extensions (extension/admit
                        (get-in scheduler [:config :extension-registry])
                        :update (:extensions request))
            request (assoc request :extensions extensions)
            restored? (contains? extensions checkpoint-extension)
            scheduler (restore-from-extension scheduler get-fn request)]
        {:scheduler (update-in scheduler [:active key :extensions]
                               merge (:extensions request))
         :event {:type (if restored? :request/restored :request/updated)
                 :id key :extensions (set (keys (:extensions request)))}})
      {:scheduler scheduler
       :event {:type :request/ignored :reason :unknown-update :id key}})))

(defn handle-message
  "Handle the request side of one decoded GraphSync message in list order.
  Returns `{:scheduler :message? :events}`. Unknown cancel/update messages are
  ignored, matching go-graphsync response-manager behavior."
  [scheduler get-fn message traversal-limits]
  (when-not (= #{:requests} (set (keys message)))
    (invalid! "graphsync scheduler: responder accepts request-only messages"
              {:message-keys (set (keys message))}))
  (let [result
        (reduce
         (fn [{:keys [scheduler responses events]} request]
           (let [handled (case (:type request)
                           :new (admit-new scheduler request traversal-limits)
                           :cancel (cancel scheduler request)
                           :update (update-extensions scheduler get-fn request)
                           (invalid! "graphsync scheduler: unknown request type"
                                     {:request request}))]
             {:scheduler (:scheduler handled)
              :responses (cond-> responses (:response handled)
                           (conj (:response handled)))
              :events (conj events (:event handled))}))
         {:scheduler scheduler :responses [] :events []}
         (:requests message))]
    (cond-> {:scheduler (:scheduler result) :events (:events result)}
      (seq (:responses result))
      (assoc :message (result-message (:responses result))))))

(defn- scheduled-entry [scheduler]
  (first
   (sort-by (juxt (comp - :priority val) (comp :order val))
            (:active scheduler))))

(defn step
  "Advance the highest-priority request under its CPU budget and emit at most
  one newly read block. Equal priorities retain admission order."
  [scheduler get-fn]
  (if-let [[key {:keys [request cursor]}] (scheduled-entry scheduler)]
    (try
      (let [advanced (graph/advance-cursor
                      cursor get-fn
                      (get-in scheduler [:config :max-traversal-work-per-step]))
            next-cursor (:cursor advanced)]
        (cond
          (:block advanced)
          (let [block (:block advanced)]
            (if (oversized-block? scheduler block)
              {:scheduler (update scheduler :active dissoc key)
               :message (result-message
                         [(response request (:failed-unknown gs/status))])
               :event {:type :request/rejected :reason :block-too-large
                       :id key :cid (:cid block)}}
              {:scheduler (assoc-in scheduler [:active key :cursor] next-cursor)
               :message {:responses [{:id (:id request)
                                      :status (:partial-response gs/status)
                                      :metadata [{:cid (:cid block)
                                                  :action :present}]}]
                         :blocks [block]}
               :event {:type :response/partial :id key :blocks 1}}))

          (:done? advanced)
          {:scheduler (update scheduler :active dissoc key)
           :message (result-message
                     [(response request (:completed-full gs/status))])
           :event {:type :response/completed :id key :blocks 0}}

          (:yielded? advanced)
          {:scheduler (assoc-in scheduler [:active key :cursor] next-cursor)
           :message (result-message [(response request (:paused gs/status))])
           :event {:type :response/paused :reason :work-budget :id key}}

          :else
          (invalid! "graphsync scheduler: cursor made no observable progress"
                    {:id key})) )
      (catch #?(:clj clojure.lang.ExceptionInfo :cljs :default) error
        (let [error-type (:type (ex-data error))
              status-code (case error-type
                            :ipld/missing-block (:content-not-found gs/status)
                            :ipld/resource-limit (:failed-unknown gs/status)
                            (throw error))]
          {:scheduler (update scheduler :active dissoc key)
           :message (result-message [(response request status-code)])
           :event {:type :request/failed :reason error-type :id key}})))
    {:scheduler scheduler :message nil :event {:type :scheduler/idle}}))

(defn drain
  "Step until idle, bounded by positive `max-messages`. Returns emitted
  messages and the final scheduler."
  [scheduler get-fn max-messages]
  (when-not (and (integer? max-messages) (pos? max-messages))
    (invalid! "graphsync scheduler: positive drain limit required"
              {:max-messages max-messages}))
  (loop [scheduler scheduler messages [] events [] remaining max-messages]
    (if (zero? (active-count scheduler))
      {:scheduler scheduler :messages messages :events events}
      (do
        (when (zero? remaining)
          (throw (ex-info "graphsync scheduler: drain limit exceeded"
                          {:type :graphsync/resource-limit
                           :limit :max-messages :maximum max-messages})))
        (let [result (step scheduler get-fn)]
          (recur (:scheduler result) (conj messages (:message result))
                 (conj events (:event result)) (dec remaining)))))))

(ns comfyui.server
  "Deno/Fetch-compatible subset of the ComfyUI prompt server API."
  (:require [comfyui.exec :as exec]
            [comfyui.workflow :as workflow]))

(defn- json-response [status value]
  (js/Response. (js/JSON.stringify (clj->js value))
                #js {:status status
                     :headers #js {"content-type" "application/json"}}))

(defn- error-response [status error]
  (json-response status {:error {:type "prompt_outputs_failed_validation"
                                 :message (or (.-message error) (str error))}
                         :node_errors (or (:errors (ex-data error)) [])}))

(defn- input-info [inputs]
  (reduce-kv
   (fn [result name {:keys [type optional] :as spec}]
     (update result (if optional :optional :required) assoc name
             [type (dissoc spec :type :optional)]))
   {:required {} :optional {}} inputs))

(defn- object-info [registry]
  (into (sorted-map)
        (map (fn [[type definition]]
               [type {:input (input-info (:inputs definition))
                      :input_order {:required (vec (keys (:inputs definition)))}
                      :output (mapv :type (:outputs definition))
                      :output_name (mapv :name (:outputs definition))
                      :name type :display_name type
                      :description "" :category (:category definition "")
                      :output_node (boolean (:output-node? definition))}]))
        @registry))

(defn- view-response [server* url]
  (try
    (let [root (get-in server* [:ctx :output-directory])
          filename (.get (.-searchParams url) "filename")
          subfolder (or (.get (.-searchParams url) "subfolder") "")
          _ (when-not (and (string? root) (seq root) (string? filename)
                           (seq filename))
              (throw (ex-info "invalid view request" {:status 400})))
          directory (js/Deno.realPathSync root)
          candidate (js/Deno.realPathSync (str root "/" subfolder "/" filename))
          _ (when-not (and (.startsWith candidate (str directory "/"))
                           (.-isFile (js/Deno.statSync candidate)))
              (throw (ex-info "view path escapes output directory" {:status 400})))]
      (js/Response. (js/Deno.readFileSync candidate)
                    #js {:status 200 :headers #js {"content-type" "image/png"}}))
    (catch :default error
      (json-response (or (:status (ex-data error)) 404)
                     {:error (or (.-message error) (str error))}))))

(defn server
  "Create one serialized async prompt service around an execution context."
  [ctx]
  {:ctx ctx
   :state (atom {:next-number 0 :pending [] :running nil :history {}})
   :clients (atom {})
   :pump-scheduled? (atom false)
   :tail (atom (js/Promise.resolve nil))})

(defn- queue-remaining [server*]
  (let [{:keys [pending running]} @(:state server*)]
    (+ (count pending) (if running 1 0))))

(defn- send-message! [socket type data]
  (when (= 1 (.-readyState socket))
    (try
      (.send socket (js/JSON.stringify (clj->js {:type type :data data})))
      (catch :default _ nil))))

(defn- broadcast! [server* type data]
  (doseq [[_ socket] @(:clients server*)]
    (send-message! socket type data))
  nil)

(defn- entry-sockets [server* entry]
  (let [clients @(:clients server*)]
    (if-let [client-id (:client-id entry)]
      (if-let [socket (get clients client-id)] [socket] [])
      (vals clients))))

(defn- emit! [server* entry type data]
  (doseq [socket (entry-sockets server* entry)]
    (send-message! socket type data))
  nil)

(defn- preview-frame [png-bytes]
  (let [frame (js/Uint8Array. (+ 8 (.-byteLength png-bytes)))
        view (js/DataView. (.-buffer frame))]
    (.setUint32 view 0 1 false)
    (.setUint32 view 4 2 false)
    (.set frame png-bytes 8)
    frame))

(defn- png-bytes? [bytes]
  (and (<= 8 (.-byteLength bytes))
       (= [137 80 78 71 13 10 26 10]
          (mapv #(aget bytes %) (range 8)))))

(defn- preview-file-frame [directory path]
  (try
    (when (string? path)
      (let [candidate (js/Deno.realPathSync path)]
        (when (and (.startsWith candidate (str directory "/"))
                   (.-isFile (js/Deno.statSync candidate)))
          (let [bytes (js/Deno.readFileSync candidate)]
            (when (png-bytes? bytes) (preview-frame bytes))))))
    (catch :default _ nil)))

(defn- emit-previews! [server* entry event]
  (try
    (let [root (get-in server* [:ctx :output-directory])
          images (->> (:output event) (filter map?) (mapcat :images))]
      (when (and (seq root) (seq images))
        (let [directory (js/Deno.realPathSync root)]
          (doseq [{:keys [path]} images]
            (when-let [frame (preview-file-frame directory path)]
              (doseq [socket (entry-sockets server* entry)]
                (when (= 1 (.-readyState socket))
                  (.send socket frame))))))))
    (catch :default _ nil))
  nil)

(defn- broadcast-status! [server*]
  (broadcast! server* "status"
              {:status {:exec_info {:queue_remaining (queue-remaining server*)}}}))

(defn- queue-item [{:keys [number id prompt extra-data outputs]}]
  [number id prompt extra-data outputs])

(defn- public-output [value]
  (if (and (map? value) (sequential? (:images value)))
    (update value :images
            #(mapv (fn [image]
                     (select-keys image [:filename :subfolder :type])) %))
    value))

(defn- history-outputs [registry prompt execution]
  (into {}
        (map (fn [id]
               (let [values (get-in execution [:results id])
                     value (first values)]
                 [id (if (map? value) (public-output value) {:value value})])))
        (workflow/output-nodes registry prompt)))

(declare schedule-pump!)

(defn- finish! [server* entry status execution error failed-node]
  (let [registry (get-in server* [:ctx :registry])
        history {:prompt (queue-item entry)
                 :outputs (if execution
                            (history-outputs registry (:prompt entry) execution) {})
                 :status {:status_str status :completed true
                          :messages (if error [["execution_error"
                                                {:prompt_id (:id entry)
                                                 :node_id failed-node
                                                 :exception_message
                                                 (or (.-message error) (str error))}]] [])}}]
    (swap! (:state server*)
           (fn [state]
             (-> state (assoc :running nil)
                 (assoc-in [:history (:id entry)] history))))
    (emit! server* entry "executing" {:node nil :prompt_id (:id entry)})
    (if error
      (emit! server* entry "execution_error"
             {:prompt_id (:id entry)
              :node_id failed-node
              :exception_message (or (.-message error) (str error))})
      (emit! server* entry "execution_success"
             {:prompt_id (:id entry) :timestamp (.now js/Date)}))
    (broadcast-status! server*)
    (schedule-pump! server*)
    nil))

(defn- pump! [server*]
  (reset! (:pump-scheduled? server*) false)
  (when (and (nil? (:running @(:state server*)))
             (seq (:pending @(:state server*))))
    (let [entry (first (:pending @(:state server*)))]
      (swap! (:state server*)
             #(-> % (assoc :running entry) (update :pending subvec 1)))
      (emit! server* entry "execution_start" {:prompt_id (:id entry)})
      (broadcast-status! server*)
      (let [original-on-node-start (get-in server* [:ctx :on-node-start])
            original-on-event (get-in server* [:ctx :on-event])
            active-node (atom nil)
            execution-ctx
            (assoc (:ctx server*)
                   :on-node-start
                   (fn [event]
                     (reset! active-node (:node event))
                     (when original-on-node-start (original-on-node-start event))
                     (emit! server* entry "executing"
                            {:node (:node event) :prompt_id (:id entry)}))
                   :on-event
                   (fn [event]
                     (when original-on-event (original-on-event event))
                     (emit-previews! server* entry event)))
            next (-> @(:tail server*)
                     (.catch (fn [_] nil))
                     (.then (fn [_]
                              (exec/execute-async execution-ctx (:prompt entry))))
                     (.then #(finish! server* entry "success" % nil nil))
                     (.catch #(finish! server* entry "error" nil % @active-node)))]
        (reset! (:tail server*) next)))))

(defn schedule-pump! [server*]
  (when (compare-and-set! (:pump-scheduled? server*) false true)
    (js/setTimeout #(pump! server*) 0))
  nil)

(defn- enqueue! [server* prompt extra-data client-id]
  (let [registry (get-in server* [:ctx :registry])
        validation (workflow/validate registry prompt)]
    (when-not (:valid? validation)
      (throw (ex-info "invalid prompt" validation)))
    (let [id (str (random-uuid))
          outputs (workflow/output-nodes registry prompt)
          result (atom nil)]
      (swap! (:state server*)
             (fn [{:keys [next-number] :as state}]
               (let [entry {:number next-number :id id :prompt prompt
                            :extra-data (or extra-data {}) :client-id client-id
                            :outputs outputs}]
                 (reset! result entry)
                 (-> state (update :next-number inc)
                     (update :pending conj entry)))))
      (schedule-pump! server*)
      (broadcast-status! server*)
      @result)))

(defn- queue-body [state]
  {:queue_running (if-let [entry (:running state)] [(queue-item entry)] [])
   :queue_pending (mapv queue-item (:pending state))})

(defn- parse-prompt-body [body]
  (let [body (js->clj body)
        prompt (get body "prompt")]
    {:prompt
     (when (map? prompt)
       (into {}
             (map (fn [[id instance]]
                    [id {:class_type (get instance "class_type")
                         :inputs (into {}
                                       (map (fn [[name value]] [(keyword name) value]))
                                       (get instance "inputs" {}))}]))
             prompt))
     :extra-data (get body "extra_data")
     :client-id (get body "client_id")}))

(defn- get-object-info [server* _ _]
  (js/Promise.resolve
   (json-response 200 (object-info (get-in server* [:ctx :registry])))))

(defn- get-queue [server* _ _]
  (js/Promise.resolve (json-response 200 (queue-body @(:state server*)))))

(defn- get-prompt-status [server* _ _]
  (js/Promise.resolve
   (json-response 200 {:exec_info {:queue_remaining (queue-remaining server*)}})))

(defn- post-queue [server* request _]
  (-> (.json request)
      (.then
       (fn [body]
         (let [{:strs [clear delete]} (js->clj body)
               deleted-ids (set delete)]
           (swap! (:state server*) update :pending
                  (fn [pending]
                    (if clear [] (vec (remove #(contains? deleted-ids (:id %))
                                               pending)))))
           (broadcast-status! server*)
           (json-response 200 {}))))
      (.catch #(error-response 400 %))))

(defn- post-prompt [server* request _]
  (-> (.json request)
      (.then (fn [body]
               (let [{:keys [prompt extra-data client-id]} (parse-prompt-body body)
                     entry (enqueue! server* prompt extra-data client-id)]
                 (json-response 200 {:prompt_id (:id entry)
                                     :number (:number entry)
                                     :node_errors {}}))))
      (.catch #(error-response 400 %))))

(defn- get-history [server* _ _]
  (js/Promise.resolve (json-response 200 (:history @(:state server*)))))

(def exact-routes
  {"GET /object_info" get-object-info
   "GET /queue" get-queue
   "GET /prompt" get-prompt-status
   "GET /history" get-history
   "POST /queue" post-queue
   "POST /prompt" post-prompt})

(defn- websocket-response [server* request url]
  (let [requested-id (.get (.-searchParams url) "clientId")
        client-id (if (seq requested-id) requested-id (str (random-uuid)))
        upgraded (js/Deno.upgradeWebSocket request)
        socket (.-socket upgraded)
        forget! (fn [_]
                  (swap! (:clients server*)
                         (fn [clients]
                           (if (identical? socket (get clients client-id))
                             (dissoc clients client-id)
                             clients))))]
    (set! (.-onopen socket)
          (fn [_]
            (swap! (:clients server*) assoc client-id socket)
            (send-message! socket "status"
                           {:status {:exec_info
                                     {:queue_remaining (queue-remaining server*)}}
                            :sid client-id})))
    (set! (.-onclose socket) forget!)
    (set! (.-onerror socket) forget!)
    (.-response upgraded)))

(defn handler [server*]
  (fn [request]
    (let [url (js/URL. (.-url request))
          path (.-pathname url)
          method (.-method request)
          route (get exact-routes (str method " " path))]
      (cond
        (and (= method "GET") (= path "/ws"))
        (websocket-response server* request url)
        route (route server* request url)
        (and (= method "GET") (= path "/view"))
        (js/Promise.resolve (view-response server* url))
        (and (= method "GET") (.startsWith path "/object_info/"))
        (let [type (js/decodeURIComponent (subs path (count "/object_info/")))
              info (object-info (get-in server* [:ctx :registry]))]
          (js/Promise.resolve
           (json-response 200 (if-let [definition (get info type)]
                                {type definition} {}))))
        (and (= method "GET") (.startsWith path "/history/"))
        (let [id (js/decodeURIComponent (subs path (count "/history/")))
              entry (get-in @(:state server*) [:history id])]
          (js/Promise.resolve (json-response 200 (if entry {id entry} {}))))
        :else (js/Promise.resolve (json-response 404 {:error "not found"}))))))

(defn serve!
  ([server*] (serve! server* {}))
  ([server* {:keys [hostname port] :or {hostname "127.0.0.1" port 8188}}]
   (js/Deno.serve #js {:hostname hostname :port port} (handler server*))))

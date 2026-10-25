(ns comfyui.native-client
  "The IO boundary to a real ComfyUI. Native protocol, three calls:

     POST /prompt          {prompt, client_id}     -> {prompt_id}
     GET  /history/{id}                            -> outputs once finished
     GET  /view?filename&subfolder&type            -> the bytes

  Everything that decides *what* to render is in comfy-graph (pure). This
  namespace only moves bytes, and its one job beyond that is to be honest about
  failure: every path that does not end with an image on disk returns
  `{:ok? false}` with a reason, so the caller reports a `:placeholder` leg
  rather than a served one."
  (:require ["fs" :as fs]
            ["path" :as path]
            [kotoba.lang.text :as str]
            [comfyui.native :as native]))

(defn- json-post [url body]
  (-> (js/fetch url
                #js {:method "POST"
                     :headers #js {"content-type" "application/json"}
                     :body (js/JSON.stringify (clj->js body))})
      (.then (fn [r]
               (if (.-ok r)
                 (.json r)
                 (.then (.text r) (fn [t] (throw (ex-info "comfy POST failed"
                                                          {:status (.-status r)
                                                           :body (subs (str t) 0 300)})))))))
      (.then #(js->clj % :keywordize-keys true))))

(defn- json-get [url]
  (-> (js/fetch url)
      (.then (fn [r]
               (if (.-ok r)
                 (.json r)
                 (throw (ex-info "comfy GET failed" {:status (.-status r) :url url})))))
      (.then #(js->clj % :keywordize-keys true))))

(defn- sleep [ms] (js/Promise. (fn [res] (js/setTimeout res ms))))

(defn- outputs-of
  "history body + prompt id -> the SaveImage outputs, or nil while still running.

  ComfyUI returns `{}` for an id it has not finished, so an empty body is
  'not yet', not 'produced nothing' — conflating the two is how a poller
  decides a running job failed."
  [body id]
  (some-> (get body (keyword id)) :outputs vals (->> (mapcat :images)) seq))

(defn render!
  "A render request -> a promise of {:ok? bool :file path :reason ...}.

  `base` is the ComfyUI root URL. `out-dir` is where the PNG lands. Polling is
  bounded: a job that has not finished within `:timeout-ms` is reported as a
  timeout rather than waited on forever, because the loop that called this has
  a slot it needs back."
  [{:keys [base out-dir req config timeout-ms poll-ms]
    :or {timeout-ms 180000 poll-ms 2000}}]
  (let [graph (native/graph req config)]
    (-> (json-post (str base "/prompt")
                   {:prompt graph :client_id "comfyui-native"})
        (.then
         (fn [{:keys [prompt_id error node_errors]}]
           (if-not prompt_id
             {:ok? false :reason :rejected :error (or error node_errors)}
             (letfn [(poll [waited]
                       (if (> waited timeout-ms)
                         (js/Promise.resolve {:ok? false :reason :timeout
                                              :prompt-id prompt_id})
                         (-> (json-get (str base "/history/" prompt_id))
                             (.then (fn [body]
                                      (if-let [imgs (outputs-of body prompt_id)]
                                        (let [{:keys [filename subfolder type]} (first imgs)
                                              url (str base "/view?filename=" (js/encodeURIComponent filename)
                                                       "&subfolder=" (js/encodeURIComponent (or subfolder ""))
                                                       "&type=" (or type "output"))]
                                          (-> (js/fetch url)
                                              (.then #(.arrayBuffer %))
                                              (.then (fn [buf]
                                                       (fs/mkdirSync out-dir #js {:recursive true})
                                                       (let [file (path/join out-dir filename)]
                                                         (fs/writeFileSync file (js/Buffer.from buf))
                                                         {:ok? true :file file
                                                          :bytes (.-byteLength buf)})))))
                                        (.then (sleep poll-ms)
                                               (fn [_] (poll (+ waited poll-ms))))))))))]
               (poll 0)))))
        (.catch (fn [e] {:ok? false :reason :error :error (ex-message e)})))))

(defn reachable?
  "Does a ComfyUI actually answer at `base`?

  This exists because the first version of the producer treated 'the env var is
  set' as 'the backend is reachable' and would have reported a served leg for a
  URL nothing was listening on."
  [base]
  (-> (js/fetch (str base "/system_stats"))
      (.then #(.-ok %))
      (.catch (fn [_] false))))

(defn base-url
  "Env -> the ComfyUI root, or nil.

  `aget` rather than `js->clj`: under nbb the latter yields a Function and every
  lookup comes back nil, so a producer reading it reported every leg degraded no
  matter how the node was configured."
  []
  (let [v (or (aget js/process.env "COMFY_URL")
              (aget js/process.env "MURAKUMO_BACKEND_URL"))]
    (when-not (str/blank? (str v)) (str/replace (str v) #"/+$" ""))))

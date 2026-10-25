(ns browseruse.actions
  "Portable browser-use action registry with structured execution results."
  (:require [browseruse.browser :as b]))

(defn action-result
  ([action message] (action-result action message nil nil))
  ([action message data state]
   (cond-> {:ok? true :action action :message message}
     (some? data) (assoc :data data)
     (some? state) (assoc :state state))))

(defn action-error [action type message data]
  {:ok? false :action action
   :error (cond-> {:type type :message message}
            (seq data) (assoc :data data))})

(defn result->text [{:keys [ok? message data state error]}]
  (if ok?
    (str message
         (when data (str "\nResult: " (pr-str data)))
         (when state (str "\n" (b/state->prompt state))))
    (str "Action failed [" (name (:type error)) "]: " (:message error)
         (when-let [d (:data error)] (str "\n" (pr-str d))))))

(defn execute-action
  "Executes an action and always returns an ActionResult map."
  [action input]
  (try
    ((or (:execute action)
         (fn [x] (action-result (:name action) "Completed" ((:fn action) x) nil))) input)
    (catch #?(:clj Exception :cljs :default) e
      (action-error (:name action) :execution
                    #?(:clj (.getMessage e) :cljs (.-message e))
                    (or (ex-data e) {})))))

(defn- tool [name description schema execute]
  (let [a {:name name :description description :schema schema :execute execute}]
    (assoc a :fn (fn [input] (result->text (execute-action a input))))))

(defn- object-schema [properties required]
  (cond-> {:type "object" :properties properties}
    (seq required) (assoc :required required)))

(defn- core-actions [browser]
  [(tool "navigate" "Navigate to a URL."
         (object-schema {:url {:type "string"}} ["url"])
         (fn [{:keys [url]}] (action-result "navigate" (str "Navigated to " url) nil (b/-navigate! browser url))))
   (tool "click_element" "Click an indexed element."
         (object-schema {:index {:type "integer"}} ["index"])
         (fn [{:keys [index]}] (action-result "click_element" (str "Clicked [" index "]") nil (b/-click! browser index))))
   (tool "input_text" "Type text into an indexed element."
         (object-schema {:index {:type "integer"} :text {:type "string"}} ["index" "text"])
         (fn [{:keys [index text]}] (action-result "input_text" (str "Typed into [" index "]") nil (b/-input-text! browser index text))))
   (tool "scroll" "Scroll up or down."
         (object-schema {:direction {:type "string" :enum ["up" "down"]}} ["direction"])
         (fn [{:keys [direction]}] (action-result "scroll" (str "Scrolled " direction) nil (b/-scroll! browser (keyword direction)))))
   (tool "go_back" "Go back."
         (object-schema {} [])
         (fn [_] (action-result "go_back" "Went back" nil (b/-back! browser))))])

(defn- tab-actions [browser]
  (when (b/supports? browser :tabs)
    [(tool "open_tab" "Open a URL in a new tab." (object-schema {:url {:type "string"}} ["url"])
           (fn [{:keys [url]}] (action-result "open_tab" "Opened tab" nil (b/-new-tab! browser url))))
     (tool "switch_tab" "Switch to a tab ID." (object-schema {:tab_id {:type "string"}} ["tab_id"])
           (fn [{:keys [tab_id]}] (action-result "switch_tab" "Switched tab" nil (b/-switch-tab! browser tab_id))))
     (tool "close_tab" "Close a tab ID." (object-schema {:tab_id {:type "string"}} ["tab_id"])
           (fn [{:keys [tab_id]}] (action-result "close_tab" "Closed tab" nil (b/-close-tab! browser tab_id))))]))

(defn- interaction-actions [browser]
  (when (b/supports? browser :interaction)
    [(tool "wait" "Wait for milliseconds or a host condition." (object-schema {:ms {:type "integer"} :condition {:type "string"}} [])
           (fn [x] (action-result "wait" "Wait complete" (b/-wait! browser x) (b/-state browser))))
     (tool "evaluate" "Evaluate host JavaScript and return serializable data." (object-schema {:expression {:type "string"} :args {}} ["expression"])
           (fn [{:keys [expression args]}] (action-result "evaluate" "Evaluation complete" (b/-evaluate! browser expression args) (b/-state browser))))
     (tool "screenshot" "Capture a screenshot reference." (object-schema {:full_page {:type "boolean"} :format {:type "string"}} [])
           (fn [{:keys [full_page format]}] (action-result "screenshot" "Screenshot captured" (b/-screenshot! browser {:full-page? full_page :format (some-> format keyword)}) (b/-state browser))))
     (tool "upload_files" "Upload files to an indexed input." (object-schema {:index {:type "integer"} :files {:type "array" :items {:type "string"}}} ["index" "files"])
           (fn [{:keys [index files]}] (action-result "upload_files" "Files uploaded" (b/-upload-files! browser index files) (b/-state browser))))
     (tool "downloads" "List download metadata." (object-schema {} [])
           (fn [_] (action-result "downloads" "Downloads listed" (b/-downloads browser) (b/-state browser))))
     (tool "select_option" "Select values in an indexed select." (object-schema {:index {:type "integer"} :values {:type "array" :items {:type "string"}}} ["index" "values"])
           (fn [{:keys [index values]}] (action-result "select_option" "Option selected" (b/-select-option! browser index values) (b/-state browser))))
     (tool "set_checked" "Set an indexed checkbox or radio." (object-schema {:index {:type "integer"} :checked {:type "boolean"}} ["index" "checked"])
           (fn [{:keys [index checked]}] (action-result "set_checked" "Checked state set" (b/-set-checked! browser index checked) (b/-state browser))))
     (tool "press_keys" "Press a key chord or sequence." (object-schema {:keys {:type "array" :items {:type "string"}}} ["keys"])
           (fn [{:keys [keys]}] (action-result "press_keys" "Keys pressed" (b/-press-keys! browser keys) (b/-state browser))))
     (tool "extract" "Extract structured page data." (object-schema {:query {}} ["query"])
           (fn [{:keys [query]}] (action-result "extract" "Data extracted" (b/-extract browser query) (b/-state browser))))]))

(defn- storage-actions [browser]
  (when (b/supports? browser :storage)
    [(tool "cookies" "Read cookies." (object-schema {:urls {:type "array" :items {:type "string"}}} [])
           (fn [{:keys [urls]}] (action-result "cookies" "Cookies read" (b/-cookies browser urls) (b/-state browser))))
     (tool "set_cookies" "Replace cookies." (object-schema {:cookies {:type "array"}} ["cookies"])
           (fn [{:keys [cookies]}] (action-result "set_cookies" "Cookies set" (b/-set-cookies! browser cookies) (b/-state browser))))
     (tool "clear_cookies" "Clear cookies." (object-schema {} [])
           (fn [_] (action-result "clear_cookies" "Cookies cleared" (b/-clear-cookies! browser) (b/-state browser))))
     (tool "storage_state" "Read cookie and web-storage state." (object-schema {} [])
           (fn [_] (action-result "storage_state" "Storage read" (b/-storage-state browser) (b/-state browser))))
     (tool "set_storage" "Replace cookie and web-storage state." (object-schema {:storage {}} ["storage"])
           (fn [{:keys [storage]}] (action-result "set_storage" "Storage set" (b/-set-storage! browser storage) (b/-state browser))))]))

(defn default-actions
  "Returns the capability-filtered standard registry. :fn stays text-compatible;
  use execute-action for lossless structured results."
  [browser]
  (vec (concat (core-actions browser) (tab-actions browser)
               (interaction-actions browser) (storage-actions browser))))

(def done-action
  {:name "done" :description "Finish the task with a final result."
   :schema {:type "object" :properties {:text {:type "string"} :success {:type "boolean"}}
            :required ["text"]}
   :fn (fn [{:keys [text]}] text)})

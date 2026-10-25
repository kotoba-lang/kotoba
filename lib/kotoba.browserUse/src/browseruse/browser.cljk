(ns browseruse.browser
  "Portable browser capability contracts and deterministic mock host."
  (:require [kotoba.lang.text :as str]))

;; Kept deliberately stable: existing browser hosts only need this protocol.
(defprotocol IBrowser
  (-navigate! [b url])
  (-click! [b index])
  (-input-text! [b index text])
  (-scroll! [b direction])
  (-back! [b])
  (-state [b]))

(defprotocol ITabBrowser
  (-tabs [b])
  (-new-tab! [b url])
  (-switch-tab! [b tab-id])
  (-close-tab! [b tab-id]))

(defprotocol IInteractionBrowser
  (-wait! [b wait-spec])
  (-evaluate! [b expression args])
  (-screenshot! [b options])
  (-upload-files! [b index files])
  (-downloads [b])
  (-select-option! [b index values])
  (-set-checked! [b index checked?])
  (-press-keys! [b keys])
  (-extract [b query]))

(defprotocol IStorageBrowser
  (-cookies [b urls])
  (-set-cookies! [b cookies])
  (-clear-cookies! [b])
  (-storage-state [b])
  (-set-storage! [b storage]))

(defn supports?
  "True when browser implements a portable optional capability."
  [browser capability]
  (case capability
    :tabs (satisfies? ITabBrowser browser)
    :interaction (satisfies? IInteractionBrowser browser)
    :storage (satisfies? IStorageBrowser browser)
    false))

(defn state->prompt
  [{:keys [url title elements dom screenshot tabs active-tab-id]}]
  (str "Current page: " title " (" url ")\n"
       (when (seq tabs) (str "Tabs: " (count tabs) ", active: " active-tab-id "\n"))
       (when dom (str "DOM: " (or (:summary dom) (:text dom) dom) "\n"))
       (when screenshot (str "Screenshot: " (or (:ref screenshot) screenshot) "\n"))
       "Interactive elements:\n"
       (str/join "\n"
                 (for [{:keys [index tag text attrs]} elements]
                   (str "[" index "]<" tag
                        (apply str (for [[k v] (sort-by key attrs)]
                                     (str " " (name k) "=\"" v "\"")))
                        ">" (or text "") "</" tag ">")))))

(defn- page [site url] (get site url {:title "404 Not Found" :elements []}))

(defn- indexed-elements [site {:keys [url inputs selected checked uploads]}]
  (vec
   (map-indexed
    (fn [i el]
      {:index i :tag (:tag el) :text (:text el)
       :attrs (cond-> (or (:attrs el) {})
                (contains? inputs [url i]) (assoc :value (get inputs [url i]))
                (contains? selected [url i]) (assoc :selected (get selected [url i]))
                (contains? checked [url i]) (assoc :checked (get checked [url i]))
                (contains? uploads [url i]) (assoc :files (get uploads [url i])))})
    (:elements (page site url)))))

(defn- public-state [site {:keys [url active-tab-id tabs screenshot] :as st}]
  (let [p (page site url)]
    {:url url :title (:title p)
     :elements (indexed-elements site st)
     :tabs (mapv #(select-keys % [:id :url :title]) tabs)
     :active-tab-id active-tab-id
     :dom {:kind :indexed-elements :element-count (count (:elements p))
           :summary (or (:dom-summary p) (:title p))}
     :screenshot screenshot}))

(defn- require-element [site {:keys [url]} index]
  (or (get-in site [url :elements index])
      (throw (ex-info "No element at index" {:type :invalid-index :index index :url url}))))

(defn mock-browser
  "Pure-data browser implementing the complete portable contract.

  Site pages may additionally provide :extract data and element :download metadata.
  Screenshot refs and time are deterministic counters; no files or clocks are used."
  [site start-url]
  (let [initial-tab {:id "tab-1" :url start-url :title (:title (page site start-url))}
        s (atom {:url start-url :inputs {} :selected {} :checked {} :uploads {}
                 :history [] :tabs [initial-tab] :active-tab-id "tab-1"
                 :next-tab 2 :next-shot 1 :elapsed-ms 0 :downloads []
                 :cookies [] :storage {:origins []}})
        sync-tab (fn [st]
                   (update st :tabs
                           (fn [tabs] (mapv #(if (= (:id %) (:active-tab-id st))
                                              (assoc % :url (:url st)
                                                       :title (:title (page site (:url st)))) %)
                                            tabs))))]
    (reify
      IBrowser
      (-navigate! [_ url]
        (swap! s (fn [st] (sync-tab (-> st (update :history conj (:url st)) (assoc :url url)))))
        (public-state site @s))
      (-click! [this index]
        (let [st @s
              el (require-element site st index)]
          (when-let [download (:download el)]
            (swap! s update :downloads conj download))
          (when-let [target (or (:nav el) (when-let [f (:nav-fn el)] (f st)))]
            (-navigate! this target))
          (public-state site @s)))
      (-input-text! [_ index text]
        (require-element site @s index)
        (swap! s assoc-in [:inputs [(:url @s) index]] text)
        (public-state site @s))
      (-scroll! [_ direction]
        (swap! s assoc :last-scroll direction)
        (public-state site @s))
      (-back! [_]
        (swap! s (fn [{:keys [history] :as st}]
                   (sync-tab (if (seq history)
                               (assoc st :url (peek history) :history (pop history)) st))))
        (public-state site @s))
      (-state [_] (public-state site @s))

      ITabBrowser
      (-tabs [_] (:tabs (public-state site @s)))
      (-new-tab! [_ url]
        (let [id (str "tab-" (:next-tab @s))]
          (swap! s (fn [st] (-> st sync-tab
                                (update :tabs conj {:id id :url url :title (:title (page site url))})
                                (assoc :active-tab-id id :url url)
                                (update :next-tab inc))))
          (public-state site @s)))
      (-switch-tab! [_ tab-id]
        (let [tab (some #(when (= tab-id (:id %)) %) (:tabs @s))]
          (when-not tab (throw (ex-info "No tab" {:type :invalid-tab :tab-id tab-id})))
          (swap! s #(-> % sync-tab (assoc :active-tab-id tab-id :url (:url tab))))
          (public-state site @s)))
      (-close-tab! [_ tab-id]
        (when (= 1 (count (:tabs @s)))
          (throw (ex-info "Cannot close the last tab" {:type :last-tab})))
        (swap! s (fn [st]
                   (let [tabs (filterv #(not= tab-id (:id %)) (:tabs st))
                         active (if (= tab-id (:active-tab-id st)) (first tabs)
                                    (some #(when (= (:active-tab-id st) (:id %)) %) tabs))]
                     (when (= tabs (:tabs st))
                       (throw (ex-info "No tab" {:type :invalid-tab :tab-id tab-id})))
                     (assoc st :tabs tabs :active-tab-id (:id active) :url (:url active)))))
        (public-state site @s))

      IInteractionBrowser
      (-wait! [_ wait-spec]
        (let [ms (long (or (:ms wait-spec) 0))]
          (when (neg? ms) (throw (ex-info "Wait must be non-negative" {:type :invalid-wait})))
          (swap! s update :elapsed-ms + ms)
          {:waited-ms ms :elapsed-ms (:elapsed-ms @s)}))
      (-evaluate! [_ expression args]
        {:expression expression :args args
         :value (get-in site [(:url @s) :evaluations expression])})
      (-screenshot! [_ options]
        (let [shot {:ref (str "mock://screenshot/" (:next-shot @s))
                    :format (or (:format options) :png)
                    :full-page? (boolean (:full-page? options))
                    :url (:url @s)}]
          (swap! s #(-> % (assoc :screenshot shot) (update :next-shot inc))) shot))
      (-upload-files! [_ index files]
        (require-element site @s index)
        (swap! s assoc-in [:uploads [(:url @s) index]] (vec files))
        {:index index :files (vec files)})
      (-downloads [_] (:downloads @s))
      (-select-option! [_ index values]
        (require-element site @s index)
        (let [values (if (sequential? values) (vec values) [values])]
          (swap! s assoc-in [:selected [(:url @s) index]] values)
          {:index index :values values}))
      (-set-checked! [_ index checked?]
        (require-element site @s index)
        (swap! s assoc-in [:checked [(:url @s) index]] (boolean checked?))
        {:index index :checked? (boolean checked?)})
      (-press-keys! [_ keys]
        (swap! s assoc :last-keys (vec keys))
        {:keys (vec keys)})
      (-extract [_ query]
        {:query query :data (get-in site [(:url @s) :extract query])})

      IStorageBrowser
      (-cookies [_ urls]
        (if (seq urls)
          (filterv #(some (fn [url] (str/includes? url (or (:domain %) ""))) urls) (:cookies @s))
          (:cookies @s)))
      (-set-cookies! [_ cookies] (swap! s assoc :cookies (vec cookies)) (:cookies @s))
      (-clear-cookies! [_] (swap! s assoc :cookies []) [])
      (-storage-state [_] (assoc (:storage @s) :cookies (:cookies @s)))
      (-set-storage! [_ storage]
        (swap! s assoc :storage (dissoc storage :cookies) :cookies (vec (:cookies storage)))
        (-storage-state _)))))

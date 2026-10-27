(ns browser.chrome
  "Browser chrome model: tabs, URL bar, and navigation intent.")

(defn empty-chrome
  []
  {:chrome/tabs []
   :chrome/active-tab-id nil
   :chrome/next-tab-id 1
   :chrome/url-input ""})

(defn new-tab
  [chrome url]
  (let [id (str "tab-" (:chrome/next-tab-id chrome))]
    (-> chrome
        (update :chrome/next-tab-id inc)
        (update :chrome/tabs conj {:tab/id id
                                   :tab/url url
                                   :tab/title nil
                                   :tab/history (cond-> [] url (conj url))
                                   :tab/status :idle})
        (assoc :chrome/active-tab-id id
               :chrome/url-input (or url "")))))

(defn active-tab
  [chrome]
  (first (filter #(= (:tab/id %) (:chrome/active-tab-id chrome))
                 (:chrome/tabs chrome))))

(defn focus-tab
  [chrome tab-id]
  (if-let [tab (first (filter #(= (:tab/id %) tab-id) (:chrome/tabs chrome)))]
    (assoc chrome :chrome/active-tab-id tab-id
                  :chrome/url-input (:tab/url tab))
    chrome))

(defn set-url-input
  [chrome value]
  (assoc chrome :chrome/url-input (str value)))

(defn commit-url
  [chrome]
  (let [url (:chrome/url-input chrome)
        tab-id (:chrome/active-tab-id chrome)]
    {:chrome (update chrome :chrome/tabs
                     (fn [tabs]
                       (mapv (fn [tab]
                               (if (= (:tab/id tab) tab-id)
                                 (-> tab
                                     (assoc :tab/url url :tab/status :loading)
                                     (update :tab/history conj url))
                                 tab))
                             tabs)))
     :navigation {:tab/id tab-id :url url}}))

(defn finish-navigation
  [chrome tab-id {:keys [title status]}]
  (update chrome :chrome/tabs
          (fn [tabs]
            (mapv (fn [tab]
                    (if (= (:tab/id tab) tab-id)
                      (assoc tab :tab/title title :tab/status (or status :idle))
                      tab))
                  tabs))))

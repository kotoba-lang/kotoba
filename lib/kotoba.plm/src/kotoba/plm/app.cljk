(ns kotoba.plm.app
  (:require [reagent.dom.client :as rdom]
            [re-frame.core :as rf]
            [kotoba.plm.core :as core]
            [kotoba.plm.ui :as ui]))

(def sample-files ["assembly.step","bom.csv","eco.edn"])

(defn hash-cid [s]
  (str "bafy" (subs (str (hash s)) 1)))

(defn install-css! []
  (let [node (.createElement js/document "style")]
    (set! (.-textContent node) (ui/css-text))
    (.appendChild (.-head js/document) node)))

(defn download! [filename text]
  (let [blob (js/Blob. #js [text] #js {:type "application/edn"})
        url (js/URL.createObjectURL blob)
        a (.createElement js/document "a")]
    (set! (.-href a) url)
    (set! (.-download a) filename)
    (.click a)
    (js/URL.revokeObjectURL url)))

(rf/reg-event-db
 :init
 (fn [_ _]
   {:stage 0
    :artifacts []
    :runner-results []
    :runner-plan nil}))

(rf/reg-event-db
 :advance
 (fn [db _]
   (update db :stage #(min (dec (count core/stages)) (inc %)))))

(rf/reg-event-db
 :audit
 (fn [db _]
   (update db :runner-results conj {:run/status :dry-run})))

(rf/reg-event-db
 :files
 (fn [db [_ files]]
   (update db :artifacts into
           (map (fn [file]
                  (let [name (.-name file)
                        artifact (core/classify-artifact name)]
                    (assoc artifact :artifact/cid (hash-cid (str name (:artifact/id artifact))))))
                files))))

(rf/reg-event-db
 :build-plan
 (fn [db _]
   (assoc db :runner-plan (core/runner-plan (:artifacts db)))))

(rf/reg-fx
 :download
 (fn [{:keys [filename body]}]
   (download! filename body)))

(rf/reg-event-fx
 :download-plan
 (fn [{:keys [db]} _]
   (let [plan (or (:runner-plan db) (core/runner-plan (:artifacts db)))]
     {:db (assoc db :runner-plan plan)
      :download {:filename "kotoba-plm-runner-plan.edn" :body (str (pr-str plan) "\n")}})))

(rf/reg-event-fx
 :download-state
 (fn [{:keys [db]} _]
   {:download {:filename "kotoba-plm-state.edn"
               :body (str (pr-str (select-keys db [:stage :artifacts :runner-results :runner-plan])) "\n")}}))

(rf/reg-sub :db identity)
(rf/reg-sub :review (fn [db _] (core/co-sientist-review db (:runner-results db))))
(rf/reg-sub :coverage (fn [db _] (core/coverage-assessment db (:runner-results db))))

(defn files-event [event]
  (let [target (.-target event)]
    (rf/dispatch [:files (vec (array-seq (.-files target)))])
    (set! (.-value target) "")))

(defn handlers []
  {:advance #(rf/dispatch [:advance])
   :audit #(rf/dispatch [:audit])
   :build-plan #(rf/dispatch [:build-plan])
   :download-plan #(rf/dispatch [:download-plan])
   :download-state #(rf/dispatch [:download-state])
   :files files-event})

(defn app-root []
  (let [db @(rf/subscribe [:db])
        review @(rf/subscribe [:review])
        coverage @(rf/subscribe [:coverage])]
    [ui/shell (assoc db :review review :coverage coverage :handlers (handlers))]))

(defonce root (atom nil))

(defn ^:dev/after-load render! []
  (when @root
    (rdom/render @root [app-root])))

(defn ^:export init []
  (install-css!)
  (rf/dispatch-sync [:init])
  (reset! root (rdom/create-root (.getElementById js/document "root")))
  (render!)
  (set! (.-__kotobaIndustrial js/window)
        #js {:dispatch rf/dispatch
             :state #(clj->js @(rf/subscribe [:db]))}))

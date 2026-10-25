(ns kotoba.issue.bcf
  "Portable buildingSMART BCF 3.0 topic/viewpoint contract and adapters for
  the generic kotoba.issue workflow. JVM XML/BCFZIP transport lives in
  `kotoba.issue.bcf.xml`."
  (:refer-clojure :exclude [comment])
  (:require [kotoba.lang.text :as string]
            [kotoba.issue.gate :as gate]))

(def contract-version 1)
(def topic-statuses #{"Open" "InProgress" "Resolved" "Closed"})
(def camera-types #{:perspective :orthogonal})

(defn- non-empty-string? [value] (and (string? value) (not (string/blank? value))))
(defn- vector3? [value] (and (vector? value) (= 3 (count value)) (every? number? value)))

(defn viewpoint
  [{:keys [guid camera selected-components visibility-exceptions
           default-visibility clipping-planes snapshot] :as value}]
  (when-not (and (non-empty-string? guid)
                 (contains? camera-types (:type camera))
                 (vector3? (:view-point camera))
                 (vector3? (:direction camera))
                 (vector3? (:up-vector camera))
                 (pos? (or (:aspect-ratio camera) 0)))
    (throw (ex-info "invalid BCF viewpoint" {:viewpoint value})))
  {:bcf.viewpoint/guid guid
   :bcf.viewpoint/camera camera
   :bcf.viewpoint/selected-components (vec selected-components)
   :bcf.viewpoint/default-visibility (boolean default-visibility)
   :bcf.viewpoint/visibility-exceptions (vec visibility-exceptions)
   :bcf.viewpoint/clipping-planes (vec clipping-planes)
   :bcf.viewpoint/snapshot snapshot})

(defn comment
  [{:keys [guid date author text viewpoint-guid] :as value}]
  (when-not (and (non-empty-string? guid) (non-empty-string? date)
                 (non-empty-string? author)
                 (or (non-empty-string? text) (non-empty-string? viewpoint-guid)))
    (throw (ex-info "invalid BCF comment" {:comment value})))
  {:bcf.comment/guid guid :bcf.comment/date date :bcf.comment/author author
   :bcf.comment/text text :bcf.comment/viewpoint-guid viewpoint-guid})

(defn topic
  [{:keys [guid type status title description creation-date creation-author
           priority labels assigned-to due-date stage viewpoints comments
           reference-links] :as value}]
  (when-not (and (non-empty-string? guid) (non-empty-string? type)
                 (non-empty-string? status) (non-empty-string? title)
                 (non-empty-string? creation-date) (non-empty-string? creation-author))
    (throw (ex-info "invalid BCF topic" {:topic value})))
  {:bcf/version "3.0" :bcf/contract-version contract-version
   :bcf.topic/guid (string/lower guid)
   :bcf.topic/type type :bcf.topic/status status :bcf.topic/title title
   :bcf.topic/description description :bcf.topic/creation-date creation-date
   :bcf.topic/creation-author creation-author :bcf.topic/priority priority
   :bcf.topic/labels (vec labels) :bcf.topic/assigned-to assigned-to
   :bcf.topic/due-date due-date :bcf.topic/stage stage
   :bcf.topic/reference-links (vec reference-links)
   :bcf.topic/viewpoints (mapv viewpoint viewpoints)
   :bcf.topic/comments (mapv comment comments)})

(defn topic->issue [bcf-topic]
  (assoc
   (gate/issue {:id (:bcf.topic/guid bcf-topic) :kind :bcf/topic
                :title (:bcf.topic/title bcf-topic) :source "BCF 3.0"
                :source-id (:bcf.topic/guid bcf-topic)
                :state (if (#{"Resolved" "Closed"} (:bcf.topic/status bcf-topic))
                         :closed :open)})
   :bcf/topic bcf-topic))

(defn update-from-issue [bcf-topic issue]
  (assoc bcf-topic
         :bcf.topic/title (:kotoba.issue/title issue)
         :bcf.topic/status (if (= :closed (:kotoba.issue/state issue)) "Closed" "Open")))

(defn ids-report->topics
  "Convert each object-level IDS failure to a BCF topic. The caller supplies
  UUID/date generation so browser, CI, and cloud runs remain deterministic."
  [ids-report {:keys [guid-fn viewpoint-guid-fn creation-date author camera]
               :or {camera {:type :perspective :view-point [10.0 10.0 10.0]
                            :direction [-1.0 -1.0 -1.0] :up-vector [0.0 0.0 1.0]
                            :field-of-view 60.0 :aspect-ratio 1.6}}}]
  (mapv
   (fn [index issue]
     (let [guid (guid-fn index issue)
           viewpoint-guid (viewpoint-guid-fn index issue)
           global-id (:ids.issue/global-id issue)
           failed-types (map (comp name :ids.requirement/type)
                             (:ids.issue/failed-requirements issue))]
       (topic
        {:guid guid :type "IDSFailure" :status "Open"
         :title (str (:ids.issue/specification issue) " — "
                     (or global-id (:ids.issue/reason issue)))
         :description (str "Failed IDS requirements: "
                           (string/join ", " failed-types))
         :creation-date creation-date :creation-author author
         :priority "Normal" :labels ["IDS" (:ids.issue/specification issue)]
         :viewpoints
         (when global-id
           [{:guid viewpoint-guid :camera camera
             :selected-components [{:ifc-guid global-id
                                    :authoring-tool-id global-id}]
             :default-visibility true}])})))
   (range) (:ids.report/issues ids-report)))

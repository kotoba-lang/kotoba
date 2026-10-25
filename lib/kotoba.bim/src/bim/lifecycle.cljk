(ns bim.lifecycle
  "Construction phases, design options, revisions, and drawing issue records."
  (:require [kotoba.lang.coll :as coll]))

(def schema-version 1)

(defn lifecycle [{:keys [phases option-sets]}]
  (let [phases (vec phases) phase-ids (mapv :phase/id phases)]
    (when-not (= (count phase-ids) (count (distinct phase-ids)))
      (throw (ex-info "phase ids must be unique" {:phase-ids phase-ids})))
    (doseq [option-set option-sets]
      (let [options (:option-set/options option-set)
            primaries (filter :option/primary? options)]
        (when-not (= 1 (count primaries))
          (throw (ex-info "design option set requires exactly one primary option"
                          {:option-set (:option-set/id option-set)})))))
    {:lifecycle/schema-version schema-version :lifecycle/phases phases
     :lifecycle/phase-index (zipmap phase-ids (range))
     :lifecycle/option-sets (into {} (map (juxt :option-set/id identity) option-sets))
     :lifecycle/revisions [] :lifecycle/issues []}))

(defn phase-status [state element view-phase-id]
  (let [index (:lifecycle/phase-index state) view (get index view-phase-id)
        created (get index (:phase/created element))
        demolished (get index (:phase/demolished element))]
    (when (nil? view)
      (throw (ex-info "view phase not found" {:phase-id view-phase-id})))
    (cond
      (and created (> created view)) :future
      (and demolished (<= demolished view)) :demolished
      (= created view) :new
      :else :existing)))

(defn phase-view
  "Filter and annotate elements according to a Revit-style phase filter."
  [state elements view-phase-id phase-filter]
  (->> elements
       (keep (fn [element]
               (let [status (phase-status state element view-phase-id)
                     display (get phase-filter status :show)]
                 (when-not (= :hide display)
                   (assoc element :phase/status status :phase/display display)))))
       vec))

(defn active-options
  "Return option ids visible for a selection map; unspecified sets use primary."
  [state selection]
  (into #{}
        (map (fn [[set-id option-set]]
               (or (get selection set-id)
                   (:option/id (first (filter :option/primary?
                                             (:option-set/options option-set)))))))
        (:lifecycle/option-sets state)))

(defn option-view [state elements selection]
  (let [active (active-options state selection)]
    (vec (filter #(or (nil? (:design-option/id %))
                      (contains? active (:design-option/id %))) elements))))

(defn add-revision [state {:keys [id sequence description date issued?] :as revision}]
  (when (some #(= id (:revision/id %)) (:lifecycle/revisions state))
    (throw (ex-info "revision id already exists" {:revision-id id})))
  (when (some #(= sequence (:revision/sequence %)) (:lifecycle/revisions state))
    (throw (ex-info "revision sequence already exists" {:sequence sequence})))
  (update state :lifecycle/revisions conj
          (assoc revision :revision/id id :revision/sequence sequence
                 :revision/description description :revision/date date
                 :revision/issued? (boolean issued?))))

(defn issue-sheet
  "Record an immutable sheet issue against existing, issued revisions."
  [state {:keys [id sheet-id revision-ids recipients timestamp] :as issue}]
  (let [revision-by-id (into {} (map (juxt :revision/id identity)
                                     (:lifecycle/revisions state)))
        missing (coll/set-difference (set revision-ids) (set (keys revision-by-id)))
        unissued (filter #(not (:revision/issued? (revision-by-id %))) revision-ids)]
    (when (seq missing)
      (throw (ex-info "sheet issue references missing revisions" {:revision-ids missing})))
    (when (seq unissued)
      (throw (ex-info "sheet issue requires issued revisions" {:revision-ids (vec unissued)})))
    (when (some #(= id (:issue/id %)) (:lifecycle/issues state))
      (throw (ex-info "sheet issue id already exists" {:issue-id id})))
    (update state :lifecycle/issues conj
            (assoc issue :issue/id id :issue/sheet-id sheet-id
                   :issue/revision-ids (vec revision-ids)
                   :issue/recipients (vec recipients) :issue/timestamp timestamp
                   :issue/status :published))))

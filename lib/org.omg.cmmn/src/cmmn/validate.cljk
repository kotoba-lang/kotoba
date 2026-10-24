(ns cmmn.validate
  "Structural validation of a CMMN-as-EDN case model. Pure: returns a vector of
  problem maps {:cmmn/severity :error|:warn :cmmn/code … :cmmn/id … :cmmn/msg …}
  so a caller decides how to surface them. `valid?` is true iff there are no
  :error-level problems (warnings are advisory)."
  (:require [cmmn.model :as m]))

(defn- problem [severity code id msg]
  {:cmmn/severity severity :cmmn/code code :cmmn/id id :cmmn/msg msg})

(defn validate
  "Return a vector of structural problems with `case-map`."
  [case-map]
  (let [ids (m/item-ids case-map)
        ps  (transient [])]
    ;; every plan-item type must be known
    (doseq [it (m/all-items case-map)]
      (when-not (contains? m/plan-item-types (:cmmn/type it))
        (conj! ps (problem :error :item/unknown-type (:cmmn/id it)
                           (str "unknown plan-item type " (:cmmn/type it))))))
    ;; every criterion :cmmn/on must reference an existing item id
    (doseq [it (m/all-items case-map)]
      (doseq [c (concat (:cmmn/entry-criteria it) (:cmmn/exit-criteria it))]
        (when-not (contains? ids (:cmmn/on c))
          (conj! ps (problem :error :criterion/dangling-ref (:cmmn/id it)
                             (str "criterion on " (:cmmn/id it)
                                  " references unknown id " (:cmmn/on c)))))))
    ;; stage :cmmn/children must all exist
    (doseq [it (m/items-of-type case-map :stage)]
      (doseq [cid (:cmmn/children it)]
        (when-not (contains? ids cid)
          (conj! ps (problem :error :stage/missing-child (:cmmn/id it)
                             (str "stage " (:cmmn/id it) " child " cid " not found"))))))
    ;; warn on simple criterion cycles (self-ref and pairwise A↔B)
    (let [deps (into {}
                     (map (fn [it]
                            [(:cmmn/id it)
                             (set (map :cmmn/on
                                       (concat (:cmmn/entry-criteria it)
                                               (:cmmn/exit-criteria it))))])
                          (m/all-items case-map)))]
      (doseq [[id d] deps]
        (when (contains? d id)
          (conj! ps (problem :warn :criterion/self-cycle id
                             (str "item " id " has a criterion referencing itself")))))
      (doseq [[a adeps] deps
              b adeps
              :when (not= a b)
              :when (contains? (get deps b #{}) a)]
        (conj! ps (problem :warn :criterion/cycle a
                           (str "possible criterion cycle between " a " and " b)))))
    (persistent! ps)))

(defn errors
  "Return only :error-severity problems."
  [case-map]
  (filterv #(= :error (:cmmn/severity %)) (validate case-map)))

(defn valid?
  "True iff `case-map` has no :error-level structural problems."
  [case-map]
  (empty? (errors case-map)))

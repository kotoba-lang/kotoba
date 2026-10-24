(ns briefing.validate
  (:require [briefing.model :as model]
            [kotoba.lang.text :as str]))

(defn problem [severity code id msg]
  {:briefing/severity severity :briefing/code code :briefing/id id :briefing/msg msg})

(defn problems [b]
  (vec
   (concat
    (for [it (:briefing/items b)
          :when (not (contains? model/item-kinds (:briefing/kind it)))]
      (problem :error :item/unknown-kind (:briefing/id it) "unknown briefing item kind"))
    (for [it (:briefing/items b)
          :when (str/blank? (:briefing/text it))]
      (problem :warning :item/missing-text (:briefing/id it) "briefing item has no text")))))

(defn valid? [b]
  (not-any? #(= :error (:briefing/severity %)) (problems b)))

(ns mokuroku.inspector
  "The right-hand pane: what is true about what is selected.

  Three modes, because the useful answer differs. One item shows its
  attributes. Many items show only what they agree on, plus aggregates —
  showing the first item's values for a multi-selection is the classic
  inspector bug, where the user edits what they think is 40 files and changes
  one. Nothing selected shows the source itself."
  (:require [mokuroku.item :as item]
            [mokuroku.source :as source]))

(defn- field [k label value]
  {:field/key k :field/label label :field/value value})

(defn- labels-for [descriptor]
  (into {} (map (juxt :attribute/key :attribute/label))
        (:source/attributes descriptor)))

(defn- single [descriptor it]
  (let [labels (labels-for descriptor)]
    {:inspector/mode :single
     :inspector/title (:item/label it)
     :inspector/subtitle (name (:item/kind it))
     :inspector/fields
     (into [(field :kind "Kind" (:item/kind it))]
           (for [k (source/attribute-keys descriptor)
                 :let [v (item/attr it k)]
                 :when (some? v)]
             (field k (get labels k (str k)) v)))}))

(defn- numeric-attribute-keys [descriptor]
  (->> (:source/attributes descriptor)
       (filter #(= :number (:attribute/type %)))
       (mapv :attribute/key)))

(defn- multi [descriptor items]
  (let [labels (labels-for descriptor)
        shared (for [k (source/attribute-keys descriptor)
                     :let [vs (set (map #(item/attr % k) items))]
                     :when (= 1 (count vs))
                     :let [v (first vs)]
                     :when (some? v)]
                 (field k (get labels k (str k)) v))
        sums (for [k (numeric-attribute-keys descriptor)
                   :let [vs (keep #(item/attr % k) items)]
                   :when (seq vs)]
               (field [:sum k] (str "Total " (get labels k (str k)))
                      (reduce + vs)))]
    {:inspector/mode :multi
     :inspector/title (str (count items) " items")
     :inspector/subtitle (->> items
                              (map :item/kind)
                              distinct
                              sort
                              (map name)
                              (interpose ", ")
                              (apply str))
     :inspector/fields
     (into [(field :count "Selected" (count items))]
           (concat sums shared))}))

(defn- empty-mode [descriptor result]
  {:inspector/mode :empty
   :inspector/title (:source/label descriptor)
   :inspector/subtitle (when-let [c (:source/capability descriptor)]
                         (str "capability " c))
   :inspector/fields
   [(field :total "Items" (:result/total result))
    (field :matched "Matching" (:result/matched result))]})

(defn inspect
  "Project DESCRIPTOR, the current RESULT and the selected ITEMS to a pane."
  [descriptor result items]
  (case (count items)
    0 (empty-mode descriptor result)
    1 (single descriptor (first items))
    (multi descriptor items)))

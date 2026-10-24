(ns engineer.selection
  "Pick / box-select / chain-select selection sets. Restored from
  kami-eng-core's `selection` module (deleted PR #82). Pure data — a
  selection-set is `{:items [...] :mode :single|:multi|:chain|:box}`.")

(def kinds #{:vertex :edge :face :solid :component :wire :net :pin})
(def modes #{:single :multi :chain :box})

(defn selection-set
  "A fresh selection set, mode `:single`."
  []
  {:items [] :mode :single})

(defn set-mode [sel mode] (assoc sel :mode mode))

(defn select
  "Select `{:id :kind}` per the current mode: `:single` replaces the whole
  set; `:multi`/`:chain`/`:box` append if not already present."
  [sel item]
  (case (:mode sel)
    :single (assoc sel :items [item])
    (:multi :chain :box)
    (if (some #(= % item) (:items sel))
      sel
      (update sel :items conj item))))

(defn deselect [sel id]
  (update sel :items (fn [items] (vec (remove #(= (:id %) id) items)))))

(defn clear [sel] (assoc sel :items []))
(defn items [sel] (:items sel))
(defn selected? [sel id] (boolean (some #(= (:id %) id) (:items sel))))
(defn count-selected [sel] (count (:items sel)))

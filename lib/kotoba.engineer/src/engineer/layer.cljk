(ns engineer.layer
  "Layer manager (visibility/lock/color/line-width). Restored from
  kami-eng-core's `layer` module (deleted PR #82). A manager starts with a
  single `\"Default\"` layer at id 0, matching the original Rust default.")

(defn manager
  "A fresh layer manager with the default layer (id 0) already present."
  []
  {:layers [{:id 0 :name "Default" :visible true :locked false
             :color [0.2 0.2 0.2 1.0] :line-width 1.0}]
   :active 0
   :next-id 1})

(defn create
  "Create a new layer `name` with `color` `[r g b a]`. Returns the updated manager."
  [mgr name color]
  (let [id (:next-id mgr)]
    (-> mgr
        (update :layers conj {:id id :name name :visible true :locked false
                               :color color :line-width 1.0})
        (update :next-id inc))))

(defn set-active
  "Set the active layer to `id`. Returns `[:ok mgr]` or `[:error msg mgr]`
  (mgr unchanged) if `id` doesn't exist."
  [mgr id]
  (if (some #(= (:id %) id) (:layers mgr))
    [:ok (assoc mgr :active id)]
    [:error (str "layer " id " not found") mgr]))

(defn set-visibility [mgr id visible]
  (update mgr :layers (fn [ls] (mapv #(if (= (:id %) id) (assoc % :visible visible) %) ls))))

(defn active [mgr] (:active mgr))
(defn all [mgr] (:layers mgr))
(defn visible-layers [mgr] (vec (filter :visible (:layers mgr))))

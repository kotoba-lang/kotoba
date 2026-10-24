(ns mokuroku.item
  "目録 — the unit a catalog lists.

  An item is deliberately flat: an id, a kind, a label, and a map of scalar
  attributes. Nesting is not allowed, for two reasons that happen to agree.
  The bounded `.kotoba` profile cannot express a recursive value yet
  (ADR-2607279200 W4, `docs/architecture.md` 'not a recursive value'), and
  sort/filter/search all want scalars anyway — a nested value would have to be
  projected to one before any of them could see it.

  A source with tree shape (a filesystem) carries `:item/parent` and the tree
  is reconstructed by whoever actually needs the tree. This is a *current
  limitation being worked around*, not the intended shape: when recursive
  logical values land, `:item/parent` becomes an implementation detail rather
  than the model.")

(def kinds
  "Item kinds the suite ships with. A source may declare its own; this set
  exists so a misspelling in a fixture is caught, not to close the world."
  #{:file :directory :symlink :volume
    :process :log-entry
    :image :track :note :document :page :font-face})

(def scalar-attribute?
  "An attribute value must be readable by a sort comparator and a search
  matcher without further projection."
  (some-fn nil? string? number? boolean? keyword?))

(defn item
  "Build an item. ATTRS is a flat map of attribute-key -> scalar."
  ([id kind label] (item id kind label {}))
  ([id kind label attrs]
   {:item/id id
    :item/kind kind
    :item/label label
    :item/attrs (or attrs {})}))

(defn attr
  ([it k] (attr it k nil))
  ([it k not-found] (get (:item/attrs it) k not-found)))

(defn with-attr [it k v]
  (assoc-in it [:item/attrs k] v))

(defn id-key
  "A total, deterministic ordering key for an item id.

  Sorting on an attribute alone is not a total order — ties would resolve
  however the underlying collection happened to be laid out, so the same query
  over the same items could produce two different orders. Every comparator in
  `mokuroku.query` breaks ties on this."
  [it]
  (let [id (:item/id it)]
    (cond
      (string? id) id
      (keyword? id) (str (symbol id))
      :else (pr-str id))))

(defn searchable-text
  "Free-text search surface: the label plus every string/keyword attribute.

  Numbers are excluded on purpose. Typing `1` should not match every item
  whose size happens to contain a 1; numeric matching belongs in a filter,
  where the operator is explicit."
  [it]
  (->> (vals (:item/attrs it))
       (filter (some-fn string? keyword?))
       (map #(if (keyword? %) (name %) %))
       (cons (:item/label it))
       (remove nil?)
       (map #(str %))))

(defn problem [code id msg]
  {:item/problem code :item/id id :item/msg msg})

(defn problems
  "Return [] when ITEM is well formed."
  [it]
  (vec
   (concat
    (when (nil? (:item/id it))
      [(problem :item/missing-id nil "item has no :item/id")])
    (when-not (keyword? (:item/kind it))
      [(problem :item/kind-not-keyword (:item/id it) "item kind must be a keyword")])
    (when-not (string? (:item/label it))
      [(problem :item/label-not-string (:item/id it) "item label must be a string")])
    ;; Absent attrs is legitimate — a source may yield items that are nothing
    ;; but a label — so only a present-and-wrong value is a problem.
    (when (and (some? (:item/attrs it)) (not (map? (:item/attrs it))))
      [(problem :item/attrs-not-map (:item/id it) "item attrs must be a map")])
    (when (map? (:item/attrs it))
      (for [[k v] (:item/attrs it)
            :when (not (scalar-attribute? v))]
        (problem :item/attr-not-scalar (:item/id it)
                 (str "attribute " k " is not a scalar")))))))

(defn valid? [it]
  (empty? (problems it)))

(defn problems-in
  "Validate a whole item vector, including cross-item identity."
  [items]
  (let [ids (map :item/id items)
        dupes (->> (frequencies ids)
                   (filter (fn [[_ n]] (> n 1)))
                   (map key))]
    (vec
     (concat
      (mapcat problems items)
      (for [id dupes]
        (problem :items/duplicate-id id "two items share one id"))))))

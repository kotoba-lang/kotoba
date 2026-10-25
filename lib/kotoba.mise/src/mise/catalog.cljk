(ns mise.catalog
  "Product / SKU / Catalog model (pure EDN) + query functions.

  A Catalog is a map {:products [...] :categories {...}}. A Product is
  {:id :brand :name :category :description :images :variants [SKU...]}. A SKU
  (variant) is {:id :product-id :name :options {...} :price Price}. Prices are
  delegated to mise.pricing (a Price is {:amount <number> :currency \"JPY\"}).

  Portable .cljc, zero host effects. The catalog is plain data the host loads
  (from a fixture, D1, an API, …); this namespace only shapes and queries it."
  (:refer-clojure :exclude [filter])
  (:require [kotoba.lang.text :as str]))

(defrecord Product [id brand name category description images variants])
(defrecord SKU [id product-id name options price])
(defrecord Catalog [products categories])

(defn product?
  "Loose duck-typed predicate so plain maps from EDN/JSON count as products."
  [x] (and (map? x) (:id x) (:name x)))

(defn sku? [x] (and (map? x) (:id x) (:price x)))

(defn catalog
  "Build a Catalog from a seq of products (and optional category tree)."
  ([products]
   (catalog products nil))
  ([products categories]
   (->Catalog (vec products) (or categories {}))))

(defn product-by-id
  "Find a product by :id in a catalog (or seq of products)."
  [src id]
  (let [products (if (map? src) (:products src) src)]
    (some #(when (= (:id %) id) %) products)))

(defn products-by-category
  "Products whose :category equals (or descends from) the given category id."
  [src cat-id]
  (let [products (if (map? src) (:products src) src)]
    (filterv #(= (:category %) cat-id) products)))

(defn search
  "Naive case-insensitive substring search over product :name/:description."
  [src q]
  (let [products (if (map? src) (:products src) src)
        ql (some-> q str str/lower)]
    (if (str/blank? ql)
      (vec products)
      (filterv (fn [p]
                 (let [n (some-> (:name p) str str/lower)
                       d (some-> (:description p) str str/lower)]
                   (or (and n (str/includes? n ql))
                       (and d (str/includes? d ql)))))
               products))))

(defn sku-by-id
  "Find a SKU by id within a product (or catalog+product-id)."
  ([product sku-id]
   (some #(when (= (:id %) sku-id) %) (:variants product)))
  ([src product-id sku-id]
   (when-let [p (product-by-id src product-id)]
     (sku-by-id p sku-id))))

(defn default-sku
  "The first variant of a product (or the product itself if no variants)."
  [product]
  (or (first (:variants product))
      (when (:price product) product)))

;; ---------------------------------------------------------------------------
;; category tree (parent/child hierarchy)
;; ---------------------------------------------------------------------------

(defn category-tree
  "Build a {parent → #{children}} map from a Catalog's :categories (which may
  be a flat map of {id → label} or already a tree). v1: categories are flat;
  this returns an empty tree (host app supplies the hierarchy). When the catalog
  :categories map has entries shaped {id → {:label :parent}}, builds the tree."
  [catalog']
  (let [cats (:categories catalog' {})]
    (reduce (fn [tree [id spec]]
              (if (map? spec)
                (let [parent (:parent spec)]
                  (if parent
                    (update tree parent (fnil conj #{}) id)
                    tree))
                tree))
            {} cats)))

(defn child-categories
  "Direct children of a category id, given a category-tree."
  [tree cat-id]
  (get tree cat-id #{}))

(defn descendant-categories
  "All descendants of a category id (recursive). Returns a set."
  [tree cat-id]
  (loop [queue [cat-id] found #{}]
    (if-let [c (first queue)]
      (let [children (child-categories tree c)
            new-children (remove found children)
            found' (into found children)]
        (recur (concat (rest queue) new-children) found'))
      found)))

(defn products-in-category
  "Products in a category AND all its descendants (given a category-tree).
  For a flat catalog (no tree), falls back to direct :category match."
  ([src cat-id]
   (products-in-category src cat-id {}))
  ([src cat-id tree]
   (let [descendants (descendant-categories tree cat-id)
         all-cats (conj descendants cat-id)
         products (if (map? src) (:products src) src)]
     (filterv #(contains? all-cats (:category %)) products))))

;; ---------------------------------------------------------------------------
;; variant matrix (size × color grid generation)
;; ---------------------------------------------------------------------------

(defn variant-matrix
  "Generate a Cartesian-product variant grid from sizes and colors. Returns a
  vec of SKU maps {:id :name :options {:size :color}}. id = product-id + size +
  color slug. Caller attaches :price per-variant after generation."
  [product-id sizes colors]
  (if (or (empty? sizes) (empty? colors))
    ;; single dimension if one is empty -- use whichever of sizes/colors is
    ;; actually populated, not sizes unconditionally, else a colors-only
    ;; product (empty sizes) silently generates zero variants.
    (let [[dim opt-key] (if (seq sizes) [sizes :size] [colors :color])]
      (vec
       (for [v (sort-by identity dim)]
         {:id (str product-id "-" (name v))
          :product-id product-id
          :name (name v)
          :options {opt-key v}})))
    (vec
     (for [s (sort-by identity sizes)
           c (sort-by identity colors)]
       (let [id (str product-id "-" (name s) "-" (name c))]
         {:id id
          :product-id product-id
          :name (str (name s) " / " (name c))
          :options {:size s :color c}})))))

(defn attach-prices
  "Given variants (from variant-matrix) and a price map {option-key → Price},
  attach :price to each variant whose options match. Variants without a match
  get the :default price (or nil if no default)."
  [variants price-map]
  (mapv (fn [v]
          (let [opts (:options v)
                price (or (some (fn [[k val]] (get-in price-map [k val])) opts)
                          (:default price-map))]
            (assoc v :price price)))
        variants))

(defn variant-by-option
  "Find a variant by a partial option match, e.g. {:size :m}. Returns the first
  matching variant or nil."
  [product option-match]
  (some #(when (every? (fn [[k v]] (= (get-in % [:options k]) v)) option-match) %)
        (:variants product [])))

(ns kotoba.plm.item
  "PLM core domain — pure constructors (tx maps) + queries over the item /
   BOM-edge / change-order graph. No ERP side effects live here; the ERP
   thread (kotoba.plm.thread) reads released PLM state and derives them."
  (:require [kotoba.plm.db :as db]))

(declare mbom-rows)

(defn- ->bigdec
  "Portable arbitrary-precision decimal: `bigdec` on the JVM, pass-through
   under cljs (no bignum type there; callers already deal in js numbers)."
  [x]
  #?(:clj (bigdec x) :cljs x))

;; ───────────────────────────── constructors (tx maps) ──────────────────────

(defn item-id [part-no rev] (str part-no "@" rev))

(defn item
  "Build an item-master tx map. Defaults lifecycle :draft, uom :ea.
   `:make-buy` is :make | :buy | :phantom; :buy items carry :std-unit-cost."
  [{:keys [part-no rev name uom make-buy category std-unit-cost package-ref]
    :or   {rev "A" uom :ea make-buy :make}}]
  (cond-> {:plm.item/id        (item-id part-no rev)
           :plm.item/part-no   part-no
           :plm.item/revision  rev
           :plm.item/name      (or name part-no)
           :plm.item/uom       uom
           :plm.item/make-buy  make-buy
           :plm.item/lifecycle :draft}
    category      (assoc :plm.item/category category)
    std-unit-cost (assoc :plm.item/std-unit-cost (->bigdec std-unit-cost))
    package-ref   (assoc :plm.item/package-ref package-ref)))

(defn bom-edge
  "Build a BOM-edge tx map linking parent→child (both given as \"<part>@<rev>\"
   item ids). `:view` is :ebom | :mbom; cost roll-up & consumption use :mbom.
   Optional effectivity: `:eff-from`/`:eff-to` (java.util.Date) bound the date
   window; `:eco` links the change order that introduced the edge."
  [{:keys [parent child qty uom find-no ref-designator view eff-from eff-to eco]
    :or   {qty 1 uom :ea find-no 0 view :mbom}}]
  (cond-> {:plm.bom/id     (str parent "|" find-no "|" child)
           :plm.bom/parent [:plm.item/id parent]
           :plm.bom/child  [:plm.item/id child]
           :plm.bom/qty    (->bigdec qty)
           :plm.bom/uom    uom
           :plm.bom/find-no (long find-no)
           :plm.bom/view   view}
    ref-designator (assoc :plm.bom/ref-designator ref-designator)
    eff-from       (assoc :plm.bom/eff-from eff-from)
    eff-to         (assoc :plm.bom/eff-to eff-to)
    eco            (assoc :plm.bom/eco [:plm.eco/id eco])))

(defn revise-item-tx
  "tx that creates a new revision of `old-id` (\"<part>@<rev>\") at `new-rev`:
   a :draft item that :supersedes the old one and copies its MBOM parent
   structure (so the new revision starts from the prior build and is edited).
   The supersede is finalised — old → :obsolete — when the new rev is released."
  [db old-id new-rev]
  (let [o      (db/pull db [:plm.item/part-no :plm.item/name :plm.item/uom
                            :plm.item/make-buy :plm.item/category :plm.item/std-unit-cost]
                        [:plm.item/id old-id])
        part   (:plm.item/part-no o)
        new-id (item-id part new-rev)
        tid    "newrev"]                                ; tempid so copied edges resolve in-tx
    (when (nil? part) (throw (ex-info "unknown item to revise" {:item old-id})))
    (into [(cond-> {:db/id              tid
                    :plm.item/id        new-id
                    :plm.item/part-no   part
                    :plm.item/revision  new-rev
                    :plm.item/name      (:plm.item/name o)
                    :plm.item/uom       (:plm.item/uom o)
                    :plm.item/make-buy  (:plm.item/make-buy o)
                    :plm.item/lifecycle :draft
                    :plm.item/supersedes [:plm.item/id old-id]}
             (:plm.item/category o)      (assoc :plm.item/category (:plm.item/category o))
             (:plm.item/std-unit-cost o) (assoc :plm.item/std-unit-cost (:plm.item/std-unit-cost o)))]
          (for [{:keys [child qty find-no]} (mbom-rows db old-id)]
            (assoc (bom-edge {:parent new-id :child child
                              :qty qty :find-no find-no :view :mbom})
                   :plm.bom/parent tid)))))             ; reference the new item by tempid

(defn change-order
  "Build an ECO tx map. `:affected` is a seq of affected item ids; on release the
   thread applies `:new-unit-cost` to those :buy items and revalues their parents."
  [{:keys [id kind affected disposition new-unit-cost]
    :or   {kind :eco disposition :use-as-is}}]
  (cond-> {:plm.eco/id          id
           :plm.eco/kind        kind
           :plm.eco/state       :draft
           :plm.eco/disposition disposition
           :plm.eco/affected    (mapv (fn [iid] [:plm.item/id iid]) affected)}
    new-unit-cost (assoc :plm.eco/new-unit-cost (->bigdec new-unit-cost))))

;; ───────────────────────────── queries ─────────────────────────────────────

(defn lifecycle [db iid] (db/attr db :plm.item/lifecycle [:plm.item/id iid]))
(defn make-buy  [db iid] (db/attr db :plm.item/make-buy  [:plm.item/id iid]))
(defn unit-cost [db iid] (db/attr db :plm.item/std-unit-cost [:plm.item/id iid]))
(defn released? [db iid] (= :released (lifecycle db iid)))

(def ^:private epoch    #inst "1970-01-01T00:00:00.000-00:00")
(def ^:private far-future #inst "9999-12-31T00:00:00.000-00:00")

(defn effective?
  "Is `[from to)` effective at `asof`? `asof` nil ⇒ effectivity ignored (all edges)."
  [from to asof]
  (or (nil? asof)
      (and (not (pos? (compare from asof)))   ; from <= asof
           (neg? (compare asof to)))))         ; asof <  to

(defn mbom-children
  "MBOM children of `iid` as [{:child <id> :qty <bigdec>} ...]. With `asof`
   (java.util.Date) only edges effective at that date are returned; arity-2
   ignores effectivity (the whole structure)."
  ([db iid] (mbom-children db iid nil))
  ([db iid asof]
   (->> (db/q '[:find ?cid ?qty ?from ?to
                :in $ ?pid ?epoch ?far
                :where
                [?p :plm.item/id ?pid]
                [?e :plm.bom/parent ?p]
                [?e :plm.bom/view :mbom]
                [?e :plm.bom/child ?c]
                [?c :plm.item/id ?cid]
                [?e :plm.bom/qty ?qty]
                [(get-else $ ?e :plm.bom/eff-from ?epoch) ?from]
                [(get-else $ ?e :plm.bom/eff-to ?far) ?to]]
              db iid epoch far-future)
        (filter (fn [[_ _ from to]] (effective? from to asof)))
        (map (fn [[cid qty _ _]] {:child cid :qty qty}))
        (sort-by :child)
        vec)))

(defn mbom-rows
  "MBOM child edges of `iid` with find-no carried (for revision copy / display)."
  [db iid]
  (->> (db/q '[:find ?cid ?qty ?fno
               :in $ ?pid
               :where
               [?p :plm.item/id ?pid]
               [?e :plm.bom/parent ?p]
               [?e :plm.bom/view :mbom]
               [?e :plm.bom/child ?c]
               [?c :plm.item/id ?cid]
               [?e :plm.bom/qty ?qty]
               [(get-else $ ?e :plm.bom/find-no 0) ?fno]]
             db iid)
       (map (fn [[cid qty fno]] {:child cid :qty qty :find-no fno}))
       (sort-by :find-no)
       vec))

(defn parents-using
  "Item ids of MBOM parents that directly consume `iid` (where-used, 1 level)."
  [db iid]
  (->> (db/q '[:find ?pid
               :in $ ?cid
               :where
               [?c :plm.item/id ?cid]
               [?e :plm.bom/child ?c]
               [?e :plm.bom/view :mbom]
               [?e :plm.bom/parent ?p]
               [?p :plm.item/id ?pid]]
             db iid)
       (map first)
       sort
       vec))

(defn ancestors-using
  "Item ids of every MBOM ancestor that transitively consumes `iid`
   (where-used, all levels — direct parents, grandparents, etc). Cycle-safe:
   a `seen` frontier stops re-walking an already-visited ancestor."
  [db iid]
  (loop [frontier (parents-using db iid)
         seen     #{}
         acc      []]
    (if (empty? frontier)
      (vec (sort (distinct acc)))
      (let [seen'      (into seen frontier)
            next-level (->> frontier
                            (mapcat #(parents-using db %))
                            distinct
                            (remove seen'))]
        (recur next-level seen' (into acc frontier))))))

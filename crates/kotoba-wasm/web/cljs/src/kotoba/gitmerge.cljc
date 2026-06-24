(ns kotoba.gitmerge
  "GitOffice Phase 3 (doc e §4) — 3-way merge over element-granular node sets.

   Pure (.cljc). Inputs are three node sets {stable-id -> attr-map} from Phase 0/1:
   base (= merge-base), ours (base branch tip), theirs (PR branch tip).

   Why this beats text 3-way merge for office docs (doc e §4):
   - ATTRIBUTE-LEVEL auto-merge: ours edits one attr, theirs edits another, on the
     SAME element -> both apply, no conflict (text merge would flag the whole line).
   - Fractional-index ordering: two concurrent inserts are two ADDs -> never a conflict
     (text merge collides on the same insertion point).
   - A real conflict is narrow: the SAME element's SAME attribute changed both sides
     to different values (or delete-vs-modify). Reported as :conflicts for a 3-pane UI."
  (:require [kotoba.gitoffice :as g]
            [kotoba.gitdiff :as d]
            [clojure.set :as set]))

;; ---------------------------------------------------------------------------
;; per-attribute 3-way
;; ---------------------------------------------------------------------------

(defn- merge3-attr
  "3-way merge of one attribute value. -> {:v val} or {:conflict {:base :ours :theirs}}."
  [ba oa ta]
  (cond
    (= oa ta) {:v oa}        ; same on both (incl. both removed the attr)
    (= oa ba) {:v ta}        ; ours unchanged -> take theirs
    (= ta ba) {:v oa}        ; theirs unchanged -> take ours
    :else     {:conflict {:base ba :ours oa :theirs ta}}))

(defn- strip-nils [m] (into {} (remove (comp nil? val) m)))

(defn- merge3-node
  "3-way merge two present nodes attr-by-attr (b may be nil = added both sides).
   -> {:node attrs} (clean) or {:conflict {attr {:base :ours :theirs}} :ours :theirs}."
  [b o t]
  (let [ks (set/union (set (keys b)) (set (keys o)) (set (keys t)))
        per (into {} (map (fn [k] [k (merge3-attr (get b k) (get o k) (get t k))]) ks))
        conflicts (into {} (keep (fn [[k r]] (when (:conflict r) [k (:conflict r)])) per))]
    (if (seq conflicts)
      {:conflict conflicts :ours o :theirs t}
      {:node (strip-nils (into {} (map (fn [[k r]] [k (:v r)]) per)))})))

;; ---------------------------------------------------------------------------
;; node-set 3-way
;; ---------------------------------------------------------------------------

(defn merge3
  "3-way merge of node sets. -> {:merged {id attrs} :conflicts {id info}}.
   Conflict info :kind ∈ #{:attr :delete-modify}. A result with empty :conflicts is
   clean and :merged is directly usable; otherwise resolve :conflicts then re-insert."
  [base ours theirs]
  (reduce
   (fn [acc id]
     (let [b (get base id) o (get ours id) t (get theirs id)]
       (cond
         (= o t) (cond-> acc (some? o) (assoc-in [:merged id] o))   ; agree (incl. both deleted)
         (= o b) (cond-> acc (some? t) (assoc-in [:merged id] t))   ; theirs side moved (incl. delete: t=nil)
         (= t b) (cond-> acc (some? o) (assoc-in [:merged id] o))   ; ours side moved
         (nil? o) (assoc-in acc [:conflicts id]
                            {:kind :delete-modify :deleted :ours :base b :theirs t})
         (nil? t) (assoc-in acc [:conflicts id]
                            {:kind :delete-modify :deleted :theirs :base b :ours o})
         :else
         (let [r (merge3-node b o t)]
           (if (:conflict r)
             (assoc-in acc [:conflicts id] {:kind :attr :attrs (:conflict r)
                                            :ours o :theirs t})
             (assoc-in acc [:merged id] (:node r)))))))
   {:merged {} :conflicts {}}
   (sort (set/union (set (keys base)) (set (keys ours)) (set (keys theirs))))))

(defn clean? [result] (empty? (:conflicts result)))

(defn resolve-conflict
  "Resolve one conflicted id by supplying its final attr-map (or nil to delete);
   moves it from :conflicts to :merged."
  [result id node]
  (-> result
      (update :conflicts dissoc id)
      (cond-> (some? node) (assoc-in [:merged id] node))))

;; ---------------------------------------------------------------------------
;; doc convenience: merged node set -> bodyJson (deterministic order)
;; ---------------------------------------------------------------------------

(def ^:private kw->kind
  {:block/paragraph "paragraph" :block/heading "heading" :block/list-item "listItem"})

(defn merged-doc->body
  "Clean merged doc node set -> bodyJson, sibling order = [block/order, id] (ties by id)."
  [merged]
  (->> merged
       (sort-by (fn [[id n]] [(:order n) id]))
       (mapv (fn [[id n]]
               (cond-> {:elementId id
                        :kind (kw->kind (:kind n) "paragraph")
                        :text (:text n)}
                 (some? (:heading-level n)) (assoc :headingLevel (:heading-level n)))))))

;; ---------------------------------------------------------------------------
;; datom-level wrappers (base/ours/theirs are full datom vectors)
;; ---------------------------------------------------------------------------

(defn merge-doc   [base-datoms ours-datoms theirs-datoms doc-id]
  (merge3 (d/doc-nodes base-datoms doc-id)
          (d/doc-nodes ours-datoms doc-id)
          (d/doc-nodes theirs-datoms doc-id)))

(defn merge-sheet [base-datoms ours-datoms theirs-datoms book-id]
  (merge3 (d/sheet-nodes base-datoms book-id)
          (d/sheet-nodes ours-datoms book-id)
          (d/sheet-nodes theirs-datoms book-id)))

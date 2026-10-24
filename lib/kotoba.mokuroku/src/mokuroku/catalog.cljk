(ns mokuroku.catalog
  "The whole kernel as one value.

  A catalog is `{source, items, query, selection}`. Every app in the
  `kotoba-lang/app-*` suite holds one of these and renders `view`. The app
  supplies its own source, its own column set, and its own chrome; it does not
  re-derive what 'sorted, filtered, selected' means."
  (:require [mokuroku.command :as command]
            [mokuroku.inspector :as inspector]
            [mokuroku.query :as query]
            [mokuroku.selection :as selection]
            [mokuroku.source :as source]))

(defn catalog
  "Build a catalog over SOURCE. Does not fetch — `refresh` does, and only the
  caller knows whether the capability grant has arrived yet."
  ([src] (catalog src {}))
  ([src q]
   {:catalog/source src
    :catalog/descriptor (source/-descriptor src)
    :catalog/items []
    :catalog/problems []
    :catalog/query (query/query q)
    :catalog/selection selection/empty-selection
    :catalog/fetched? false}))

(defn refresh
  "Pull from the source and reconcile the selection against what came back."
  [cat]
  (let [{:fetch/keys [items problems]} (source/fetch (:catalog/source cat))
        sel (selection/reconcile (:catalog/selection cat) (map :item/id items))]
    (assoc cat
           :catalog/items items
           :catalog/problems problems
           :catalog/selection sel
           :catalog/fetched? true)))

(defn with-items
  "Refresh from an item vector the host already fetched. The path a host uses
  when the capability call is async and it cannot hand back an ISource that
  answers synchronously."
  [cat items]
  (let [items (vec items)
        sel (selection/reconcile (:catalog/selection cat) (map :item/id items))]
    (assoc cat
           :catalog/items items
           :catalog/selection sel
           :catalog/fetched? true)))

(defn set-query [cat q] (assoc cat :catalog/query (query/query q)))
(defn update-query [cat f & args] (assoc cat :catalog/query (query/query (apply f (:catalog/query cat) args))))
(defn search [cat text] (update-query cat assoc :query/text text))
(defn group-by-attribute [cat k] (update-query cat assoc :query/group-by k))

(defn sort-by-attribute
  "Click a column header. Clicking the active column flips direction, which is
  the behaviour every one of these apps needs and none should re-implement."
  [cat k]
  (let [[[ck cd]] (:query/sort (:catalog/query cat))
        dir (if (= ck k) (if (= :asc cd) :desc :asc) :asc)]
    (update-query cat assoc :query/sort [[k dir]])))

(defn result [cat]
  (query/run (:catalog/items cat) (:catalog/query cat) (:catalog/descriptor cat)))

(defn select [cat id] (update cat :catalog/selection selection/select id))
(defn toggle [cat id] (update cat :catalog/selection selection/toggle id))
(defn clear-selection [cat] (update cat :catalog/selection selection/clear))

(defn extend-selection [cat id]
  (let [ids (query/ordered-ids (result cat))]
    (update cat :catalog/selection selection/extend-to ids id)))

(defn select-all [cat]
  (let [ids (query/ordered-ids (result cat))]
    (update cat :catalog/selection selection/select-all ids)))

(defn selected-items [cat]
  (selection/selected-items (:catalog/selection cat) (:result/items (result cat))))

(defn view
  "One value with everything a renderer needs and nothing it must compute.

  `:view/problems` carries both malformed source rows and nonsense in the
  query. It is deliberately not merged into one opaque error: a view that
  cannot tell 'this provider sent a bad row' from 'you filtered on a column
  that does not exist' will report the wrong one to the user."
  [cat]
  (let [res (result cat)
        sel (:catalog/selection cat)
        chosen (selection/selected-items sel (:result/items res))]
    {:view/descriptor (:catalog/descriptor cat)
     :view/result res
     :view/selection sel
     :view/query (:catalog/query cat)
     :view/inspector (inspector/inspect (:catalog/descriptor cat) res chosen)
     :view/commands (command/available (:catalog/descriptor cat) (count chosen))
     :view/fetched? (:catalog/fetched? cat)
     :view/problems {:problems/items (:catalog/problems cat)
                     :problems/query (:result/problems res)
                     :problems/dropped-selection (:selection/dropped sel)}}))

(defn propose
  "Propose COMMAND-ID against the current selection."
  ([cat command-id] (propose cat command-id nil))
  ([cat command-id argument]
   (command/propose (:catalog/descriptor cat)
                    command-id
                    (mapv :item/id (selected-items cat))
                    argument)))

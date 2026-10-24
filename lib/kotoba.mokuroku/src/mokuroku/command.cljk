(ns mokuroku.command
  "What the user may do to a selection — as a **proposal**, never as an act.

  `mokuroku` holds no capability and calls nothing. `available` answers which
  commands the source declared it accepts and the selection makes sense for;
  `propose` shapes one into a value the host can decide on. Whether that value
  is ever executed is the host's business, gated by the same capability grant
  that made the source readable in the first place.

  This is the same split `kotoba-lang/koyomi` makes between drafting an event
  and inviting anyone to it, and the reason is the same: the thing that can
  decide is not the thing that can act."
  (:require [mokuroku.source :as source]))

(def catalog
  "Commands the suite knows about. A source opts in via
  `:source/commands`; nothing here is offered by default.

  `:command/destructive?` is not styling. The host is expected to require a
  fresh, explicit confirmation for a destructive command and to refuse to
  batch it silently — deleting 4,000 files because a select-all was still in
  effect is the failure this flag exists to prevent."
  {:open        {:command/label "Open"      :command/effect :item/open
                 :command/arity :any        :command/destructive? false}
   :reveal      {:command/label "Reveal"    :command/effect :item/reveal
                 :command/arity :single     :command/destructive? false}
   :rename      {:command/label "Rename"    :command/effect :item/rename
                 :command/arity :single     :command/destructive? false
                 :command/argument :string}
   :copy-path   {:command/label "Copy Path" :command/effect :clipboard/write
                 :command/arity :any        :command/destructive? false}
   :quicklook   {:command/label "Quick Look" :command/effect :item/preview
                 :command/arity :single     :command/destructive? false}
   :play        {:command/label "Play"      :command/effect :audio/play
                 :command/arity :any        :command/destructive? false}
   :export      {:command/label "Export"    :command/effect :item/export
                 :command/arity :any        :command/destructive? false}
   :quit        {:command/label "Quit Process" :command/effect :process/signal
                 :command/arity :any        :command/destructive? true}
   :trash       {:command/label "Move to Trash" :command/effect :item/trash
                 :command/arity :any        :command/destructive? true}
   :eject       {:command/label "Eject"     :command/effect :volume/eject
                 :command/arity :single     :command/destructive? true}})

(defn- arity-ok? [command n]
  (case (:command/arity command)
    :single (= 1 n)
    :any (pos? n)
    (pos? n)))

(defn available
  "Commands offerable for this source and this many selected items.

  Intersecting with `:source/commands` is what keeps an app from offering
  Trash on a read-only source: the source, not the app, decides what it will
  accept."
  [descriptor selected-count]
  (->> catalog
       (filter (fn [[id command]]
                 (and (source/accepts? descriptor id)
                      (arity-ok? command selected-count))))
       (sort-by key)
       (mapv (fn [[id command]]
               (assoc command
                      :command/id id
                      :command/enabled? true)))))

(defn propose
  "Shape a proposal. Executes nothing.

  `:proposal/requires-confirmation?` is true for anything destructive and for
  any batch of more than one item — a host may relax the second, but it has to
  do so deliberately rather than by never being told."
  ([descriptor command-id target-ids] (propose descriptor command-id target-ids nil))
  ([descriptor command-id target-ids argument]
   (let [command (get catalog command-id)]
     (cond
       (nil? command)
       {:proposal/refused :unknown-command :proposal/command command-id}

       (not (source/accepts? descriptor command-id))
       {:proposal/refused :source-does-not-accept
        :proposal/command command-id
        :proposal/source (:source/id descriptor)}

       (not (arity-ok? command (count target-ids)))
       {:proposal/refused :wrong-arity
        :proposal/command command-id
        :proposal/arity (:command/arity command)
        :proposal/target-count (count target-ids)}

       :else
       {:proposal/command command-id
        :proposal/effect (:command/effect command)
        :proposal/source (:source/id descriptor)
        :proposal/capability (:source/capability descriptor)
        :proposal/targets (vec target-ids)
        :proposal/argument argument
        :proposal/destructive? (:command/destructive? command)
        :proposal/requires-confirmation?
        (or (:command/destructive? command) (> (count target-ids) 1))}))))

(defn refused? [proposal]
  (contains? proposal :proposal/refused))

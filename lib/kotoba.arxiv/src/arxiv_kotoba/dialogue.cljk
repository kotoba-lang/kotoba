(ns arxiv-kotoba.dialogue
  (:require [kotoba.lang.text :as str]))

(defn respond
  "Small deterministic dialogue seed. A model-backed host can replace this, but
  the actor always keeps the same boundary: dialogue explains, ops executes."
  [{:keys [text]}]
  (let [t (str/lower (str text))]
    (cond
      (str/includes? t "category")
      {:status :ok
       :text "I can advise categories from the local EDN facts, then route validation through :arxiv/advise-categories."}

      (or (str/includes? t "submit") (str/includes? t "submission"))
      {:status :ok
       :text "I can prepare a draft submission, but final arXiv submit requires human approval."}

      :else
      {:status :ok
       :text "I represent arXiv-facing workflows as an organism actor. Use functional ops for execution."})))


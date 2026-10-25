(ns ctf.model)

(def routes [:malak :yabai])
(def levels #{:clear :monitor :challenge :deny :review})

(defn request [id subject opts]
  {:ctf/id id
   :ctf/subject subject
   :ctf/purpose (:purpose opts)
   :ctf/case-ref (:case-ref opts)
   :ctf/routes (vec (or (:routes opts) routes))
   :ctf/requested-at (:requested-at opts)})

(defn result [request route level opts]
  {:ctf/id (:ctf/id request)
   :ctf/route route
   :ctf/level level
   :ctf/score (:score opts)
   :ctf/categories (set (:categories opts))
   :ctf/evidence-ref (:evidence-ref opts)
   :ctf/asserter (:asserter opts)
   :ctf/observed-at (:observed-at opts)
   :ctf/non-adjudicating true})

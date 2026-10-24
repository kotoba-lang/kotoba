(ns haishin.plan
  "Fan one artifact out into one validated request description per target.

  Planning is pure and always available — no grant, no credentials, no network.
  That is deliberate: the useful thing to be able to do at any time, including
  in CI and in a governor's review step, is to see exactly what *would* be sent
  everywhere. Nothing here can send it.

  A plan separates entries from rejections rather than failing the whole batch
  on the first bad target. A 4-minute vertical video is a valid YouTube upload
  and an invalid X post, and the right answer is to publish it to YouTube and
  report why X was skipped — not to publish nothing."
  (:require [kotoba.lang.text :as str]
            [haishin.artifact :as artifact]
            [haishin.constraints :as constraints]
            [haishin.target :as target]))

(defn- entry
  [artifact target-id opts]
  {:entry/target target-id
   :entry/request (target/request target-id artifact opts)
   :entry/warnings (target/warnings target-id artifact)})

(defn plan
  "artifact + target-ids -> plan.

  opts:
    :at                   caller-supplied timestamp string. There is no clock
                          read here — an ambient clock would make plans
                          non-reproducible and is exactly the kind of ambient
                          authority this library refuses.
    :tags?                append hashtags to composed text (default true)
    :attribution?         append the canonical source link (default true)
    :body-chars-override  raise the text limit for a target tier that allows
                          more than the documented default (X premium, ...)

  Returns:
    {:plan/artifact-id .. :plan/at ..
     :plan/entries  [{:entry/target :youtube :entry/request {..} :entry/warnings [..]}]
     :plan/rejected [{:reject/target :x :reject/problems [..]}]}

  Throws only if the *artifact itself* is malformed — that is a producer bug,
  not a per-target outcome, and silently degrading it into six identical
  rejections would bury the cause."
  ([artifact target-ids] (plan artifact target-ids {}))
  ([artifact target-ids opts]
   (let [a (artifact/normalize artifact)
         ps (artifact/problems a)]
     (when (seq ps)
       (throw (ex-info "haishin: malformed artifact"
                       {:haishin/error :malformed-artifact :problems ps})))
     (let [graded (map (fn [tid]
                         (let [problems (target/problems tid a opts)]
                           (if (seq problems)
                             [:rejected {:reject/target tid :reject/problems problems}]
                             [:entry (entry a tid opts)])))
                       target-ids)
           by-kind (group-by first graded)]
       {:plan/artifact-id (:artifact/id a)
        :plan/at (:at opts)
        :plan/entries (mapv second (:entry by-kind))
        :plan/rejected (mapv second (:rejected by-kind))}))))

(defn targets-in
  "Which targets this plan would actually send to."
  [plan]
  (into (sorted-set) (map :entry/target) (:plan/entries plan)))

(defn all-warnings
  [plan]
  (into [] (mapcat :entry/warnings) (:plan/entries plan)))

(defn summary
  "One line per target, for a CLI or a governor's review comment. Reads top to
  bottom as: what will go out, what will not, and why not."
  [plan]
  (let [sent (for [e (:plan/entries plan)
                   :let [w (count (:entry/warnings e))]]
               (str "  → " (name (:entry/target e))
                    " " (:request/endpoint (:entry/request e))
                    (when (pos? w) (str "  (" w " warning" (when (> w 1) "s") ")"))))
        skipped (for [r (:plan/rejected plan)]
                  (str "  ✗ " (name (:reject/target r)) " — "
                       (:problem/message (first (:reject/problems r)))))]
    (str/join
     "\n"
     (concat [(str "haishin plan for " (:plan/artifact-id plan)
                   " — " (count (:plan/entries plan)) " target(s), "
                   (count (:plan/rejected plan)) " skipped")]
             sent skipped))))

(defn describe-targets
  "Every target this library knows, with its limit provenance."
  []
  (mapv constraints/describe constraints/target-ids))

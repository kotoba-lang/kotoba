(ns importer.outcome
  "Three values, because two hide the one that matters.

  An importer that could not reach the provider and an importer that reached it
  and found nothing new must not answer with the same value. ADR-2608136000
  found that shape fourteen times in a single day: `measured, clean` and `could
  not measure` collapsed into one, and the silence accumulated as green.

    :synced      ran to completion. May have moved zero records.
    :failed      ran, and the provider or the sink refused.
    :unmeasured  could not run at all -- no credential, gate blocked, no
                 network, nothing to read.

  There is deliberately no `ok?` and no `success?`. A caller that wants to
  treat :unmeasured as a success has to write that down where a reviewer can
  see it.")

(def values
  "In reporting order, worst last."
  [:synced :unmeasured :failed])

(def value-set (set values))

(defn outcome? [x] (contains? value-set x))

(def ^:private severity {:synced 0 :unmeasured 1 :failed 2})

(defn exit-code
  "0 / 1 / 2. The third code exists so a shell can tell `nothing to do` from
  `I never found out`, which an exit status of 0 or 1 cannot."
  [o]
  (case o
    :synced 0
    :failed 1
    :unmeasured 2
    (throw (ex-info "not an outcome" {:importer/outcome o}))))

(defn worst
  "The outcome of a run made of several.

  :failed beats :unmeasured beats :synced. Neither of the first two is green,
  so the ordering between them only decides which word is printed -- it is
  `tally` that keeps what actually happened. An empty collection is
  :unmeasured, NOT :synced: a batch that ran nothing has not synced anything,
  and answering :synced there is the exact bug this namespace exists for."
  [outcomes]
  (let [os (filter outcome? outcomes)]
    (if (empty? os)
      :unmeasured
      (apply max-key severity (sort-by severity os)))))

(defn tally
  "Counts by outcome, all three keys always present. A report that omits the
  zero rows lets a reader mistake `no failures listed` for `no failures`."
  [outcomes]
  (merge {:synced 0 :failed 0 :unmeasured 0}
         (frequencies (filter outcome? outcomes))))

(defn green?
  "True only for :synced. Named for what it is rather than for what a caller
  hopes it is."
  [o]
  (= :synced o))

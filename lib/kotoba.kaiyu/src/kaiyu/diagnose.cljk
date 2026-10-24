(ns kaiyu.diagnose
  "What a 回遊 report SAYS is wrong — the judgment half, kept pure and separate
  from both the measuring and the acting.

  `kaiyu.core` decides what may be recorded. This decides what the recording
  means, and it is deliberately the only place that does: an orchestrator that
  both fetches and judges ends up with its rules spread through its I/O, where
  they cannot be tested and quietly become whatever the last incident made
  them.

  Every finding here is a QUESTION a human can answer, not a verdict. The data
  is counts and dates with no visitor identity (that is the whole design), so
  it can locate where attention stops and where it never arrives — it cannot
  say why. A finding that claimed to know why would be inventing the part the
  measurement deliberately does not collect.

  ## The one rule that matters

  **Absence of rows is never evidence.** `kaiyu.core/measurement-state`
  distinguishes `:not-measured` / `:partial` / `:measured`, and
  `measurement-findings` refuses to read an empty section as a fact about
  visitors. The failure this prevents is the expensive one: on 2026-08-07
  `/_metrics/audience` answered 200 with zeros for a day while the table held
  595 pageviews, because every read threw and was swallowed. A loop that judged
  that report would have filed 『誰も来ていない』 issues, and every one of them
  would have been about a broken read.

  **What turns absence back into evidence.** A `:partial` section is normally
  allowed to be empty, because collection may have started an hour ago. But
  when a sibling section began collecting on the SAME DAY OR LATER and holds
  rows, the instrument demonstrably was not silent during this section's whole
  span, and the emptiness becomes a fact about this section rather than about
  how young the collector is. Measured 2026-08-13 on kotobase.net, whose
  `transitions` had held 0 rows since 2026-08-07 while `visits` — switched on
  the same day, read in the same response — had counted 575: two of the four
  site rules had been drawing on an empty section for six days and nothing said
  so. The finding still only asks, because counts cannot separate 「誰も回遊して
  いない」 from 「辺が emit されていない」; it is `:high` rather than `:blocked`
  for the same reason.

  **What absence can also mean.** A site may never have instrumented a section
  at all, and until 2026-08-14 that returned the same value as a beacon that
  broke — the failure this library exists to prevent, aimed at itself. Such
  sections are DECLARED with `:uninstrumented`; the declaration is reported in
  `:coverage`, and a declaration its own data contradicts is `:blocked` above
  whatever it was silencing. See `measurement-findings`.

  **Where collection STOPPED.** `measurement-state` is built entirely from
  `collected-since`, so it answers where a span began and has nothing to say
  about where it ended: a beacon that wrote for two days and died reports the
  same `:partial` as one still writing, and every site rule then draws on
  frozen rows under the window's name. Measured 2026-08-15 on babiniku.net,
  whose three sections had been byte-identical since 08-11 while the tick
  reported `ok` and the queue was asked the same dead-end question on 08-11,
  08-12 and 08-13. A caller that can re-query supplies `:recent` (see
  `kaiyu.core/recent`), and `staleness-findings` asks about it. Deliberately
  never `:blocked`: a quiet site has exactly this shape, and blocking it would
  hand a low-traffic site the permanent silence `:uninstrumented` was added to
  undo, twice.

  **What this does NOT do**, written down because the opposite claim stood here
  until 2026-08-11 and was false: the four site rules receive `:rows` and never
  see `:state`. They fire on a `:partial` section, and on a `:not-measured` one
  whose `:blocked` finding was suppressed because the site went live inside the
  window. The numbers they produce are real, but they describe a shorter period
  than the window names — measured that day on babiniku.net, whose first-ever
  candidate was a dead-end drawn from a single day of edges and labelled with a
  seven-day window.

  So every finding carries the `:sections` it drew on, `diagnose` returns
  `:coverage`, and `->issue` prints the span the evidence is true within.
  Whether a rule should fire on `:partial` at all is deliberately NOT settled
  here: gating on `:measured` would silence three of four live sites until each
  accumulates a full window, and choosing silence over a caveated number is a
  product decision, not a library one."
  (:require [kotoba.lang.text :as str]
            [kaiyu.core :as kaiyu]))

(def severities
  "Ordered. `:blocked` is not a severity of the site — it is a severity of the
  MEASUREMENT, and it outranks everything because a broken instrument makes the
  other findings meaningless rather than merely less certain."
  [:blocked :high :medium :low])

(def ^:private severity-rank (zipmap severities (range)))

(defn- finding
  "`sections` are the report sections this finding was drawn from. They are
  carried so `->issue` can state the span the evidence actually covers, which
  is not the same as the span that was asked for: a rule reading a `:partial`
  section produces real numbers about a shorter period than the window names."
  [id severity title question evidence sections]
  {:id id :severity severity :title title :question question :evidence evidence
   :sections (vec sections)})

;; ───────────────────────── rules ─────────────────────────

(defn- live-collection-witness
  "The sibling section whose rows prove the instrument was reporting DURING
  this section's collecting span, or nil.

  Only a sibling that began collecting no earlier than this one qualifies. Its
  span is then contained in this one's, so its rows cannot all predate the
  moment this section was switched on — which is exactly what a sibling that
  started earlier fails to rule out. Sorted by name so the witness a finding
  cites is the same one on every platform the report is read on."
  [sections since]
  (->> sections
       (keep (fn [[k {:keys [collected-since rows]}]]
               (when (and (seq rows)
                          (some? collected-since)
                          (>= (compare collected-since since) 0))
                 {:section k :collected-since collected-since :rows (count rows)})))
       (sort-by (comp name :section))
       first))

(defn measurement-findings
  "Rules about the instrument, checked before any rule about the site.

  A section that is `:not-measured` inside a window the site was live for is
  either a beacon that stopped or a read that throws — both are urgent, and
  neither is a fact about visitors.

  **There is a third reading, and until 2026-08-14 this returned the same value
  for it.** A site can simply not instrument a section at all. kotobase.net is
  a build-time-generated multi-page site with no client script: its store
  returns `(kaiyu/section win [] nil)` as a literal constant and says so in its
  own docstring (『Dwell is not measured here』). The three answers the question
  offers — beacon stopped / read threw / nobody came — are all wrong for it, and
  no human can close the issue, because there is nothing to fix and nothing to
  wait for. Left alone it is worse than noise: `diagnose` short-circuits on
  `:blocked`, so one permanently-unanswerable finding silences every site rule
  for that site forever. Measured on kotobase.net: its window first rolled past
  `:site-live-since` for the window ending 2026-08-13, and from that window on
  its four site rules stopped being evaluated — including the acquisition
  finding that had been top in all five recorded rounds before it.

  So a site may DECLARE the sections it does not collect, via `:uninstrumented`.
  Two things keep that from becoming a mute switch:

  - the declaration is carried in `coverage`, so a reader sees 「宣言により
    計測していない」 rather than a section that quietly is not mentioned;
  - a declaration contradicted by its own data is itself `:blocked`, and ranks
    above what it was silencing. A site that starts collecting the section, or
    a declaration copied onto the wrong site, surfaces on the next tick instead
    of muting it.

  What it is NOT for: a section that is instrumented and returning nothing.
  shinshi.club's `transitions` read null on the same day, while its `dwell` —
  client-observed, same beacon, same response — held ten rows. That is the case
  this rule exists to catch, and declaring it away would delete the finding."
  [{:keys [window sections site-live-since uninstrumented]}]
  (keep (fn [[section {:keys [state collected-since rows]}]]
          (let [declared? (contains? (or uninstrumented #{}) section)
                witness (when (and (= :partial state) (empty? rows) (some? collected-since))
                          (live-collection-witness sections collected-since))]
          (cond
            ;; Checked BEFORE the declaration is honoured: a stale declaration
            ;; has to be louder than the finding it suppresses.
            (and declared? (or (seq rows) (some? collected-since)))
            (finding (keyword "kaiyu.measurement"
                              (str (name section) "-declared-uninstrumented-but-collecting"))
                     :blocked
                     (str (name section) " は「計測しない」と宣言されているのに行がある")
                     (str "この site は " (name section) " を計測しない宣言を持っているが、"
                          "この window では " (count rows) " 行"
                          (when collected-since (str "・収集開始 " collected-since))
                          "が返っている。宣言が古くなったのか、別の site の宣言が"
                          "紛れているのか。宣言はこの section の所見を黙らせるので、"
                          "先にこれを決める。")
                     {:section section :state state :collected-since collected-since
                      :rows (count rows) :declared :uninstrumented :window window}
                     [section])

            ;; Declared and empty — the shape the declaration predicts. Not a
            ;; fault, and not a silence either: `coverage` carries it.
            declared? nil

            (and (= :not-measured state)
                 (or (nil? site-live-since)
                     (<= (compare site-live-since (:from window)) 0)))
            (finding (keyword "kaiyu.measurement" (str (name section) "-not-measured"))
                     :blocked
                     (str (name section) " が測れていない")
                     (str "この window で " (name section)
                          " は 1 行も無く、収集開始日も記録されていない。"
                          "beacon が動いていないのか、読み取りが失敗しているのか、"
                          "本当に誰も来ていないのか——先にこれを決めないと、他の所見は読めない。")
                     {:section section :state state :collected-since collected-since
                      :window window}
                     [section])

            (and (= :measured state) (empty? rows))
            (finding (keyword "kaiyu.measurement" (str (name section) "-empty-while-measured"))
                     :high
                     (str (name section) " は測れているのに 0 行")
                     (str "収集は " collected-since " から続いているのに、この window の行が 0。"
                          "計測は生きていて到達が無い、という読みでよいか。")
                     {:section section :collected-since collected-since :window window}
                     [section])

            witness
            (finding (keyword "kaiyu.measurement" (str (name section) "-empty-while-collecting"))
                     :high
                     (str (name section) " は収集が動いているのに 0 行")
                     (str "収集は " collected-since " から動いているのに、この window の "
                          (name section) " は 0 行。同じ日以降に始まった "
                          (name (:section witness)) " は " (:rows witness)
                          " 行を記録しているので、計器そのものは黙っていない。"
                          "この面が本当に 0 なのか、この section だけが記録されていないのか。")
                     {:section section :state state :collected-since collected-since
                      :witness (:section witness)
                      :witness-collected-since (:collected-since witness)
                      :witness-rows (:rows witness)
                      :window window}
                     [section])

            :else nil)))
        sections))

(defn- row-volume
  "How many events the rows stand for, not how many groups they fall into.

  Rows are grouped: `{:route \"home\" :bucket \"lt10\" :count 1}` is one row
  standing for one visit, and `{:from \"home\" :to \"chat\" :count 8}` is one
  row standing for eight. Counting rows calls those the same evidence. Falls
  back to the row count for a shape carrying no `:count`, which is the most
  that can honestly be assumed about rows this does not recognise."
  [rows]
  (let [counts (keep :count rows)]
    (if (seq counts) (reduce + counts) (count rows))))

(defn- can-detect-silence?
  "Whether 0 rows in `trailing` would be surprising for a section of this volume.

  A section's own rate over the window predicts `volume × trailing/window` rows
  in the trailing span. Below one, zero is the EXPECTED observation and carries
  no information — and the rule would go on reporting it every day, because a
  single old row can never re-enter the trailing span. A test that can only
  ever fire discriminates nothing.

  Measured 2026-08-29 on shinshi.club: `dwell` held ONE row in seven days,
  predicting 0.43 in three, and was reported `:high` 『stopped』 against a
  witness whose ratio to it had not changed — one dwell per five visits over
  the window, zero per four over the span.

  Stated as `volume × trailing ≥ window` so the arithmetic is integer and
  identical on both platforms; the ratio form differs between Clojure and
  ClojureScript in the type it produces, and this is a boundary."
  [volume window trailing]
  (let [w (:days window) t (:days trailing)]
    (boolean (and (number? w) (pos? w) (number? t)
                  (>= (* volume t) w)))))

(defn- stale-sections
  "Sections holding rows in the window but none in its trailing span.

  `collected-since` must fall strictly before that span: a section switched on
  inside it cannot have been silent for it, and reading one as stale would
  report the collector's own youth as a fault."
  [sections trailing]
  (->> sections
       (keep (fn [[k {:keys [collected-since rows recent]}]]
               (when (and (seq rows)
                          (some? recent)
                          (zero? (:rows recent))
                          (some? collected-since)
                          (neg? (compare collected-since (:from trailing))))
                 {:section k :collected-since collected-since :rows (count rows)
                  :volume (row-volume rows)})))
       (sort-by (comp name :section))
       vec))

(defn staleness-findings
  "Collection that HAS rows, and none of them recent.

  `kaiyu.core/measurement-state` knows where collection began and nothing about
  where it stopped, so a beacon that wrote for two days and died reports the
  same `:partial` as one still writing — and every site rule then draws on
  frozen rows while the report carries the window's name. Measured 2026-08-15
  on babiniku.net: `visits`, `dwell` and `transitions` had been byte-identical
  across rounds since 2026-08-11, the tick reported `ok`, and the queue was
  asked the same question about a dead end computed from those rows on 08-11,
  08-12 and 08-13. Re-querying the read face for its own trailing span settled
  in one request what three rounds of snapshots could not.

  **Never `:blocked`.** A quiet site produces exactly this shape, and
  `diagnose` drops every site finding when anything is blocked — so ranking
  this above the site would hand a low-traffic site permanent silence, which is
  the failure `:uninstrumented` was added to undo, twice. It ranks with the
  other 『the rows are real but may not mean what they look like』 findings and
  suppresses nothing.

  Two readings, told apart by the same witness logic as `live-collection-witness`:

  - a sibling section holds recent rows, so the instrument is demonstrably
    still writing and this section alone went quiet;
  - nothing is recent, so either collection stopped or nobody came — which
    counts cannot separate, and which is therefore asked rather than asserted."
  [{:keys [window sections uninstrumented]}]
  (let [instrumented (remove (fn [[k _]] (contains? (or uninstrumented #{}) k)) sections)
        probe-days (some (fn [[_ s]] (get-in s [:recent :days])) instrumented)]
    (if (nil? probe-days)
      []
      (let [trailing (kaiyu/trailing-window window probe-days)
            stale (stale-sections instrumented trailing)
            fresh (->> instrumented
                       (keep (fn [[k {:keys [recent]}]]
                               (when (and (some? recent) (pos? (:rows recent)))
                                 {:section k :rows (:rows recent)})))
                       (sort-by (comp name :section))
                       first)]
        (cond
          (empty? stale) []

          ;; The floor guards only this reading. It asserts that this section
          ;; ALONE went quiet, which requires that the section was previously
          ;; loud enough for quiet to be visible. `collection-stopped` below
          ;; draws on every section at once and already says counts cannot
          ;; separate a dead collector from a quiet site, so a per-section
          ;; floor there would only weaken evidence that is stronger for being
          ;; an ensemble.
          fresh
          (mapv (fn [{:keys [section collected-since rows]}]
                  (finding (keyword "kaiyu.measurement"
                                    (str (name section) "-stopped-while-sibling-collects"))
                           :high
                           (str (name section) " は " (:from trailing) " 以降 1 行も増えていない")
                           (str "この window の " (name section) " は " rows " 行あるが、直近 "
                                (:days trailing) " 日（" (:from trailing) "〜" (:to trailing)
                                "）は 0 行。同じ応答の " (name (:section fresh)) " はその期間に "
                                (:rows fresh) " 行を記録しているので、計器そのものは黙っていない。"
                                "この section だけが記録されなくなったのか、"
                                "この面に本当に誰も来ていないのか。")
                           {:section section :collected-since collected-since
                            :rows rows :recent-rows 0 :trailing trailing
                            :witness (:section fresh) :witness-recent-rows (:rows fresh)
                            :window window}
                           [section]))
                (filterv #(can-detect-silence? (:volume %) window trailing) stale))

          :else
          [(finding :kaiyu.measurement/collection-stopped
                    :high
                    (str "計測が " (:from trailing) " 以降 1 行も増えていない")
                    (str "この window には行があるが、直近 " (:days trailing) " 日（"
                         (:from trailing) "〜" (:to trailing) "）は "
                         (str/join "・" (map (comp name :section) stale))
                         " のいずれも 0 行。beacon が止まったのか、"
                         "本当に誰も来ていないのか——この数字で所見を出す前にこれを決める。"
                         "counts と dates だけでは区別が付かない。")
                    {:sections (mapv :section stale)
                     :collected-since (into {} (map (juxt :section :collected-since) stale))
                     :rows (into {} (map (juxt :section :rows) stale))
                     :recent-rows 0 :trailing trailing :window window}
                    (mapv :section stale))])))))

(defn dead-end-findings
  "Routes people reach and never leave.

  A route with inbound edges and no outbound ones is where the journey stops.
  That is not automatically bad — a checkout confirmation SHOULD end it — so
  the finding names the route and asks, rather than asserting a defect."
  [{:keys [transitions min-visits]}]
  (let [min-visits (or min-visits 5)
        inbound (reduce (fn [m {:keys [to count]}] (update m to (fnil + 0) count)) {} transitions)
        outbound (reduce (fn [m {:keys [from count]}] (update m from (fnil + 0) count)) {} transitions)]
    (->> inbound
         (filter (fn [[route n]]
                   (and (>= n min-visits)
                        (zero? (get outbound route 0))
                        (not= route kaiyu/other-route))))
         (sort-by (comp - val))
         (map (fn [[route n]]
                (finding (keyword "kaiyu.journey" (str "dead-end-" route))
                         :medium
                         (str "「" route "」から先に進んだ人がいない")
                         (str n " 件の遷移がこの面に入り、出ていく辺が 1 件も無い。"
                              "ここで終わってよい面か（完了・退出が正しい面か）、"
                              "それとも次に行く先が見えていないのか。")
                         {:route route :inbound n :outbound 0}
                         [:transitions])))
         vec)))

(defn attention-findings
  "Routes people reach and leave immediately.

  Reads the dwell distribution per route: if the shortest bucket dominates a
  route that is not a redirect-ish surface, the page is either not answering
  the question that brought them or not showing that it does."
  [{:keys [dwell min-samples short-share]}]
  (let [min-samples (or min-samples 10)
        threshold (or short-share 0.7)
        by-route (group-by :route dwell)]
    (->> by-route
         (keep (fn [[route rows]]
                 (let [total (reduce + 0 (map :count rows))
                       shortest (reduce + 0 (map :count (filter #(= "lt10" (:bucket %)) rows)))]
                   (when (and (>= total min-samples)
                              (>= (/ (double shortest) total) threshold))
                     (finding (keyword "kaiyu.attention" (str "bounce-" route))
                              :high
                              (str "「" route "」は " (Math/round (* 100.0 (/ (double shortest) total)))
                                   "% が 10 秒未満で離れている")
                              (str total " 件中 " shortest " 件が最短バケット。"
                                   "この面は来た人の問いに答えているか、"
                                   "答えていることが見えているか。")
                              {:route route :samples total :under-10s shortest}
                              [:dwell])))))
         (sort-by (comp - :samples :evidence))
         vec)))

(defn reach-findings
  "Routes that exist and nobody arrives at.

  Named from the site's own vocabulary, so the absence is about a page that was
  built — not about a name nobody chose. Low severity on purpose: a page with
  no traffic may be perfectly deliberate."
  [{:keys [vocabulary transitions dwell]}]
  (let [seen (into #{} (concat (map :to transitions) (map :from transitions) (map :route dwell)))]
    (->> (sort (remove seen vocabulary))
         (map (fn [route]
                (finding (keyword "kaiyu.reach" (str "unreached-" route))
                         :low
                         (str "「" route "」に誰も来ていない")
                         (str "この window で " route " への遷移も滞在も 1 件も無い。"
                              "導線が無いのか、要らない面なのか。")
                         {:route route}
                         [:transitions :dwell])))
         vec)))

(defn share-pct
  "`count` of `total` as a whole percent, floored.

  Rounding reads 4756 of 4775 as 100%, and 100% is a claim these numbers do not
  make: the 19 visits it rounds away are the whole of what the question asks
  (「この入口が止まったときに残るものがあるか」). Flooring can only understate a
  share, so a title reaches 100% only when the tail really is empty and never
  answers the question ahead of the reader."
  [count total]
  (int (Math/floor (* 100.0 (/ (double count) total)))))

(defn entry-concentration-findings
  "One arrival bucket carrying nearly everything.

  Not a defect — most sites have one dominant channel — but it is the single
  fact most worth knowing before spending on any other channel, and it changes
  what every other finding is worth."
  [{:keys [visits min-total dominant-share]}]
  (let [total (reduce + 0 (map :count visits))
        threshold (or dominant-share 0.9)]
    (when (>= total (or min-total 20))
      (when-let [{:keys [source count]} (->> visits (sort-by (comp - :count)) first)]
        (when (>= (/ (double count) total) threshold)
          [(finding (keyword "kaiyu.acquisition" (str "single-channel-" source))
                    :medium
                    (str "到達の " (share-pct count total) "% が「" source "」")
                    (str total " 件中 " count " 件が 1 つの入口。"
                         "この入口が止まったときに残るものがあるか。")
                    {:source source :visits count :total total}
                    [:visits])])))))

;; ───────────────────────── entry point ─────────────────────────

(defn coverage
  "section → `{:state :collected-since}`, the boundary each section's rows are
  true within.

  Kept beside the findings rather than folded into them because a finding is a
  question about the site and this is a fact about the instrument; a reader who
  cannot see both is being asked to trust a number without its span.

  A declared-uninstrumented section carries `:declared :uninstrumented`. It is
  reported rather than dropped on purpose: a suppression a reader cannot see is
  indistinguishable from a section that passed."
  ([sections] (coverage sections #{}))
  ([sections uninstrumented]
   (reduce-kv (fn [m k {:keys [state collected-since recent]}]
                (assoc m k (cond-> {:state state :collected-since collected-since}
                             (some? recent) (assoc :recent recent)
                             (contains? (or uninstrumented #{}) k)
                             (assoc :declared :uninstrumented))))
              {} (into {} sections))))

(defn diagnose
  "A kaiyu report → ranked findings.

  `report` is what a site's read face returns, normalized to:

    {:site \"shinshi.club\"
     :window {...}                       ; kaiyu.core/window
     :vocabulary #{...}                  ; the site's route set
     :site-live-since \"YYYY-MM-DD\"     ; optional
     :uninstrumented #{:dwell}           ; optional; sections the site does not collect
     :sections {:visits {...} :dwell {...} :transitions {...}}}

  where each section is a `kaiyu.core/section` map.

  **Measurement findings short-circuit everything.** If the instrument is in
  doubt, the site findings are not reported at all — not sorted below, not
  included. Reporting both would invite acting on the ones that are easier to
  act on, which are exactly the ones that might be artefacts."
  [{:keys [sections vocabulary uninstrumented] :as report}]
  (let [measurement (into (vec (measurement-findings report))
                          (staleness-findings report))
        blocked (filter #(= :blocked (:severity %)) measurement)]
    (if (seq blocked)
      {:site (:site report)
       :window (:window report)
       :coverage (coverage sections uninstrumented)
       :uninstrumented (or uninstrumented #{})
       :findings (vec (sort-by (comp severity-rank :severity) measurement))
       :blocked? true}
      (let [rows (fn [k] (get-in sections [k :rows] []))
            findings (concat measurement
                             (attention-findings {:dwell (rows :dwell)})
                             (dead-end-findings {:transitions (rows :transitions)})
                             (entry-concentration-findings {:visits (rows :visits)})
                             (reach-findings {:vocabulary (or vocabulary #{})
                                              :transitions (rows :transitions)
                                              :dwell (rows :dwell)}))]
        {:site (:site report)
         :window (:window report)
         :coverage (coverage sections uninstrumented)
         :uninstrumented (or uninstrumented #{})
         :findings (vec (sort-by (juxt (comp severity-rank :severity) :id) findings))
         :blocked? false}))))

(defn top-finding
  "The one thing to work on. Returns nil when there is nothing to say — which
  a loop must treat as a valid outcome and not as a reason to lower the bar.
  A loop that must produce an issue every round will produce noise on the
  rounds when the site is fine, and noise is what makes a queue unread."
  [diagnosis]
  (first (:findings diagnosis)))

(def ^:private state-rank {:not-measured 0 :partial 1 :measured 2})

(defn- coverage-line
  "The 測ったこと line stating the span the evidence is actually true within.

  Reports the WORST state among the sections the finding drew on: a finding
  built from a fully measured section and a partial one is only as good as the
  partial one. nil when there is nothing to say — a caller that built a
  diagnosis by hand gets the old body rather than a fabricated boundary.

  A declared-uninstrumented section is `:not-measured` too, but 「収集開始日が
  記録されていない」 would be the wrong reason to give for it: the date is not
  missing, the collection does not exist. It is named instead, so a reader can
  tell a finding built partly on a section nobody collects from one built on a
  section whose span is genuinely unknown.

  **Both ends or neither.** 「2026-08-11 以降のみ」 names the near end of the
  span and a reader completes the far one as 『今日まで』; on babiniku.net that
  sentence was printed for four days about rows that all fell on 08-10 and
  08-11. When a trailing probe is present it is appended, so the line states a
  span rather than a start."
  [window coverage sections]
  (when-let [cs (seq (keep (fn [s] (some-> (coverage s) (assoc :section s))) sections))]
    (let [worst (apply min-key (comp state-rank :state) cs)
          since (:collected-since worst)
          stale (->> cs
                     (filter (fn [{:keys [recent]}] (and (some? recent) (zero? (:rows recent)))))
                     (sort-by (comp name :section))
                     seq)
          freshness (when stale
                      (let [trailing (kaiyu/trailing-window window (:days (:recent (first stale))))]
                        (str "。**直近 " (:days trailing) " 日（" (:from trailing) "〜"
                             (:to trailing) "）は " (str/join "・" (map (comp name :section) stale))
                             " とも 0 行**——この数字は window の終わりまで続いた話ではない")))
          line (case (:state worst)
                 :measured
                 (str "- 根拠の範囲: この window 全体（" since " から測れている）")
                 :partial
                 (str "- 根拠の範囲: **" since " 以降のみ**。"
                      "window は " (:from window) " からだが、それ以前の行は無い。"
                      "この数字を window 全体の話として読まないこと")
                 :not-measured
                 (if (= :uninstrumented (:declared worst))
                   (str "- 根拠の範囲: この site は " (name (:section worst))
                        " を**計測していない**（宣言済み）。"
                        "この数字はそれ以外の section だけから作られている")
                   (str "- 根拠の範囲: **不明**（収集開始日が記録されていない）。"
                        "この数字が何日分なのかは、この報告からは言えない"))
                 nil)]
      (when line (str line freshness)))))

(defn ->issue
  "A finding → the issue body a human reads in the queue.

  Deliberately not a fix. The data cannot say why, so an issue that proposed a
  remedy would be dressing a guess as an inference. It states what was
  measured, over what window, and the question to answer."
  [{:keys [site window coverage]} {:keys [id severity title question evidence sections]}]
  {:kind :kaizen/open-issue
   :id (str "kaizen:" site ":" (name id) ":" (:from window) "_" (:to window))
   :severity severity
   :title (str "[" site "] " title)
   :body (str/join
          "\n"
          (remove
           nil?
           [(str "## 測ったこと")
           (str "- サイト: " site)
           (str "- 期間: " (:from window) " 〜 " (:to window) "（両端含む）")
           (str "- 根拠: " (pr-str evidence))
           (coverage-line window coverage sections)
           ""
           "## 答えるべき問い"
           question
           ""
           "## この issue が言っていないこと"
           (str "回遊の計測は counts と dates だけで、訪問者を識別しない。"
                "どこで注意が止まり、どこに届いていないかは分かるが、"
                "**なぜ**は分からない。原因の推測はここには書かない。")]))})

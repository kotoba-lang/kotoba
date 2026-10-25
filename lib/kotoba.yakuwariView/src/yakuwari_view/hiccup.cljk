(ns yakuwari-view.hiccup
  "The display model -> hiccup, in a class vocabulary the consuming surface
  styles itself.

  ## Why this emits no design-system components

  The two surfaces this exists for are on different design systems.
  `network-awai/cloud-itonami`'s cockpit is on the kotoba-ui paved road
  (`kotoba-ui.core` + `appkit.core`, HIG tokens); `cloud-itonami-app` depends
  on `jp-go-digital-design-system` directly. A component here that called
  either one would force the other surface off its own paved road, and a
  component that abstracted over both would be a third design system nobody
  asked for.

  So this namespace emits plain elements carrying a documented class and
  `data-*` vocabulary, and each surface owns the CSS. That is not a
  compromise invented here — the cockpit's own hydration script already
  injects `.row` / `.pill` / `.business-card` markup for exactly the dense
  rows that 'can't be shell components', so this fits the pattern already in
  place there.

  ## The vocabulary

    .yakuwari-fleet                    root
      .yakuwari-fleet-totals           one .yakuwari-metric per figure
      .yakuwari-group                  one per business
        .yakuwari-group-head
          .yakuwari-group-name / -domain
        .yakuwari-role[data-health]    one per role; data-health is the hook
          .yakuwari-role-head
            .yakuwari-role-id
            .yakuwari-role-badge       present only when outward
          .yakuwari-role-objective
          .yakuwari-capacity           .yakuwari-pill[data-kind]
          .yakuwari-needs-human        .yakuwari-cap[data-decision]
          .yakuwari-role-problems      present only when invalid
      .yakuwari-orphans                present only when non-empty
      .yakuwari-empty                  present only when a group has no roles

  `data-health` and `data-decision` carry state instead of a class per state,
  so a surface writes one selector per value rather than one class per
  combination, and an unrecognised value still renders (unstyled) rather than
  disappearing.

  Values are emitted verbatim as strings. Nothing here escapes anything —
  hiccup renderers do that, and doing it twice double-escapes."
  (:require [kotoba.lang.text :as str]))

(defn- label
  "A keyword as text, dropping the namespace: an operator reads `director`,
  not `:network-isekai/director`."
  [v]
  (cond
    (keyword? v) (name v)
    (nil? v) ""
    :else (str v)))

(defn- qualified
  "The full keyword including namespace, for titles and data attributes where
  disambiguation matters more than brevity."
  [v]
  (if (keyword? v)
    (if-let [ns (namespace v)] (str ns "/" (name v)) (name v))
    (str v)))

(defn metric [k v]
  [:div.yakuwari-metric {:data-metric (label k)}
   [:span.yakuwari-metric-value (str v)]
   [:span.yakuwari-metric-label (label k)]])

(defn capacity
  "running / queued / blocked / desired as pills.

  `desired` is always shown, including when it is zero. A role deliberately
  scaled to zero and a role whose capacity nobody set look the same if the
  figure is hidden when falsy."
  [{:role/keys [running queued blocked desired]}]
  [:div.yakuwari-capacity
   [:span.yakuwari-pill {:data-kind "running"} (str running " running")]
   (when (pos? (or queued 0))
     [:span.yakuwari-pill {:data-kind "queued"} (str queued " queued")])
   (when (pos? (or blocked 0))
     [:span.yakuwari-pill {:data-kind "blocked"} (str blocked " awaiting a human")])
   [:span.yakuwari-pill {:data-kind "desired"} (str "desired " desired)]])

(defn needs-human
  "The capabilities this role cannot act on alone. Rendered from the policy,
  so it describes the role rather than its current queue — an empty queue
  must not make a heavily gated role look ungated."
  [{:role/keys [needs-human]}]
  (when (seq needs-human)
    [:ul.yakuwari-needs-human
     (for [{:keys [capability decision]} needs-human]
       [:li.yakuwari-cap {:data-decision (label decision)
                          :title (qualified capability)}
        (qualified capability)])]))

(defn problems
  "Why a role is invalid, on the card itself. A role that failed validation
  is still listed — dropping it would render a fleet that looks complete."
  [{:role/keys [problems]}]
  (when (seq problems)
    [:ul.yakuwari-role-problems
     (for [p problems]
       [:li.yakuwari-problem {:data-problem (label (:problem p))}
        (str/join " " (remove str/blank?
                              [(label (:problem p))
                               (when-let [c (:capability p)] (qualified c))
                               (when-let [r (:rule p)] (str "— " r))]))])]))

(defn role
  "One role card. `data-health` is the styling hook; the label is also
  written as text so the card is readable without CSS."
  [{:role/keys [id objective health outward? identity] :as r}]
  [:article.yakuwari-role {:data-health (label health)
                           :data-outward (str (boolean outward?))}
   [:header.yakuwari-role-head
    [:span.yakuwari-role-id {:title (qualified id)} (label id)]
    (when outward?
      [:span.yakuwari-role-badge
       {:title (str "corresponds outward" (when identity (str " as " identity)))}
       "outward"])
    [:span.yakuwari-role-health (label health)]]
   (when-not (str/blank? (str objective))
     [:p.yakuwari-role-objective (str objective)])
   (capacity r)
   (needs-human r)
   (problems r)])

(defn group
  "One business and its roles."
  [{:group/keys [id name domain roles totals]}]
  [:section.yakuwari-group {:data-group (label id)}
   [:header.yakuwari-group-head
    [:h3.yakuwari-group-name (or name (label id))]
    (when-not (str/blank? (str domain))
      [:span.yakuwari-group-domain (str domain)])
    [:span.yakuwari-group-count
     (str (:roles totals) (if (= 1 (:roles totals)) " role" " roles"))]]
   (if (seq roles)
     [:div.yakuwari-roles (for [r roles] (role r))]
     ;; A business with no roles is a real state, not an empty render. Saying
     ;; so beats an unexplained gap where cards should be.
     [:p.yakuwari-empty "no roles defined"])])

(defn orphans
  "Roles whose group nobody declared. Shown because the alternative is a role
  that silently appears on no surface at all."
  [{:fleet/keys [orphan-roles]}]
  (when (seq orphan-roles)
    [:section.yakuwari-orphans
     [:h3.yakuwari-orphans-head "roles with no declared group"]
     [:ul
      (for [{:role/keys [id group]} orphan-roles]
        [:li.yakuwari-orphan (str (qualified id) " → " (qualified group))])]]))

(defn fleet-totals [{:fleet/keys [totals]}]
  [:div.yakuwari-fleet-totals
   (metric :roles (:roles totals))
   (metric :running (:running totals))
   (metric :queued (:queued totals))
   (metric :awaiting-a-human (:blocked totals))
   (metric :outward (:outward totals))
   (when (pos? (:invalid totals)) (metric :invalid (:invalid totals)))])

(defn fleet
  "The whole projection as one tree. A surface may instead call `group` /
  `role` piecemeal to place them in its own layout — that is the expected
  use for the cockpit, which has its own pane structure."
  [projection]
  [:div.yakuwari-fleet
   (fleet-totals projection)
   (for [g (:fleet/groups projection)] (group g))
   (orphans projection)])

(defn hil-queue
  "The held-run queue as rows — the local workspace app's primary view.
  Recency ordering is the model's job (`model/hil-queue`); this only renders
  what it is given, so the two cannot disagree about order."
  [rows]
  [:ul.yakuwari-hil-queue
   (if (seq rows)
     (for [row rows
           :let [{run-id :run/id goal :run/goal
                  role-id :role/id group :role/group
                  objective :role/objective} row]]
       [:li.yakuwari-hil-row {:data-run (str run-id)}
        [:span.yakuwari-hil-role (qualified role-id)]
        (when group [:span.yakuwari-hil-group (label group)])
        ;; The run's own goal when it has one, else the role's objective —
        ;; a row with neither would be an approval request with nothing
        ;; stating what is being approved.
        [:span.yakuwari-hil-goal (str (or goal objective ""))]])
     [:li.yakuwari-empty "nothing is waiting on you"])])

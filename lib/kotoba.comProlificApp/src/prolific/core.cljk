(ns prolific.core
  "Portable Prolific domain logic — reward arithmetic, filter resolution,
  study payload construction, submission triage.

  Everything here is pure: it takes already-fetched data and returns data.
  The HTTP side lives in `prolific.client`. That split is the point — the
  parts worth getting right (what a participant is paid, which population is
  recruited, which submissions get money) are the parts you want to test
  without a network or a token."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------- rewards

;; Prolific's own recommended rate is USD 12.00/hour; the hard floor is 8.00.
;; Defaulting to the floor buys rushed, resentful participants and unusable
;; free text, which is a false economy on a study whose entire output is
;; written answers.
(def default-hourly-usd 12.00)

;; Corporate platform fee. Academic/non-profit is 33.3%.
(def default-fee-rate 0.428)

;; Money is computed in integer cents, never in floating point.
;;
;; This is not stylistic. The first version used `(* 100 hourly (/ minutes 60))`
;; and the JVM evaluated it to 200.00000000000006 where JS got exactly 200 —
;; so `Math/ceil` crossed to the next 5c bracket on one host and not the
;; other, and the same study paid $2.05 under `clojure` and $2.00 under `nbb`.
;; A reward that depends on which runtime happened to build the payload is a
;; bug you find in a participant's complaint, not in a test.

(defn- ceil-div
  "Integer ceiling division. Positive operands only."
  [a b]
  (quot (+ (long a) (dec (long b))) (long b)))

(defn- round-div
  "Integer division rounding half up. Positive operands only."
  [a b]
  (quot (+ (long a) (quot (long b) 2)) (long b)))

(defn reward-cents
  "Whole cents for `minutes` of work, rounded UP to the next 5c so the
  displayed hourly rate never lands under the target.

  Identical on every host: the only float operation is converting the
  configured hourly rate to cents once, on a small number."
  ([minutes] (reward-cents minutes default-hourly-usd))
  ([minutes hourly-usd]
   (let [hourly-cents (long (Math/round (* 100.0 (double hourly-usd))))
         per-session (ceil-div (* hourly-cents (long minutes)) 60)]
     (* 5 (ceil-div per-session 5)))))

(defn cost-breakdown
  "What a run costs, before committing to it."
  ([places minutes] (cost-breakdown places minutes default-hourly-usd default-fee-rate))
  ([places minutes hourly-usd fee-rate]
   (let [reward (reward-cents minutes hourly-usd)
         participants (* reward (long places))
         ;; Fee in basis points so the multiply stays integral.
         fee-bp (long (Math/round (* 10000.0 (double fee-rate))))
         fee (round-div (* participants fee-bp) 10000)]
     {:reward-cents reward
      :places (long places)
      :minutes (long minutes)
      :participant-total-cents participants
      :platform-fee-cents fee
      :total-cents (+ participants fee)})))

(defn usd
  "Cents -> \"$12.34\"."
  [cents]
  (let [c (long cents)]
    (str "$" (quot c 100) "." (subs (str (+ 100 (rem c 100))) 1))))

;; ---------------------------------------------------------------- filters

;; Prolific's filter vocabulary is account-scoped and its choice ids are
;; opaque ("0", "13", …). Resolve them from the live /filters/ response
;; rather than hardcoding: a hardcoded id silently recruits the wrong
;; population the day Prolific renumbers a choice list.

(defn- filter-text [flt]
  (str/lower (str (:title flt) " " (:question flt) " " (:description flt))))

(def preferred-language-filter-ids
  "Tried in order, by exact `filter_id`.

  Fluency first, then first/primary language: what decides whether someone can
  do the task is whether they can read the screen, not what they grew up
  speaking."
  ["fluent-languages" "first-language" "primary-language"])

(def ^:private language-probe
  #{"english" "spanish" "french" "arabic" "chinese" "german" "portuguese"})

(defn language-choices?
  "Does this filter's choice list consist OF languages?

  The discriminator is structural rather than a name guess: a language filter
  offers languages as its options. Two exact label hits from the probe set is
  enough to tell one from a filter that merely mentions languages in its
  question."
  [flt]
  (>= (count (for [[_ label] (:choices flt)
                   :when (contains? language-probe
                                    (str/lower (str/trim (str label))))]
               label))
      2))

(defn language-filter
  "The filter whose choices are languages, preferring fluency.

  Chosen by exact `filter_id` first, because the text heuristic that used to
  do this job picked the wrong filter against the live API — a defect no
  fixture could show, since the fixture had four filters and the account has
  491.

  It scanned title/question/description for \"language\" and then for
  \"fluent\", and `english-speaking-monolingual` (index 303) matched both: its
  question reads \"are you fluent only in English?\". `fluent-languages` sits
  at index 388 and was never reached. The chosen filter's options are
  monolingualism categories — \"I only know English\", \"I know one other
  language…\" — so no language matched and `resolve-languages` returned
  `:unmatched` for all five requested languages.

  The invariant held: an unmatched language is reported, never dropped, so
  this surfaced as a refusal rather than as a study recruiting the wrong
  population. But live language resolution did not work at all.

  The text heuristic survives as a last resort, now gated on
  `language-choices?` so a filter that only talks about languages cannot win
  again."
  [filters]
  (let [by-id (into {} (map (juxt :filter_id identity)) filters)]
    (or (some by-id preferred-language-filter-ids)
        (first (filter #(and (= "select" (:type %))
                             (str/includes? (filter-text %) "language")
                             (language-choices? %))
                       filters)))))

(defn match-languages
  "{requested [[choice-id label] …]}. Substring matching on purpose: a pool
  labelled \"Chinese (Mandarin)\" and \"Chinese (Cantonese)\" should both
  count for \"Chinese\"."
  [flt wanted]
  (into {}
        (for [w wanted]
          [w (vec (for [[cid label] (:choices flt)
                        :when (str/includes? (str/lower (str label))
                                             (str/lower w))]
                    [(name cid) (str label)]))])))

(defn resolve-languages
  "{:filter_id … :selected_values [...] :labels [...]} or
   {:error :no-language-filter} / {:error :unmatched :missing [...] :choices …}.

  Returns the failure as data rather than throwing: an unmatched language must
  never be silently dropped, because dropping one recruits a population nobody
  asked for, but the caller decides how loudly to complain."
  [filters wanted]
  (if-let [flt (language-filter filters)]
    (let [matched (match-languages flt wanted)
          missing (vec (keep (fn [[w hits]] (when (empty? hits) w)) matched))]
      (if (seq missing)
        {:error :unmatched :missing missing
         :filter_id (:filter_id flt) :choices (:choices flt)}
        {:filter_id (:filter_id flt)
         :selected_values (vec (distinct (mapcat #(map first %) (vals matched))))
         :labels (vec (distinct (mapcat #(map second %) (vals matched))))}))
    {:error :no-language-filter}))

(defn pool-reads?
  "Does the resolved pool include a reader of `language`? Used to refuse
  recruiting people who cannot read the surface they are being sent to."
  [labels language]
  (boolean (some #(str/includes? (str/lower (str %))
                                 (str/lower language))
                 labels)))

;; ------------------------------------------------------------------ study

(defn study-payload
  "The body for POST /studies/.

  `task` supplies :name :description :minutes; `opts` supplies :places,
  :completion-code, :external-url and the resolved :language-filter."
  [{:keys [name description minutes internal-name]}
   {:keys [places completion-code external-url language-filter
           hourly-usd device-compatibility]}]
  (cond-> {:name name
           :description description
           :external_study_url external-url
           :prolific_id_option "url_parameters"
           :completion_codes [{:code completion-code
                               :code_type "COMPLETED"
                               :actions [{:action "AUTOMATICALLY_APPROVE"}]}]
           :total_available_places places
           :estimated_completion_time minutes
           :reward (reward-cents minutes (or hourly-usd default-hourly-usd))
           :device_compatibility (or device-compatibility ["desktop"])
           :peripheral_requirements []
           :filters (if language-filter
                      [{:filter_id (:filter_id language-filter)
                        :selected_values (:selected_values language-filter)}]
                      [])}
    internal-name (assoc :internal_name internal-name)))

;; ------------------------------------------------------------ submissions

;; GET /submissions/?study=… — note this is NOT /studies/{id}/submissions/,
;; a path that does not exist.
(def submission-statuses
  #{"RESERVED" "ACTIVE" "TIMED-OUT" "AWAITING REVIEW"
    "APPROVED" "RETURNED" "REJECTED" "SCREENED OUT"})

(defn awaiting-review
  "Submissions still owed a decision — the ones that block someone's payment."
  [submissions]
  (filter #(= "AWAITING REVIEW" (:status %)) submissions))

(defn reached-debrief?
  "Did this submission come back with a completion code? Those that did not
  are the participants who abandoned the task — the people a completion-code
  auto-approval rule cannot reach, and the ones a study most needs to hear
  from. They are owed payment all the same."
  [submission]
  (boolean (not-empty (str (:study_code submission)))))

(defn triage
  "Split a study's submissions into what an operator actually has to act on."
  [submissions]
  (let [pending (awaiting-review submissions)]
    {:total (count submissions)
     :by-status (frequencies (map :status submissions))
     :pending pending
     :pending-with-code (vec (filter reached-debrief? pending))
     :pending-abandoned (vec (remove reached-debrief? pending))}))

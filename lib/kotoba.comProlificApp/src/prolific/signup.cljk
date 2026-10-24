(ns prolific.signup
  "The Prolific researcher signup as data: steps, fields, and who may fill
  each one.

  The step list is transcribed from a real traversal on 2026-07-30, not from
  Prolific's docs — the flow is a single route (`/register/researcher/email`)
  that advances by fragment (`#country`, `#professional_profile`), which
  matters because it means the URL alone is weak evidence of progress (see
  `prolific.evidence/navigated?`).

  Why the human/machine split is four categories and not two
  -----------------------------------------------------------
  Lumping every human-only field under \"needs a human\" hides the only
  distinction worth acting on. Three of these can never be automated, and
  one is simply data nobody has written down yet:

    :human/credential   passwords. A permanent boundary.
    :human/captcha      bot-detection. A permanent boundary.
    :human/consent      terms, marketing opt-in, cookie banners. A consent
                        is given by a person; an agent cannot hold it.
    :human/unknown-fact country of residence. NOT a boundary — the run
                        stopped because nobody had stated the value, and it
                        becomes machine-fillable the moment the profile
                        carries it.

  Conflating the fourth with the first three is what makes an onboarding
  runner look permanently 60% manual when it is actually 80% automatable
  with two more lines of config. `gaps` reports exactly that difference.

  Pure: takes a profile map, returns a plan."
  (:require [kotoba.lang.text :as str]))

(def boundary-reasons
  "Reasons that no amount of configuration will lift."
  #{:human/credential :human/captcha :human/consent})

(def steps
  "Ordered. `:step/marker` is text that only the NEXT screen renders, used
  as the second half of navigation evidence.

  `:step/advance-is-consent` marks a step whose NEXT BUTTON IS ITSELF the
  agreement. Observed on the live form 2026-07-30: the email step has no
  terms checkbox at all — the text \"I agree to Prolific's Researcher Terms\"
  sits directly above the Next button, so pressing Next is the act of
  agreeing. A runner looking for a checkbox to leave alone finds none,
  concludes there is no consent on this step, and enters a binding contract
  by pressing what looks like navigation.

  This is why consent cannot be modelled as a field type. It is a property
  of the transition."
  [{:step/id :email
    :step/heading "What's your organization email?"
    :step/marker "country of residence"
    :step/advance-is-consent :terms
    :step/fields
    [{:field/id :email
      :field/label "Email"
      :field/kind :text
      :field/profile-key :email
      :field/actor :machine}
     {:field/id :marketing-opt-in
      :field/label "Check here to occasionally receive emails"
      :field/kind :checkbox
      :field/actor :human
      :field/reason :human/consent
      ;; Left unchecked rather than merely unfilled: declining non-essential
      ;; collection is the default, so "do nothing" is already the right
      ;; answer here and no human decision is blocked on it.
      :field/default :unchecked}
     {:field/id :privacy-banner
      :field/label "We collect and process your personal information"
      :field/kind :consent-banner
      :field/actor :human
      :field/reason :human/consent
      :field/recommend "Decline — the stated purposes include Marketing"}]}

   {:step/id :country
    :step/heading "What's your country of residence?"
    :step/marker "Tell us about your work"
    :step/fields
    [{:field/id :country-of-residence
      :field/label "Country of residence"
      :field/kind :radio
      :field/options ["United States" "United Kingdom" "Other"]
      :field/profile-key :country-of-residence
      :field/actor :machine
      ;; Machine-fillable ONLY from an explicit profile value. It asks where
      ;; a person lives, not where the company is registered, and it has tax
      ;; and jurisdiction consequences — so an absent value must surface as
      ;; :human/unknown-fact rather than be inferred from the org's
      ;; incorporation state.
      :field/no-inference "the holder's residence is not the company's jurisdiction"}]}

   {:step/id :professional-profile
    :step/heading "Tell us about your work"
    ;; Was "password", left stale when the :name step was discovered and
    ;; inserted after this one. Inserting a step invalidates the marker of the
    ;; step BEFORE it, and only that one — a marker names the next screen, so
    ;; it is the one field here that is not local to its own step.
    ;;
    ;; The check caught it twice rather than once: the first traversal reported
    ;; `moved? true marked? false` and led to finding :name, and the second
    ;; reported it again because fixing the model meant adding the step, not
    ;; correcting the pointer. Worth keeping as a reminder that this field
    ;; couples adjacent steps.
    :step/marker "What should we call you"
    :step/fields
    [{:field/id :sector
      :field/label "Sector"
      :field/kind :select
      :field/profile-key :sector
      :field/actor :machine}
     {:field/id :organization-name
      :field/label "Organization Name"
      :field/kind :text
      :field/profile-key :organization-name
      :field/actor :machine}
     ;; A typeahead, not a plain text box. Writing a value that is not in its
     ;; suggestion list leaves the field in an uncommitted state, and on blur
     ;; it substituted its own nearest suggestion: "Research Operations"
     ;; became "User Researcher" AFTER the write had been verified :match.
     ;; The widget offers its own escape — a "Press Enter to use <text>"
     ;; control — so :commit names it. Clicking that control is used rather
     ;; than pressing Enter, which in a form can submit it.
     {:field/id :job-role
      :field/label "Job Role"
      :field/kind :text
      :field/commit :typeahead
      :field/profile-key :job-role
      :field/actor :machine}
     {:field/id :department
      :field/label "Department"
      :field/kind :text
      :field/commit :typeahead
      :field/profile-key :department
      :field/actor :machine}]}

   ;; Discovered only by advancing: the flow is email -> country ->
   ;; professional_profile -> name -> credentials, and this step was absent
   ;; from the model transcribed on the first traversal. The marker check is
   ;; what surfaced it — advancing from :professional-profile reported
   ;; `moved? true marked? false`, i.e. the page went somewhere that was not
   ;; the screen the model predicted. A weaker check (URL only) would have
   ;; called it success and the next step would have written a first name into
   ;; a password field.
   {:step/id :name
    :step/heading "What should we call you?"
    :step/marker "password"
    :step/fields
    [{:field/id :first-name
      :field/label "First name"
      :field/kind :text
      :field/profile-key :first-name
      :field/actor :machine}
     {:field/id :last-name
      :field/label "Last name"
      :field/kind :text
      :field/profile-key :last-name
      :field/actor :machine}]}

   ;; Never reached. The terms live on the :email step (see
   ;; :step/advance-is-consent), so this step's contents are modelled from the
   ;; boundary rather than from observation and its labels may be wrong.
   {:step/id :credentials
    :step/heading "Create a password"
    :step/marker nil
    :step/observed? false
    :step/fields
    [{:field/id :password
      :field/label "Password"
      :field/kind :password
      :field/actor :human
      :field/reason :human/credential}
     {:field/id :captcha
      :field/label "reCAPTCHA"
      :field/kind :captcha
      :field/actor :human
      :field/reason :human/captcha}]}])

(defn consent-gates
  "Steps a machine must not advance, and what agreeing would commit to.

  Separate from `gaps` on purpose: a consent gate is not a missing value, it
  is a transition that only a person may make. A caller drives the fields of
  such a step and then stops."
  []
  (vec (for [s steps :when (:step/advance-is-consent s)]
         {:step (:step/id s)
          :commits (:step/advance-is-consent s)
          :note "the Next button is the agreement; there is no checkbox"})))

(defn may-advance?
  "May a machine press this step's Next button?"
  [step-id]
  (not-any? #(= step-id (:step %)) (consent-gates)))

(defn- blank? [v]
  (or (nil? v) (and (string? v) (str/blank? v))))

(defn classify
  "One field against a profile: fill it, or say precisely why not.

  A `:machine` field with no profile value is reported as
  `:human/unknown-fact` — an automation gap — and never guessed. That is the
  whole reason this returns a reason keyword instead of dropping the field."
  [field profile]
  (let [{:field/keys [id actor reason profile-key]} field
        value (when profile-key (get profile profile-key))]
    (cond
      (= :human actor)
      {:field id :action :blocked :reason reason
       :recommend (:field/recommend field)
       :default (:field/default field)}

      (blank? value)
      {:field id :action :blocked :reason :human/unknown-fact
       :profile-key profile-key
       :because (:field/no-inference field)}

      :else
      {:field id :action :fill
       :label (:field/label field)
       :kind (:field/kind field)
       :commit (:field/commit field)
       :value value})))

(defn plan
  "The whole signup as a per-step plan for `profile`.

  Returns one entry per step with `:fill` and `:blocked`. Callers execute
  `:fill` and hand `:blocked` to a human; nothing here performs any action."
  [profile]
  (mapv (fn [step]
          (let [classified (mapv #(classify % profile) (:step/fields step))]
            {:step (:step/id step)
             :heading (:step/heading step)
             :marker (:step/marker step)
             :fill (filterv #(= :fill (:action %)) classified)
             :blocked (filterv #(= :blocked (:action %)) classified)}))
        steps))

(defn gaps
  "Blocked fields split into what config can fix and what it cannot.

  This is the number to watch across iterations. `:closable` shrinking is
  progress; `:boundary` shrinking would mean something has gone wrong."
  [profile]
  (let [blocked (mapcat :blocked (plan profile))]
    {:boundary (vec (filter #(contains? boundary-reasons (:reason %)) blocked))
     :closable (vec (remove #(contains? boundary-reasons (:reason %)) blocked))}))

(defn coverage
  "What fraction of fields this profile can fill, and which keys would raise
  it. Reported so a run states its own automation level instead of implying
  completeness."
  [profile]
  (let [p (plan profile)
        filled (count (mapcat :fill p))
        {:keys [boundary closable]} (gaps profile)
        total (+ filled (count boundary) (count closable))]
    {:fields total
     :machine-filled filled
     :closable-gaps (mapv :profile-key closable)
     :permanent-boundaries (count boundary)
     ;; Integer permille, so the figure is identical on every host for the
     ;; same reason the money path is integer cents.
     :automatable-permille (if (pos? total)
                             (quot (* 1000 (+ filled (count closable))) total)
                             0)}))

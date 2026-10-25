(ns kotoba.statement-fetch
  "Declarative retrieval of bank / brokerage statements through an external
  browser-automation CLI (`agent-browser`).

  This namespace is **pure**: it validates institution flow definitions and
  compiles them into argv vectors. It performs no I/O. A host driver
  (`kotoba.statement-fetch.agent-browser`) executes the argv it produces.

  ## Safety invariant

  A flow may never carry a step that types authentication material. This is
  not a convention — `validate-flow` rejects such a flow, so a flow that
  types a banking password cannot be compiled at all.

  Authentication is modelled as exactly one `:handoff` step: the run stops,
  control returns to a human operator who authenticates through their own
  password manager, and the driver resumes only once the operator confirms.
  The agent never observes the credential."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; Safety
;; ---------------------------------------------------------------------------

(def secret-keys
  "Step keys that would carry authentication material. Their presence is a
  hard validation failure regardless of the value."
  #{:step/password :step/secret :step/credential :step/pin :step/otp
    :step/token :step/passphrase})

(def secret-text-re
  "Matches selectors/values that name authentication material, in the
  languages these flows are written in."
  #"(?i)password|passwd|passcode|secret|credential|\botp\b|\bpin\b|token|パスワード|暗証|認証番号|ワンタイム")

(defn- secret-bearing?
  "True when `step` would put authentication material into the page."
  [step]
  (or (some #(contains? step %) secret-keys)
      (and (= :fill (:step/type step))
           (boolean (some #(and (string? %) (re-find secret-text-re %))
                          [(:step/selector step) (:step/value step)])))))

;; ---------------------------------------------------------------------------
;; Flow validation
;; ---------------------------------------------------------------------------

(def step-types
  #{:navigate :click :fill :select :wait :expect :download :snapshot :handoff})

(defn- step-errors [idx step]
  (let [t (:step/type step)]
    (cond-> []
      (not (contains? step-types t))
      (conj {:error/kind :unknown-step-type :error/index idx :error/type t})

      (secret-bearing? step)
      (conj {:error/kind :credential-step-forbidden
             :error/index idx
             :error/note "authentication must be a :handoff step; the agent never types credentials"})

      (and (= :navigate t) (not (string? (:step/url step))))
      (conj {:error/kind :missing-url :error/index idx})

      (and (contains? #{:click :fill :select :expect :download} t)
           (not (string? (:step/selector step))))
      (conj {:error/kind :missing-selector :error/index idx :error/type t})

      (and (= :download t) (not (string? (:step/path step))))
      (conj {:error/kind :missing-download-path :error/index idx}))))

(defn validate-flow
  "Returns a (possibly empty) vector of error maps for `flow`.

  A flow is valid when it names an institution, authenticates via exactly one
  `:handoff` step, and carries no credential-bearing step anywhere."
  [flow]
  (let [login (:flow/login flow)
        steps (vec (:flow/steps flow))]
    (into
     (cond-> []
       (not (keyword? (:institution/id flow)))
       (conj {:error/kind :missing-institution-id})

       (not (map? login))
       (conj {:error/kind :missing-login-handoff})

       (and (map? login) (not= :handoff (:step/type login)))
       (conj {:error/kind :login-must-be-handoff
              :error/note "credentials are entered by a human, never by the agent"})

       (and (map? login) (not (string? (:handoff/url login))))
       (conj {:error/kind :missing-handoff-url})

       (some #(= :handoff (:step/type %)) steps)
       (conj {:error/kind :handoff-outside-login
              :error/note "the only handoff is :flow/login"})

       (empty? steps)
       (conj {:error/kind :empty-flow}))
     (mapcat #(step-errors %1 %2) (range) steps))))

(defn valid-flow?
  [flow]
  (empty? (validate-flow flow)))

;; ---------------------------------------------------------------------------
;; Parameter substitution
;; ---------------------------------------------------------------------------

(def ^:private param-re #"\{\{([a-zA-Z0-9_-]+)\}\}")

(defn render
  "Substitutes `{{name}}` placeholders in `s` from `params` (keyword keys).
  An unknown placeholder is left intact so `missing-params` can report it."
  [s params]
  (if-not (string? s)
    s
    (str/replace s param-re
                 (fn [m]
                   (let [k (keyword (second m))]
                     (if (contains? params k)
                       (str (get params k))
                       (first m)))))))

(defn missing-params
  "Placeholder names in `flow` that `params` does not supply."
  [flow params]
  (->> (concat (vals (:flow/login flow)) (mapcat vals (:flow/steps flow)))
       (filter string?)
       (mapcat #(map second (re-seq param-re %)))
       (map keyword)
       (remove #(contains? params %))
       distinct
       vec))

;; ---------------------------------------------------------------------------
;; Compilation to argv
;; ---------------------------------------------------------------------------

(defn step->argv
  "Compiles one resolved step into an `agent-browser` argv tail, or nil for
  steps the driver handles itself (`:handoff`)."
  [{:step/keys [type url selector value values path timeout] :as _step}]
  (case type
    :navigate ["open" url]
    :click    ["click" selector]
    :fill     ["fill" selector (str value)]
    :select   (into ["select" selector] (map str (or values [value])))
    :wait     ["wait" (str (or timeout selector))]
    :expect   ["is" "visible" selector]
    :download ["download" selector path]
    :snapshot ["snapshot" "-i" "-c"]
    :handoff  nil
    nil))

(defn plan
  "Compiles `flow` + `params` into an executable plan.

  Returns `{:plan/institution … :plan/login … :plan/steps [step …]}` where
  every step carries a resolved `:step/argv`. Throws when the flow is invalid
  or a placeholder is unresolved — a half-resolved banking flow must never
  reach a browser."
  [flow params]
  (let [errors (validate-flow flow)]
    (when (seq errors)
      (throw (ex-info "invalid statement-fetch flow" {:errors errors
                                                      :institution (:institution/id flow)}))))
  (let [missing (missing-params flow params)]
    (when (seq missing)
      (throw (ex-info "unresolved flow parameters" {:missing missing
                                                    :institution (:institution/id flow)}))))
  (let [resolve-step (fn [step]
                       (reduce-kv (fn [m k v] (assoc m k (render v params))) {} step))
        login (resolve-step (:flow/login flow))]
    {:plan/institution (:institution/id flow)
     :plan/name        (:institution/name flow)
     :plan/login       login
     :plan/steps       (mapv (fn [step]
                               (let [s (resolve-step step)]
                                 (assoc s :step/argv (step->argv s))))
                             (:flow/steps flow))}))

(defn session-argv
  "Global `agent-browser` flags for a run. `profile` reuses an existing Chrome
  profile so an operator's own authenticated session — established through
  their password manager — is what the flow runs against."
  [{:keys [session profile]}]
  (cond-> []
    session (into ["--session" session])
    profile (into ["--profile" profile])))

(defn unverified-steps
  "Steps still carrying selectors that no real run has confirmed. Flow
  definitions start life this way; a discovery run replaces them."
  [flow]
  (->> (:flow/steps flow)
       (map-indexed vector)
       (filter (fn [[_ s]] (:step/unverified s)))
       (mapv (fn [[i s]] (assoc s :step/index i)))))

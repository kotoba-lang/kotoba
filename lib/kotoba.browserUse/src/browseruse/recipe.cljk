(ns browseruse.recipe
  "Reusable, data-driven web-form RECIPE runner over IBrowser.

  The fragile part of GUI automation is targeting: pixel coordinates drift,
  element indices shift between renders, and a small vision model mis-clicks. A
  recipe instead REMEMBERS TAGS as *semantic element matchers* (by tag + name /
  placeholder / text), re-resolved against the live indexed elements
  (`browseruse.browser/-state`) at every step — deterministic, replayable, and
  robust to index shifts. No model is in the loop: this is a recorded procedure,
  not an agent. Steps can capture screenshots for verification and pause for a
  human (e.g. a CAPTCHA the automation must NOT solve).

  A recipe is plain data, so a registration/login/whatever flow becomes a
  reusable, version-controllable artifact:

    {:url \"https://site/register\"
     :steps [{:do :fill  :match {:tag \"input\" :name \"name\"}  :value \"etzhayyim\"}
             {:do :fill  :match {:tag \"input\" :name \"mail\"}  :value \"me@x.com\"}
             {:do :fill  :match {:tag \"input\" :name \"pass[pass1]\"} :value {:secret \"vault/ref\"}}
             {:do :screenshot :as \"filled\"}
             {:do :wait-human :prompt \"Solve the CAPTCHA, then continue\"}
             {:do :click :match {:tag \"button\" :text \"Create new account\"}}]}"
  (:require [browseruse.browser :as b]
            [browseruse.guardrail :as guardrail]
            [browseruse.captcha :as captcha]
            [browseruse.history :as history]
            [browseruse.session :as session]
            [kotoba.lang.text :as str]))

(defn- norm [s] (str/lower (str/trim (or s ""))))

(defn match-index
  "Resolve a semantic matcher to the index of the first live element satisfying
  it (all provided keys ANDed). Keys (all optional):
    :tag         exact tag (a/input/button/select/textarea)
    :name        attrs.name equals (case-insensitive)
    :placeholder attrs.placeholder contains
    :text        text contains (case-insensitive)
    :href        attrs.href contains
    :occurrence  pick the nth (0-based) among matches (default 0)
  Returns the element :index, or nil if no match."
  [elements {:keys [tag name placeholder text href occurrence] :or {occurrence 0}}]
  (let [hits (->> elements
                  (filter (fn [{t :tag tx :text a :attrs}]
                            (and (or (nil? tag) (= (norm tag) (norm t)))
                                 (or (nil? name) (= (norm name) (norm (:name a))))
                                 (or (nil? placeholder)
                                     (str/includes? (norm (:placeholder a)) (norm placeholder)))
                                 (or (nil? text) (str/includes? (norm tx) (norm text)))
                                 (or (nil? href) (str/includes? (norm (:href a)) (norm href))))))
                  vec)]
    (when (< occurrence (count hits))
      (:index (clojure.core/nth hits occurrence)))))

(defn- resolve-value [v resolve-secret]
  (cond
    (string? v) v
    (and (map? v) (:secret v)) (resolve-secret (:secret v))
    (and (map? v) (contains? v :env)) #?(:clj (or (System/getenv (:env v)) "") :cljs "")
    :else (str v)))

(defn run-recipe!
  "Execute a recipe against an IBrowser. Stops at the first failed step.
  Returns {:ok bool :log [step-result …] :state <final state> :error <str?>}.

  opts:
    :resolve-secret (fn [ref] -> string)   resolve {:secret ref} values (e.g. vault)
    :screenshot     (fn [name] -> path)    capture a screenshot (no-op default)
    :pause          (fn [prompt] -> any)   handle :wait-human (no-op default)
    :verbose        bool                   println each step

  step :do values:
    :navigate {:url ..}                    go to a URL
    :fill     {:match .. :value ..}        type into the matched element
    :select   {:match .. :value ..}        choose an <option> (needs :select opt fn)
    :check    {:match ..}                  tick a checkbox (needs :check opt fn)
    :click    {:match ..}                  click the matched element
    :assert   {:match ..}                  fail unless the element exists
    :screenshot {:as ..}                   capture a screenshot
    :wait-human {:prompt ..}               generic operator pause
    :captcha {:mode :human|:external ...}  bounded CAPTCHA orchestration"
  [browser {:keys [url steps]}
   {:keys [resolve-secret screenshot pause select check verbose settings session history]
    :or {resolve-secret (fn [_] (throw (ex-info "recipe: no :resolve-secret given" {})))
         screenshot (fn [_] nil)
         pause (fn [_] nil)
         select (fn [_ _] (throw (ex-info "recipe: :select step needs a :select opt fn (host capability)" {})))
         check (fn [_] (throw (ex-info "recipe: :check step needs a :check opt fn (host capability)" {})))}}]
  (let [settings (guardrail/policy settings)
        audit-settings (cond-> settings
                         (:captcha settings)
                         (update :captcha captcha/public-settings))
        session (or session (session/create-session {:id "recipe"}))
        history (or history (atom (history/empty-history (:id session) audit-settings)))]
  (when url
    (guardrail/assert-action! settings {:name "navigate" :input {:url url}})
    (b/-navigate! browser url))
  (loop [remaining steps log [] step-number 1]
    (if (empty? remaining)
      {:ok true :log log :state (b/-state browser) :history @history :session session}
      (let [{:keys [do match value as prompt] :as step} (first remaining)
            els (:elements (b/-state browser))
            need-idx (#{:fill :click :assert :select :check} do)
            idx (when need-idx (match-index els match))]
        (when-not (session/runnable? session)
          (throw (ex-info "recipe: session is not running" {:status (session/status session)})))
        (session/hook! session :before-step {:step step :step-number step-number})
        (when verbose (println "recipe:" do (or match "") (when as (str "→" as))))
        (cond
          (and need-idx (nil? idx))
          {:ok false :error (str "no element matched " (pr-str match) " for :" (clojure.core/name do))
           :log log :state (b/-state browser) :history @history :session session}

          :else
          (let [executed
                (guardrail/execute
                 settings {:name (clojure.core/name do) :input step}
                 #(case do
                  :navigate (do (b/-navigate! browser (:url step)) {:do do :url (:url step)})
                  :fill (do (b/-input-text! browser idx (resolve-value value resolve-secret))
                            {:do do :index idx :secret? (boolean (and (map? value) (:secret value)))})
                  :click (do (b/-click! browser idx) {:do do :index idx})
                  :select (do (select idx (resolve-value value resolve-secret))
                              {:do do :index idx :value value})
                  :check (do (check idx) {:do do :index idx})
                  :assert {:do do :index idx :ok true}
                  :screenshot {:do do :as as :path (screenshot as)}
                  :wait-human {:do do :prompt prompt :resumed (boolean (pause prompt))}
                  :captcha (let [captcha-opts (merge (:captcha settings)
                                                     (:captcha step)
                                                     {:session session
                                                      :human-handler
                                                      (or (get-in step [:captcha :human-handler])
                                                          (fn [challenge]
                                                            (pause (or prompt
                                                                       (str "Solve " (:type challenge)
                                                                            " CAPTCHA, then continue")))))})
                                 challenge (or (:challenge step) (captcha/detect (b/-state browser)))
                                 solved (when challenge (captcha/solve! challenge captcha-opts))]
                             {:do do :detected? (boolean challenge)
                              :result (when solved (captcha/audit-result solved))})
                  (throw (ex-info (str "recipe: unknown :do " (pr-str do)) {:step step}))))
                result (:value executed)
                _ (guardrail/assert-url! settings (:url (b/-state browser)))
                audit-step (if (= :captcha do)
                             (cond-> (dissoc step :captcha :challenge)
                               (:captcha step)
                               (assoc :captcha (captcha/public-settings (:captcha step)))
                               (:challenge step)
                               (assoc :challenge
                                      (select-keys (:challenge step)
                                                   [:id :type :url :element-index :evidence])))
                             (dissoc step :value))
                action-result (history/->ActionResult
                               step-number (clojure.core/name do)
                               (guardrail/redact audit-step (:sensitive-data settings))
                               (guardrail/redact result (:sensitive-data settings))
                               nil (:url (b/-state browser)) (:attempts executed)
                               (:elapsed-ms executed) {:recipe? true})]
            (swap! history history/append action-result)
            (session/hook! session :after-step action-result)
            (recur (rest remaining) (conj log result) (inc step-number)))))))))

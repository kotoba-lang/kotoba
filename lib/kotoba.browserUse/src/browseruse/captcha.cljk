(ns browseruse.captcha
  "Portable CAPTCHA orchestration. Detection, operator hand-off and external
  solving are deliberately separate. Provider credentials belong inside the
  adapter implementation and must never be passed in challenge/options maps."
  (:require [kotoba.lang.text :as str]
            [browseruse.session :as session]))

(defprotocol CaptchaProvider
  (-submit! [provider challenge opts] "Submit a public challenge; returns a job map.")
  (-poll! [provider job opts] "Return {:status :pending|:solved|:failed ...}.")
  (-cancel! [provider job opts] "Best-effort cancellation."))

(def defaults
  {:mode :human :timeout-ms 120000 :poll-interval-ms 1000 :max-polls 120
   :detect? true})

(defn policy [opts]
  (let [p (merge defaults (or opts {}))]
    (when-not (#{:human :external :disabled} (:mode p))
      (throw (ex-info "browser-use: invalid CAPTCHA mode" {:type :captcha/invalid-policy})))
    (doseq [k [:timeout-ms :poll-interval-ms :max-polls]]
      (when-not (pos? (get p k))
        (throw (ex-info "browser-use: CAPTCHA bounds must be positive"
                        {:type :captcha/invalid-policy :key k}))))
    p))

(defn public-settings
  "Serializable policy for history/audit. Runtime handlers and providers are
  excluded because they may close over credentials."
  [opts]
  (select-keys (policy opts)
               [:mode :timeout-ms :poll-interval-ms :max-polls :detect?]))

(defn- evidence-for [{:keys [tag text attrs]}]
  (let [haystack (str/lower
                  (str tag " " text " " (:id attrs) " " (:name attrs) " "
                       (:title attrs) " " (:src attrs) " " (:class attrs)))]
    (cond
      (re-find #"hcaptcha|h-captcha" haystack) :hcaptcha
      (re-find #"recaptcha|g-recaptcha" haystack) :recaptcha
      (re-find #"turnstile|cf-chl|challenge-platform" haystack) :turnstile
      (re-find #"captcha" haystack) :generic
      :else nil)))

(defn detect
  "Detect a likely challenge from portable browser state. Returns public
  metadata only; page contents, cookies and credentials are not copied."
  [{:keys [url elements]}]
  (when-let [[element kind] (some (fn [el] (when-let [k (evidence-for el)] [el k])) elements)]
    {:id (str "captcha-" (or (:index element) "unindexed"))
     :type kind :url url :element-index (:index element)
     :site-key (or (get-in element [:attrs :data-sitekey])
                   (get-in element [:attrs "data-sitekey"]))
     :evidence :dom-indicator}))

(defn audit-result
  "Remove solver tokens/provider payloads before hooks, logs or history."
  [result]
  (-> result
      (dissoc :solution :token :provider-response :job)
      (update :challenge #(select-keys % [:id :type :url :element-index :evidence]))))

(defn- elapsed-ms [started now-fn] (- (now-fn) started))

(defn solve!
  "Resolve challenge according to policy.

  Runtime opts:
    :session       AgentSession used for pause/resume and audit hooks
    :human-handler blocking operator callback; truthy means completed
    :provider      CaptchaProvider (credentials remain encapsulated in it)
    :apply-solution callback that consumes the private solution
    :sleep-fn/:now-fn injectable portable timing functions

  Polling is bounded by both :max-polls and :timeout-ms."
  [challenge opts]
  (let [{:keys [mode timeout-ms poll-interval-ms max-polls provider session
                human-handler apply-solution sleep-fn now-fn]
         :or {sleep-fn #?(:clj (fn [ms] (Thread/sleep ms)) :cljs (fn [_] nil))
              now-fn #?(:clj #(System/currentTimeMillis) :cljs #(.now js/Date))}}
        (merge (policy opts) opts)
        emit! (fn [hook payload]
                (when session (session/hook! session hook (audit-result payload))))]
    (emit! :captcha-detected {:status :detected :challenge challenge})
    (case mode
      :disabled {:status :skipped :challenge challenge}
      :human
      (do
        (when-not human-handler
          (throw (ex-info "browser-use: CAPTCHA requires a human handler"
                          {:type :captcha/human-handler-required})))
        (when session (session/pause! session))
        (try
          (if (human-handler (select-keys challenge [:id :type :url :element-index :evidence]))
            (do (when session (session/resume! session))
                (let [r {:status :solved :method :human :challenge challenge}]
                  (emit! :captcha-resolved r) r))
            (let [r {:status :pending-human :method :human :challenge challenge}]
              (emit! :captcha-pending r) r))
          (catch #?(:clj Exception :cljs :default) e
            (emit! :captcha-failed {:status :failed :method :human :challenge challenge})
            (throw e))))
      :external
      (do
        (when-not (satisfies? CaptchaProvider provider)
          (throw (ex-info "browser-use: external CAPTCHA provider required"
                          {:type :captcha/provider-required})))
        (let [started (now-fn)
              provider-opts (select-keys (policy opts)
                                         [:timeout-ms :poll-interval-ms :max-polls])
              job (-submit! provider challenge provider-opts)]
          (loop [poll 1]
            (when (or (> poll max-polls) (>= (elapsed-ms started now-fn) timeout-ms))
              (-cancel! provider job provider-opts)
              (throw (ex-info "browser-use: CAPTCHA solver timed out"
                              {:type :captcha/timeout :polls (dec poll)})))
            (let [{:keys [status solution]} (-poll! provider job provider-opts)]
              (case status
                :solved (do (when apply-solution (apply-solution solution challenge))
                            (let [r {:status :solved :method :external
                                     :polls poll :solution solution :challenge challenge}]
                              (emit! :captcha-resolved r) r))
                :failed (do (emit! :captcha-failed
                                   {:status :failed :method :external :challenge challenge})
                            (throw (ex-info "browser-use: CAPTCHA solver failed"
                                            {:type :captcha/provider-failed})))
                :pending (do (sleep-fn poll-interval-ms) (recur (inc poll)))
                (throw (ex-info "browser-use: invalid CAPTCHA provider status"
                                {:type :captcha/invalid-provider-status :status status}))))))))))

(defn maybe-solve!
  "Detect and solve a challenge, or return nil when none is present."
  [browser-state opts]
  (let [p (policy opts)]
    (when (and (:detect? p) (not= :disabled (:mode p)))
      (when-let [challenge (detect browser-state)]
        (solve! challenge opts)))))

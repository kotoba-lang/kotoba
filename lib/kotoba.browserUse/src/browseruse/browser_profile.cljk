(ns browseruse.browser-profile
  "Validated browser launch/profile configuration.

  `:stealth` means explicit fingerprint controls only.  It is not a promise
  that automation is undetectable and does not bypass access controls."
  (:require [kotoba.lang.text :as str]))

(def ^:private secret-keys #{:password :authorization :proxy-authorization})

(defn redact-secrets
  "Recursively replaces credential values before configs enter logs/history."
  [x]
  (cond
    (map? x) (into {} (map (fn [[k v]] [k (if (secret-keys k) "[REDACTED]"
                                                 (redact-secrets v))])) x)
    (vector? x) (mapv redact-secrets x)
    (sequential? x) (map redact-secrets x)
    :else x))

(defn validate-profile
  [opts]
  (let [{:keys [proxy cdp-url user-data-dir init-scripts]} opts]
    (when (and cdp-url user-data-dir)
      (throw (ex-info ":cdp-url and :user-data-dir are mutually exclusive"
                      {:type :invalid-browser-profile})))
    (when (and proxy (str/blank? (:server proxy)))
      (throw (ex-info "Proxy :server must be non-blank"
                      {:type :invalid-browser-profile :field [:proxy :server]})))
    (when (and (or (:username proxy) (:password proxy))
               (not (and (:username proxy) (:password proxy))))
      (throw (ex-info "Proxy authentication requires both username and password"
                      {:type :invalid-browser-profile :field :proxy-auth})))
    (when-not (every? #(or (string? %) (and (map? %) (or (:content %) (:path %))))
                      (or init-scripts []))
      (throw (ex-info "Init scripts must be strings or {:content ...}/{:path ...}"
                      {:type :invalid-browser-profile :field :init-scripts})))
    opts))

(defn capability-report
  "Machine-readable, credential-free statement of effective host features."
  [opts]
  (let [opts (validate-profile opts)]
    {:provider :playwright-jvm
     :connection-mode (cond (:cdp-url opts) :cdp
                            (:user-data-dir opts) :persistent-profile
                            :else :isolated)
     :proxy {:configured? (boolean (:proxy opts))
             :authenticated? (boolean (get-in opts [:proxy :username]))
             :bypass-configured? (boolean (get-in opts [:proxy :bypass]))}
     :fingerprint {:configured (->> [:viewport :screen :user-agent :locale :timezone-id
                                     :geolocation :color-scheme :device-scale-factor
                                     :has-touch? :mobile? :extra-http-headers]
                                    (filter #(contains? opts %)) vec)
                   :init-scripts? (boolean (seq (:init-scripts opts)))}
     :stealth {:level :configuration-hardening
               :automation-undetectable? false
               :captcha-bypass? false
               :note "Fingerprint controls reduce accidental inconsistencies; they do not guarantee evasion."}
     :effective-config (cond->
                        (redact-secrets
                         (select-keys opts [:headless? :channel :executable-path
                                            :user-data-dir :proxy :viewport :screen :user-agent
                                            :locale :timezone-id :geolocation :color-scheme]))
                         (:cdp-url opts) (assoc :cdp-url "[CONFIGURED]"))}))

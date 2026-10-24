(ns macos-inventory.core
  "Vocabularies and parsers for macOS system inventory. Pure — no IO.

  Everything this library can *say* about a machine is named here, and every
  format it has to read is parsed here, so the parsers are testable against
  captured fixtures instead of against whatever the host happens to be running.

  The parsers are the interesting part: `lsof`, `profiles`, `systemextensionsctl`
  and `kmutil` all emit shapes that are easy to almost-parse. A signature verdict
  derived from a misread line is worse than no verdict, because it is reported
  with the same confidence as a correct one."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; vocabularies
;; ---------------------------------------------------------------------------

(def persistence-classes
  "Ways something arranges to run again without being asked. `:scope` says whose
  authority it runs with; `:removable?` says whether removing the registering
  file actually disables it (a configuration profile does not work that way)."
  {:launch-agent-user   {:label "User LaunchAgent"      :scope :user   :removable? true}
   :launch-agent-global {:label "Global LaunchAgent"    :scope :system :removable? true}
   :launch-daemon       {:label "LaunchDaemon (root)"   :scope :system :removable? true}
   :login-item          {:label "Login item"            :scope :user   :removable? false}
   :config-profile      {:label "Configuration profile" :scope :system :removable? false}
   :cron                {:label "cron job"              :scope :user   :removable? false}
   :periodic            {:label "periodic script"       :scope :system :removable? true}
   :browser-extension   {:label "Browser extension"     :scope :user   :removable? true}
   :kernel-extension    {:label "Kernel extension"      :scope :system :removable? false}
   :system-extension    {:label "System extension"      :scope :system :removable? false}})

(def signature-states
  {:notarized    {:label "Notarized"                    :trusted? true}
   :apple-signed {:label "Signed by Apple"              :trusted? true}
   :dev-signed   {:label "Developer ID signed"          :trusted? true}
   :adhoc        {:label "Ad-hoc signed"                :trusted? false}
   :unsigned     {:label "Unsigned"                     :trusted? false}
   :broken       {:label "Signature does not verify"    :trusted? false}
   :revoked      {:label "Certificate revoked"          :trusted? false}
   :unknown      {:label "Signature could not be verified" :trusted? nil}})

(def tcc-service->class
  "TCC service identifiers to a readable class. The four marked high-impact live
  only in the *system* database, which needs Full Disk Access to read — a probe
  that reads only the user database omits exactly these."
  {"kTCCServiceSystemPolicyAllFiles"      :full-disk-access
   "kTCCServiceScreenCapture"             :screen-recording
   "kTCCServiceAccessibility"             :accessibility
   "kTCCServiceListenEvent"               :input-monitoring
   "kTCCServicePostEvent"                 :input-monitoring
   "kTCCServiceCamera"                    :camera
   "kTCCServiceMicrophone"                :microphone
   "kTCCServiceAddressBook"               :contacts
   "kTCCServiceCalendar"                  :calendar
   "kTCCServiceReminders"                 :reminders
   "kTCCServicePhotos"                    :photos
   "kTCCServiceDeveloperTool"             :developer-tools
   "kTCCServiceSystemPolicyDesktopFolder" :desktop-folder
   "kTCCServiceSystemPolicyDocumentsFolder" :documents-folder
   "kTCCServiceSystemPolicyDownloadsFolder" :downloads-folder
   "kTCCServiceSystemPolicyRemovableVolume" :removable-volumes
   "kTCCServiceLocation"                  :location})

(def high-impact-grants
  "Grants that give effectively unlimited observation of the user."
  #{:full-disk-access :screen-recording :accessibility :input-monitoring})

(def ^:const tcc-granted-auth-values
  "auth_value 2 = allowed, 3 = limited. 0 and 1 are denied/unknown."
  #{"2" "3"})

;; ---------------------------------------------------------------------------
;; codesign / spctl
;; ---------------------------------------------------------------------------

(defn parse-codesign
  "`codesign -dv --verbose=4` writes its whole report to **stderr** and exits 0.
  Reading only stdout yields nothing and every verdict becomes :unknown, which is
  how a fleet of properly signed daemons gets reported as unverifiable.

  `notarized?` is the result of a separate spctl call; Developer ID says who
  signed a thing, only spctl says Apple notarized it."
  [{:keys [stderr exit notarized?]}]
  (let [t (str/lower (or stderr ""))]
    (cond
      (str/includes? t "not signed at all") :unsigned
      (str/includes? t "invalid signature") :broken
      (str/includes? t "revoked") :revoked
      (and (some? exit) (not (zero? exit)))
      (if (str/includes? t "no such file") :unknown :broken)
      (str/includes? t "signature=adhoc") :adhoc
      (or (str/includes? t "authority=software signing")
          (str/includes? t "authority=apple code signing")) :apple-signed
      (str/includes? t "authority=developer id application")
      (if notarized? :notarized :dev-signed)
      :else :unknown)))

(defn parse-spctl-notarized? [{:keys [stdout stderr]}]
  (let [t (str/lower (str stdout " " stderr))]
    (boolean (and (str/includes? t "accepted") (str/includes? t "notarized")))))

(defn parse-gatekeeper [{:keys [stdout]}]
  (let [t (str/lower (or stdout ""))]
    (cond
      (str/includes? t "assessments enabled") :enabled
      (str/includes? t "assessments disabled") :disabled
      :else :unknown)))

;; ---------------------------------------------------------------------------
;; lsof
;; ---------------------------------------------------------------------------

(defn parse-lsof
  "`lsof -F pcn` emits a pid line, then a command line, then one name line per
  socket. Returns {pid {:command c :ports #{...}}}.

  The command name is truncated by lsof and cannot be code-signed — the caller
  has to resolve the pid to a real executable path before any signature question
  is meaningful."
  [out]
  (:acc
   (reduce (fn [{:keys [pid acc]} line]
             (cond
               (str/starts-with? line "p") {:pid (subs line 1) :acc acc}
               (str/starts-with? line "c") {:pid pid :acc (assoc-in acc [pid :command] (subs line 1))}
               (str/starts-with? line "n")
               {:pid pid
                :acc (update-in acc [pid :ports] (fnil conj #{})
                                (last (str/split (subs line 1) #":")))}
               :else {:pid pid :acc acc}))
           {:pid nil :acc {}}
           (remove str/blank? (str/split-lines (or out ""))))))

;; ---------------------------------------------------------------------------
;; TCC rows
;; ---------------------------------------------------------------------------

(defn parse-tcc-rows
  "sqlite3 pipe-separated `service|client|auth_value` rows -> granted rows only."
  [out]
  (->> (str/split-lines (or out ""))
       (remove str/blank?)
       (map #(str/split % #"\|"))
       (filter #(= 3 (count %)))
       (filter (fn [[_ _ auth]] (contains? tcc-granted-auth-values auth)))
       vec))

(defn tcc-by-client
  "Granted rows -> {client #{grant-class ...}}. Rows from several databases are
  merged, so a client holding grants in both appears once with the union."
  [rows]
  (reduce (fn [acc [service client _]]
            (if-let [c (tcc-service->class service)]
              (update acc client (fnil conj #{}) c)
              acc))
          {}
          rows))

;; ---------------------------------------------------------------------------
;; configuration profiles
;; ---------------------------------------------------------------------------

(defn parse-profiles
  "`profiles -L -o stdout-xml` converted to JSON gives a map of domain ->
  vector of profile maps. Flatten to a seq of {:identifier :display-name
  :organization :removable?}.

  Accepts the already-parsed data because the plist->JSON conversion is IO."
  [data]
  (into []
        (comp (mapcat val)
              (keep (fn [p]
                      (when (map? p)
                        {:identifier (or (get p "ProfileIdentifier") (get p "ProfileUUID"))
                         :display-name (get p "ProfileDisplayName")
                         :organization (get p "ProfileOrganization")
                         :install-date (get p "ProfileInstallDate")
                         ;; A profile the user cannot remove is a different kind
                         ;; of fact from one they can.
                         :removable? (not= "never" (get p "ProfileRemovalDisallowed"))}))))
        (if (map? data) data {})))

;; ---------------------------------------------------------------------------
;; system extensions / kexts
;; ---------------------------------------------------------------------------

(defn parse-system-extensions
  "`systemextensionsctl list` output. Rows look like:

    --- com.apple.system_extension.network_extension
    enabled\\tactive\\tteamID\\tbundleID (version)\\tname [state]

  The header lines and the trailing `[activated enabled]` state are both easy to
  mistake for a record, so anchor on the bundle-id-with-version column."
  [out]
  (into []
        (keep (fn [line]
                (let [l (str/trim line)]
                  (when-not (or (str/blank? l)
                                (str/starts-with? l "---")
                                (str/starts-with? l "enabled")
                                (str/includes? l "extension(s)"))
                    (let [cols (str/split l #"\t+")
                          bundle-col (first (filter #(re-find #"\(.+\)" %) cols))]
                      (when bundle-col
                        {:bundle-id (str/trim (first (str/split bundle-col #"\(")))
                         :version (second (re-find #"\((.+?)\)" bundle-col))
                         :team-id (first (filter #(re-matches #"[A-Z0-9]{10}" (str/trim %)) cols))
                         :enabled? (boolean (re-find #"(?i)\benabled\b" l))
                         :state (second (re-find #"\[(.+?)\]" l))}))))))
        (str/split-lines (or out ""))))

(defn parse-kext-list
  "`kmutil showloaded --no-kernel-components` columns:
  Index Refs Address Size Wired Name (Version) UUID <Linked Against>

  Apple's own kexts are the overwhelming majority; a third-party one is the
  finding, so the bundle id prefix matters more than the row shape."
  [out]
  (into []
        (keep (fn [line]
                (let [l (str/trim line)]
                  (when-let [[_ name version]
                             (re-find #"([A-Za-z0-9_.\-]+\.[A-Za-z0-9_.\-]+)\s+\(([^)]+)\)" l)]
                    (when-not (str/starts-with? l "Index")
                      {:bundle-id name
                       :version version
                       :apple? (or (str/starts-with? name "com.apple.")
                                   (str/starts-with? name "__kernel__"))})))))
        (str/split-lines (or out ""))))

;; ---------------------------------------------------------------------------
;; browser extensions
;; ---------------------------------------------------------------------------

(def ^:private risky-permission-patterns
  "Extension permissions that grant broad observation. `<all_urls>` and
  host-wildcards mean the extension sees every page, which is the browser
  equivalent of Full Disk Access."
  [#"^<all_urls>$" #"^\*://\*/" #"^https?://\*/" #"^webRequest" #"^cookies$"
   #"^history$" #"^debugger$" #"^nativeMessaging$" #"^proxy$" #"^tabs$"
   #"^clipboardRead$" #"^desktopCapture$" #"^management$"])

(defn risky-permissions
  "Which of an extension's requested permissions grant broad observation."
  [permissions]
  (into []
        (filter (fn [p] (some #(re-find % (str p)) risky-permission-patterns)))
        (or permissions [])))

(defn parse-chromium-manifest
  "A Chromium extension manifest.json (already parsed) -> a record. Handles both
  manifest v2 (`permissions` mixes hosts and APIs) and v3 (`host_permissions`
  split out)."
  [{:strs [name version permissions host_permissions manifest_version] :as m}]
  (when (map? m)
    (let [perms (vec (concat (or permissions []) (or host_permissions [])))]
      {:name (if (string? name) name "(unnamed)")
       :version version
       :manifest-version (or manifest_version 2)
       :permissions perms
       :risky-permissions (risky-permissions perms)})))

;; ---------------------------------------------------------------------------
;; coverage
;; ---------------------------------------------------------------------------

(def coverage-statuses
  "Higher wins when sources disagree. A denial is the loudest thing an inventory
  can say and must never be masked by a success elsewhere."
  {:complete 0 :not-attempted 1 :partial 2 :denied 3})

(defn combine-status [statuses]
  (let [s (set (remove nil? statuses))]
    (cond
      (empty? s) :not-attempted
      (contains? s :denied) :denied
      (contains? s :partial) :partial
      (and (contains? s :complete) (contains? s :not-attempted)) :partial
      (contains? s :complete) :complete
      :else :not-attempted)))

(defn add-coverage [coverage surface status detail]
  (update coverage surface
          (fn [prev]
            {:status (combine-status [(:status prev) status])
             :detail (->> [(:detail prev) detail]
                          (remove #(or (nil? %) (= "" %)))
                          distinct
                          (str/join "; "))})))

(defn merge-coverage [& maps]
  (reduce (fn [acc m]
            (reduce-kv (fn [a k {:keys [status detail]}] (add-coverage a k status detail))
                       acc m))
          {}
          (remove nil? maps)))

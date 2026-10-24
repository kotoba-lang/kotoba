(ns macos-inventory.host
  "The probes. nbb. Read-only throughout.

  Two rules hold everywhere here:

  1. **No probe may trigger an authorisation or consent dialog.** A tool that
     fires prompts as it starts teaches the user to click through them. Measured:
     `sfltool dumpbtm` requests `system.privilege.admin` and pops an auth sheet,
     so it is not used at all — login items are read best-effort from the
     BackgroundTaskManagement store instead and reported as `:partial`.
  2. **A probe that cannot see reports that it could not see.** Never an empty
     result that reads as a clean machine."
  (:require ["node:child_process" :as cp]
            ["node:fs" :as fs]
            ["node:os" :as os]
            ["node:path" :as path]
            [kotoba.lang.text :as str]
            [macos-inventory.core :as c]))

;; ---------------------------------------------------------------------------
;; process / fs helpers
;; ---------------------------------------------------------------------------

(defn sh
  "Run a command without a shell. Returns {:ok? :out :err :code}.

  spawnSync, not execFileSync: execFileSync only exposes stderr on the error
  object, so a *successful* command's stderr is lost. `codesign -dv` writes its
  entire report to stderr and exits 0 — with execFileSync every signature verdict
  came back :unknown."
  [cmd args & [{:keys [timeout-ms]}]]
  (try
    (let [r (cp/spawnSync cmd (clj->js (vec args))
                          #js {:encoding "utf8" :timeout (or timeout-ms 10000)})
          code (.-status r)]
      {:ok? (= 0 code)
       :out (str (or (.-stdout r) ""))
       :err (str (or (.-stderr r) (some-> (.-error r) .-message) ""))
       :code (or code 1)})
    (catch :default e {:ok? false :out "" :err (str (.-message e)) :code 1})))

(defn home [] (os/homedir))

(defn expand [p]
  (if (str/starts-with? p "~") (path/join (home) (subs p 1)) p))

(defn exists? [p] (try (do (fs/lstatSync p) true) (catch :default _ false)))
(defn lstat [p] (try (fs/lstatSync p) (catch :default _ nil)))
(defn real-path [p] (try (fs/realpathSync p) (catch :default _ p)))
(defn- readdir [p] (array-seq (try (fs/readdirSync p) (catch :default _ #js []))))

(defn read-plist
  "Parse a plist to Clojure data via plutil. nil when unreadable — several Apple
  stores are NSKeyedArchiver blobs that have no JSON representation."
  [p]
  (let [{:keys [ok? out]} (sh "/usr/bin/plutil" ["-convert" "json" "-o" "-" p]
                              {:timeout-ms 8000})]
    (when ok?
      (try (js->clj (js/JSON.parse out) :keywordize-keys false) (catch :default _ nil)))))

;; ---------------------------------------------------------------------------
;; signatures
;; ---------------------------------------------------------------------------

(defn signature
  "Signing verdict for an executable path, as a core/signature-states key."
  [p]
  (if-not (and p (exists? p))
    :unknown
    (let [cs (sh "/usr/bin/codesign" ["-dv" "--verbose=4" p] {:timeout-ms 8000})
          dev-id? (str/includes? (str/lower (:err cs)) "authority=developer id application")
          notarized? (when dev-id?
                       (c/parse-spctl-notarized?
                        (let [r (sh "/usr/sbin/spctl" ["-a" "-vv" "-t" "exec" p]
                                    {:timeout-ms 15000})]
                          {:stdout (:out r) :stderr (:err r)})))]
      (c/parse-codesign {:stderr (:err cs) :exit (:code cs) :notarized? notarized?}))))

(defn quarantined? [p]
  (:ok? (sh "/usr/bin/xattr" ["-p" "com.apple.quarantine" p] {:timeout-ms 5000})))

(defn gatekeeper []
  (let [r (sh "/usr/sbin/spctl" ["--status"] {:timeout-ms 8000})]
    {:status (c/parse-gatekeeper {:stdout (str (:out r) (:err r))})}))

(defn xprotect-version
  "XProtect's signature bundle version — the answer to 'is Apple's own malware
  blocklist current', which matters more than any list this library ships."
  []
  (let [candidates ["/Library/Apple/System/Library/CoreServices/XProtect.bundle/Contents/Info.plist"
                    "/System/Library/CoreServices/XProtect.bundle/Contents/Info.plist"]]
    (if-let [hit (first (filter exists? candidates))]
      {:version (get (read-plist hit) "CFBundleShortVersionString")
       :path hit}
      {:version nil :path nil})))

;; ---------------------------------------------------------------------------
;; launchd
;; ---------------------------------------------------------------------------

(def launch-dirs
  [{:dir "~/Library/LaunchAgents" :class :launch-agent-user   :surface :launch-agents}
   {:dir "/Library/LaunchAgents"  :class :launch-agent-global :surface :launch-agents}
   {:dir "/Library/LaunchDaemons" :class :launch-daemon       :surface :launch-daemons}])

(defn- plist-program [plist]
  (or (get plist "Program") (first (get plist "ProgramArguments"))))

(defn launchd
  "One record per launchd job. `:signatures? false` skips codesign, which
  dominates the runtime."
  [{:keys [signatures?] :or {signatures? true}}]
  (let [cov (atom {})]
    {:items
     (into []
           (mapcat
            (fn [{:keys [dir class surface]}]
              (let [d (expand dir)]
                (if-not (exists? d)
                  (do (swap! cov c/add-coverage surface :not-attempted (str d " does not exist")) [])
                  (let [names (filter #(str/ends-with? % ".plist") (readdir d))
                        out (into []
                                  (keep (fn [n]
                                          (let [p (path/join d n)
                                                plist (read-plist p)
                                                prog (plist-program plist)
                                                st (lstat p)]
                                            ;; A plist with no Program and no
                                            ;; ProgramArguments runs nothing.
                                            ;; Uninstallers leave such stubs
                                            ;; behind; scoring them as unsigned
                                            ;; root daemons is how a security
                                            ;; tool teaches people to ignore it.
                                            (when (and plist prog)
                                              {:path p
                                               :real-path (real-path p)
                                               :bytes (if st (.-size st) 0)
                                               :mtime-ms (if st (.getTime (.-mtime st)) 0)
                                               :surface surface
                                               :persistence class
                                               :label (get plist "Label")
                                               :program prog
                                               :run-at-load? (boolean (get plist "RunAtLoad"))
                                               :keep-alive? (boolean (get plist "KeepAlive"))
                                               :quarantine? (quarantined? p)
                                               :signature (if signatures? (signature prog) :unknown)})))
                                        names))]
                    (swap! cov c/add-coverage surface
                           (if signatures? :complete :partial)
                           (str (count out) " jobs in " d
                                (when-not signatures? " (signatures not checked)")))
                    out))))
            launch-dirs))
     :coverage @cov}))

;; ---------------------------------------------------------------------------
;; login items — best effort, never prompting
;; ---------------------------------------------------------------------------

(def btm-store
  "~/Library/Application Support/com.apple.backgroundtaskmanagementagent/backgrounditems.btm")

(defn login-items
  "Login items / background items.

  Deliberately does NOT call `sfltool dumpbtm`: measured on macOS 26, it requests
  `system.privilege.admin` and raises an authorisation sheet. The
  BackgroundTaskManagement store is an NSKeyedArchiver blob with no JSON
  representation, so this extracts bundle-identifier-shaped strings from its XML
  form — enough to enumerate *what* is registered, not enough to be authoritative
  about state. Reported as `:partial` for that reason."
  []
  (let [p (expand btm-store)]
    (cond
      (not (exists? p))
      {:items [] :coverage {:login-items {:status :not-attempted
                                          :detail "no BackgroundTaskManagement store"}}}
      :else
      (let [{:keys [ok? out err]} (sh "/usr/bin/plutil" ["-convert" "xml1" "-o" "-" p]
                                      {:timeout-ms 8000})]
        (if-not ok?
          {:items []
           :coverage {:login-items
                      {:status :denied
                       :detail (str "BackgroundTaskManagement store unreadable — grant Full Disk "
                                    "Access to enumerate login items ("
                                    (first (str/split-lines (str/trim err))) ")")}}}
          (let [ids (->> (re-seq #"<string>([A-Za-z0-9][A-Za-z0-9\-]*(?:\.[A-Za-z0-9\-]+){2,})</string>" out)
                         (map second)
                         (remove #(str/ends-with? % ".plist"))
                         distinct
                         sort
                         vec)]
            {:items (mapv (fn [id] {:bundle-id id :persistence :login-item :surface :login-items}) ids)
             :coverage
             {:login-items
              ;; Zero extracted identifiers does NOT mean zero login items. The
              ;; store is an NSKeyedArchiver blob and on this machine its
              ;; identifiers sit inside base64 <data> elements, not <string>
              ;; ones — so the honest report is "could not read", not "none".
              (if (empty? ids)
                {:status :denied
                 :detail (str "BackgroundTaskManagement store is a keyed archive whose "
                              "identifiers are inside base64 <data> blobs — none could be "
                              "extracted, which is NOT the same as none being registered. "
                              "Enumerating them needs sfltool, which raises an admin prompt "
                              "and is deliberately not called.")}
                {:status :partial
                 :detail (str (count ids) " background items named in the BTM store "
                              "(identifiers only — enable/disable state needs sfltool, "
                              "which raises an admin prompt and is not called)")})}}))))))

;; ---------------------------------------------------------------------------
;; configuration profiles
;; ---------------------------------------------------------------------------

(defn config-profiles []
  (let [r (sh "/usr/bin/profiles" ["-L" "-o" "stdout-xml"] {:timeout-ms 15000})]
    (if-not (:ok? r)
      {:items [] :coverage {:config-profiles {:status :denied :detail (str/trim (:err r))}}}
      (let [tmp (path/join (os/tmpdir) "macos-inventory-profiles.plist")
            _ (fs/writeFileSync tmp (:out r) "utf8")
            data (read-plist tmp)
            items (mapv #(assoc % :persistence :config-profile :surface :config-profiles)
                        (c/parse-profiles data))]
        (try (fs/rmSync tmp) (catch :default _ nil))
        {:items items
         :coverage {:config-profiles
                    {:status :complete
                     :detail (str (count items) " configuration profile(s) installed")}}}))))

;; ---------------------------------------------------------------------------
;; system extensions / kexts
;; ---------------------------------------------------------------------------

(defn system-extensions []
  (let [r (sh "/usr/bin/systemextensionsctl" ["list"] {:timeout-ms 15000})]
    (if-not (:ok? r)
      {:items [] :coverage {:system-extensions {:status :denied :detail (str/trim (:err r))}}}
      (let [items (mapv #(assoc % :persistence :system-extension :surface :system-extensions)
                        (c/parse-system-extensions (:out r)))]
        {:items items
         :coverage {:system-extensions
                    {:status :complete :detail (str (count items) " system extension(s)")}}}))))

(defn kexts
  "Loaded kernel extensions, third-party only. Apple's own are the overwhelming
  majority and are not the finding."
  []
  (let [r (sh "/usr/bin/kmutil" ["showloaded" "--no-kernel-components"] {:timeout-ms 30000})]
    (if-not (:ok? r)
      {:items [] :coverage {:kexts {:status :denied :detail (str/trim (:err r))}}}
      (let [all (c/parse-kext-list (:out r))
            third-party (remove :apple? all)
            items (mapv #(assoc % :persistence :kernel-extension :surface :kexts) third-party)]
        {:items items
         :coverage {:kexts
                    {:status :complete
                     :detail (str (count items) " third-party of " (count all) " loaded kexts")}}}))))

;; ---------------------------------------------------------------------------
;; browser extensions
;; ---------------------------------------------------------------------------

(def chromium-profiles
  [{:browser "Chrome"  :root "~/Library/Application Support/Google/Chrome"}
   {:browser "Brave"   :root "~/Library/Application Support/BraveSoftware/Brave-Browser"}
   {:browser "Edge"    :root "~/Library/Application Support/Microsoft Edge"}
   {:browser "Arc"     :root "~/Library/Application Support/Arc/User Data"}
   {:browser "Vivaldi" :root "~/Library/Application Support/Vivaldi"}
   {:browser "Chromium" :root "~/Library/Application Support/Chromium"}])

(defn- chromium-extensions [browser root]
  (into []
        (mapcat
         (fn [prof]
           (let [ext-dir (path/join root prof "Extensions")]
             (when (exists? ext-dir)
               (for [id (readdir ext-dir)
                     :when (not= id "Temp")
                     :let [vdirs (readdir (path/join ext-dir id))
                           vdir (last (sort vdirs))
                           mpath (when vdir (path/join ext-dir id vdir "manifest.json"))
                           m (when (and mpath (exists? mpath))
                               (try (js->clj (js/JSON.parse (fs/readFileSync mpath "utf8")))
                                    (catch :default _ nil)))
                           parsed (when m (c/parse-chromium-manifest m))]
                     :when parsed]
                 (assoc parsed
                        :browser browser
                        :profile prof
                        :extension-id id
                        :path (path/join ext-dir id)
                        :persistence :browser-extension
                        :surface :browser-extensions))))))
        (filter #(exists? (path/join root % "Extensions")) (readdir root))))

(defn browser-extensions
  "Installed Chromium-family extensions with their requested permissions.

  Safari extensions are app-bundled and enumerating them needs a different route,
  so they are reported as not attempted rather than counted as none."
  []
  (let [cov (atom {})
        items (into []
                    (mapcat (fn [{:keys [browser root]}]
                              (let [r (expand root)]
                                (if-not (exists? r)
                                  []
                                  (let [ex (chromium-extensions browser r)]
                                    (swap! cov c/add-coverage :browser-extensions :complete
                                           (str (count ex) " in " browser))
                                    ex)))))
                    chromium-profiles)]
    (when (empty? @cov)
      (swap! cov c/add-coverage :browser-extensions :not-attempted
             "no Chromium-family browser profiles found"))
    (swap! cov c/add-coverage :browser-extensions :partial
           "Safari extensions are app-bundled and are not enumerated")
    {:items items :coverage @cov}))

;; ---------------------------------------------------------------------------
;; TCC privacy grants
;; ---------------------------------------------------------------------------

(def tcc-databases
  "TCC is split across two databases and the **system** one holds the grants that
  matter most: Full Disk Access, Screen Recording, Accessibility and Input
  Monitoring live only there. Reading just the user database reports `:complete`
  while omitting every high-impact grant."
  [{:path "~/Library/Application Support/com.apple.TCC/TCC.db" :scope :user}
   {:path "/Library/Application Support/com.apple.TCC/TCC.db" :scope :system}])

(defn- read-tcc [{:keys [path scope]}]
  (let [db (expand path)]
    (if-not (exists? db)
      {:rows [] :status :not-attempted :detail (str (name scope) " TCC.db absent")}
      (let [{:keys [ok? out err]}
            (sh "/usr/bin/sqlite3" ["-readonly" db "select service, client, auth_value from access;"]
                {:timeout-ms 10000})]
        (if-not ok?
          {:rows [] :status :denied
           :detail (str (name scope) " TCC.db unreadable — grant Full Disk Access to include "
                        (name scope) " privacy grants ("
                        (first (str/split-lines (str/trim err))) ")")}
          {:rows (c/parse-tcc-rows out) :status :complete
           :detail (str (count (c/parse-tcc-rows out)) " grants in the " (name scope) " database")})))))

(defn tcc-grants
  "Privacy grants per client, merged across both databases."
  []
  (let [reads (mapv read-tcc tcc-databases)
        coverage (reduce (fn [c {:keys [status detail]}]
                           (c/add-coverage c :tcc-grants status detail))
                         {} reads)
        by-client (c/tcc-by-client (mapcat :rows reads))]
    {:items (mapv (fn [[client grants]]
                    {:client client
                     :bundle-id client
                     :grants (vec (sort grants))
                     :high-impact (vec (sort (filter c/high-impact-grants grants)))
                     :surface :tcc-grants})
                  by-client)
     :coverage coverage}))

;; ---------------------------------------------------------------------------
;; listening sockets
;; ---------------------------------------------------------------------------

(defn executable-path
  "Full executable path for a pid. lsof reports only a truncated command name,
  and a name cannot be code-signed."
  [pid]
  (let [{:keys [ok? out]} (sh "/bin/ps" ["-p" (str pid) "-o" "comm="] {:timeout-ms 5000})
        p (str/trim (or out ""))]
    (when (and ok? (seq p) (exists? p)) p)))

(defn listening
  "Programs holding a listening TCP socket, resolved to a real executable path so
  their signature can actually be verified."
  [{:keys [signatures?] :or {signatures? true}}]
  (let [r (sh "/usr/sbin/lsof" ["-nP" "-iTCP" "-sTCP:LISTEN" "-F" "pcn"] {:timeout-ms 20000})]
    (if-not (:ok? r)
      {:items [] :coverage {:listening-ports {:status :denied :detail (str/trim (:err r))}}}
      (let [procs (c/parse-lsof (:out r))
            items (into []
                        (keep (fn [[pid {:keys [command ports]}]]
                                (when (seq ports)
                                  (let [exe (executable-path pid)]
                                    {:pid pid
                                     :command command
                                     :path (or exe command)
                                     :real-path (if exe (real-path exe) command)
                                     :resolved? (boolean exe)
                                     :ports (vec (sort ports))
                                     :surface :listening-ports
                                     :signature (if (and exe signatures?) (signature exe) :unknown)}))))
                        procs)
            resolved (count (filter :resolved? items))]
        {:items items
         :coverage {:listening-ports
                    {:status (if (= resolved (count items)) :complete :partial)
                     :detail (str resolved "/" (count items)
                                  " listening processes resolved to a signable path"
                                  (when (< resolved (count items))
                                    " (the rest are owned by other users or exited)"))}}}))))

;; ---------------------------------------------------------------------------
;; installed applications
;; ---------------------------------------------------------------------------

(def app-dirs
  ["/Applications" "/Applications/Utilities" "~/Applications"
   "/System/Applications" "/System/Applications/Utilities"])

(defn installed-apps
  "Installed applications with bundle id, name, version and provenance.

  Version and last-modified are what an update check needs; `:app-store?` and
  `:sparkle-feed` say *how* a given app expects to be updated, which is why this
  library reports them rather than trying to update anything itself."
  []
  (let [cov (atom {})
        items (into []
                    (mapcat
                     (fn [dir]
                       (let [d (expand dir)]
                         (if-not (exists? d)
                           []
                           (let [apps (into []
                                            (keep (fn [n]
                                                    (when (str/ends-with? n ".app")
                                                      (let [bundle (path/join d n)
                                                            info (read-plist (path/join bundle "Contents" "Info.plist"))
                                                            st (lstat bundle)]
                                                        (when info
                                                          {:path bundle
                                                           :name (or (get info "CFBundleName")
                                                                     (subs n 0 (- (count n) 4)))
                                                           :bundle-id (get info "CFBundleIdentifier")
                                                           :version (or (get info "CFBundleShortVersionString")
                                                                        (get info "CFBundleVersion"))
                                                           :min-system (get info "LSMinimumSystemVersion")
                                                           :sparkle-feed (get info "SUFeedURL")
                                                           :app-store? (exists? (path/join bundle "Contents" "_MASReceipt" "receipt"))
                                                           :system? (str/starts-with? d "/System")
                                                           :mtime-ms (if st (.getTime (.-mtime st)) 0)})))))
                                            (readdir d))]
                             (swap! cov c/add-coverage :installed-apps :complete
                                    (str (count apps) " in " d))
                             apps))))
                     app-dirs))]
    {:items items :coverage @cov}))

;; ---------------------------------------------------------------------------
;; everything
;; ---------------------------------------------------------------------------

(defn inventory
  "Run every probe. `:with-tcc?` and `:with-ports?` default off because they are
  the slow ones; neither prompts."
  [{:keys [signatures? with-tcc? with-ports? with-apps?]
    :or {signatures? true with-tcc? true with-ports? true with-apps? true}}]
  (let [ld (launchd {:signatures? signatures?})
        li (login-items)
        cp' (config-profiles)
        se (system-extensions)
        kx (kexts)
        be (browser-extensions)
        tcc (if with-tcc? (tcc-grants)
                {:items [] :coverage {:tcc-grants {:status :not-attempted
                                                   :detail "with-tcc? false"}}})
        ls (if with-ports? (listening {:signatures? signatures?})
               {:items [] :coverage {:listening-ports {:status :not-attempted
                                                       :detail "with-ports? false"}}})
        apps (if with-apps? (installed-apps)
                 {:items [] :coverage {:installed-apps {:status :not-attempted
                                                        :detail "with-apps? false"}}})]
    {:launchd (:items ld)
     :login-items (:items li)
     :config-profiles (:items cp')
     :system-extensions (:items se)
     :kexts (:items kx)
     :browser-extensions (:items be)
     :tcc-grants (:items tcc)
     :listening (:items ls)
     :installed-apps (:items apps)
     :gatekeeper (gatekeeper)
     :xprotect (xprotect-version)
     :coverage (apply c/merge-coverage (map :coverage [ld li cp' se kx be tcc ls apps]))}))

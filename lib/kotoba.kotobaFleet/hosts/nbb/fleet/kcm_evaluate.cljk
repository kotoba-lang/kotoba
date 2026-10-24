(ns fleet.kcm-evaluate
  "Pure and filesystem helpers for the customer-facing KCM evaluator."
  (:require ["node:child_process" :as cp]
            ["node:fs" :as fs]
            ["node:path" :as path]
            [kotoba.lang.text :as str]
            [fleet.kcm :as kcm]
            [fleet.kcm-provider :as provider]))

(def policy-format :kotoba-kcm-policy/v1)
(def report-format :kotoba-kcm-evaluation/v1)
(def pilot-share-format :kotoba-kcm-pilot-share/v1)

(defn- sensitive-source-path? [relative]
  (let [lower (str/lower relative)
        parts (str/split lower #"/")
        base (last parts)]
    (or (some #{".ssh" ".aws" ".gnupg"} parts)
        (boolean (re-matches #"\.env(?:\..+)?" base))
        (contains? #{"credentials.json" "service-account.json"
                     "id_rsa" "id_ed25519"} base)
        (boolean (re-find #"\.(?:pem|key|p12|pfx)$" base)))))

(defn- tracked-files [root]
  (let [absolute (path/resolve root)
        raw (try
              (cp/execFileSync
               "git" #js ["-c" "core.fsmonitor=false" "-C" absolute
                           "ls-files" "-z" "--cached"]
               #js {:encoding "utf8" :maxBuffer 33554432})
              (catch :default e
                (throw (ex-info "source repo must be a Git worktree; KCM will not guess an untracked file boundary"
                                {:root absolute} e))))
        relatives (->> (str/split raw #"\u0000") (remove str/blank?) sort vec)]
    (doseq [relative relatives]
      (when (sensitive-source-path? relative)
        (throw (ex-info (str "tracked source closure contains a sensitive credential path: " relative)
                        {:path relative}))))
    (mapv
     (fn [relative]
       (let [p (path/join absolute relative)
             stat (fs/lstatSync p)]
         (cond
           (.isSymbolicLink stat)
           (throw (ex-info (str "source closure contains symlink: " relative)
                           {:path relative}))
           (.isFile stat) [relative p]
           :else (throw (ex-info (str "tracked source closure contains a non-regular file: " relative)
                                 {:path relative})))))
     relatives)))

(defn source-closure
  "Hash only Git-tracked regular files. Untracked/ignored files never enter the
  transport; symlinks, special files, and credential-shaped tracked paths fail
  closed before any source bytes are copied."
  [root]
  (let [absolute (path/resolve root)]
    (when-not (and (fs/existsSync absolute) (.isDirectory (fs/statSync absolute)))
      (throw (ex-info (str "source repo is not a directory: " absolute) {})))
    (let [files (mapv (fn [[relative p]]
                        (let [stat (fs/statSync p)]
                          {:path relative :size (.-size stat)
                           :sha256 (provider/file-sha256 p)}))
                      (tracked-files absolute))
          body {:format :kotoba-source-closure/v1
                :selection :git-tracked
                :files files}]
      (when (empty? files)
        (throw (ex-info "source repo contains no regular files" {})))
      {:root absolute :body body
       :cid (str "sha256:" (kcm/sha256 body))
       :files (count files) :bytes (reduce + (map :size files))})))

(defn copy-closure! [closure destination]
  (fs/mkdirSync destination #js {:recursive true})
  (doseq [{:keys [path size sha256]} (get-in closure [:body :files])]
    (let [from (path/join (:root closure) path)
          to (path/join destination path)]
      (fs/mkdirSync (path/dirname to) #js {:recursive true})
      (fs/copyFileSync from to)
      (let [stat (fs/statSync to)
            actual (provider/file-sha256 to)]
        (when-not (and (= size (.-size stat)) (= sha256 actual))
          (throw (ex-info (str "source changed while copying closure: " path)
                          {:path path :expected sha256 :actual actual}))))))
  destination)

(defn policy-cid [policy] (str "sha256:" (kcm/sha256 policy)))

(defn discover-entrypoints [root]
  (->> (tracked-files (path/resolve root))
       (map first)
       (filter #(str/ends-with? % ".kotoba"))
       vec))

(defn auto-policy
  "Create the deliberately narrow first-pilot policy. A repo with multiple
  Kotoba entrypoints must select one explicitly; guessing would turn a green
  result into evidence about an arbitrary file."
  [root requested-entry]
  (let [entries (discover-entrypoints root)
        requested (some-> requested-entry (str/replace #"^\./" ""))
        entry (cond
                requested
                (if (some #{requested} entries)
                  requested
                  (throw (ex-info (str "--entry is not a regular .kotoba file in the repo: "
                                       requested)
                                  {:entry requested :entrypoints entries})))

                (= 1 (count entries)) (first entries)
                (empty? entries)
                (throw (ex-info "auto pilot found no .kotoba entrypoint"
                                {:entrypoints []}))
                :else
                (throw (ex-info
                        (str "auto pilot found multiple .kotoba entrypoints; choose --entry: "
                             (str/join ", " entries))
                        {:entrypoints entries})))]
    {:format policy-format
     :target-abi :wasm32-wasi
     :effects []
     :capabilities #{:code/read :build/check :build/compile}
     :checks [{:id :check :args ["check" entry] :pure? true}]
     :builds [{:id :wasm
               :args ["compile" entry "--target" "wasm32-wasi"
                      "--output" "kcm-pilot.wasm"]}]}))

(defn policy-spec [policy]
  {:machine :kotoba-capability-machine
   :kcm/identity {:definition-closure-cid "sha256:pending"
                  :compiler-cid "pending" :module-lock-cid "pending"
                  :target-abi (:target-abi policy)
                  :hostcaps-policy-cid (policy-cid policy)
                  :provider-closure-sha256 (apply str (repeat 64 "0"))
                  :runtime-sha256 (apply str (repeat 64 "0"))
                  :effects (vec (or (:effects policy) []))}
   :kcm/provider {:archive "pending" :manifest "pending"
                  :archive-sha256 (apply str (repeat 64 "0"))}
   :kcm/capabilities (set (:capabilities policy))
   :kcm/checks (:checks policy)
   :kcm/builds (vec (or (:builds policy) []))})

(defn validate-policy! [policy]
  (let [format-reasons (cond-> []
                         (not (map? policy)) (conj "policy must be an EDN map")
                         (not= policy-format (:format policy))
                         (conj (str "policy format must be " policy-format)))
        reasons (into format-reasons (kcm/validation-reasons (policy-spec policy)))]
    (when (seq reasons)
      (throw (ex-info (str "invalid KCM policy: " (str/join "; " reasons))
                      {:reasons reasons})))
    policy))

(defn complete-spec [{:keys [policy closure provider-build root tarball cache-root]}]
  (-> (policy-spec policy)
      (assoc :work-id "kcm-evaluate" :root root :tarball tarball
             :exec-backing (case (.-platform js/process)
                             "darwin" :sandbox-exec
                             "linux" :bubblewrap
                             (throw (ex-info "KCM has no verified execution backing for this OS"
                                             {:platform (.-platform js/process)})))
             :kcm/cache-root cache-root)
      (assoc :kcm/provider
             {:archive (:archive provider-build) :manifest (:manifest provider-build)
              :archive-sha256 (:archive-sha256 provider-build)})
      (assoc :kcm/identity
             {:definition-closure-cid (:cid closure)
              :compiler-cid (:compiler-cid provider-build)
              :module-lock-cid (:module-lock-cid provider-build)
              :target-abi (:target-abi policy)
              :hostcaps-policy-cid (policy-cid policy)
              :provider-closure-sha256 (:provider-closure-sha256 provider-build)
              :runtime-sha256 (:runtime-sha256 provider-build)
              :effects (vec (or (:effects policy) []))})))

(defn with-report-cid [body]
  (assoc body :report-cid (str "sha256:" (kcm/sha256 body))))

(defn evaluation-report [{:keys [policy closure provider-build result]}]
  (let [required-probes #{:read-home-ssh :read-home :read-ambient-env
                          :network-curl :network-node :write-home :write-outside}
        runs (concat (:first result) (:second result) (:builds result))
        contained? (and (empty? (get-in result [:backing :leaked]))
                        (= required-probes (set (get-in result [:backing :blocked]))))
        complete? (and (= (count (:checks policy)) (count (:first result)))
                       (= (count (:checks policy)) (count (:second result)))
                       (= (count (or (:builds policy) [])) (count (:builds result)))
                       (string? (:machine-id result)))
        accepted? (and contained? complete? (every? #(zero? (:exit %)) runs))
        body {:format report-format
              :decision (if accepted? :accepted :rejected)
              :subject {:definition-closure-cid (:cid closure)
                        :files (:files closure) :bytes (:bytes closure)}
              :policy {:cid (policy-cid policy) :target-abi (:target-abi policy)
                       :capabilities (set (:capabilities policy))
                       :effects (vec (or (:effects policy) []))}
              :machine {:id (:machine-id result) :contract kcm/contract-version}
              :provider (select-keys provider-build
                                     [:compiler-cid :module-lock-cid
                                      :provider-closure-sha256 :runtime-sha256
                                      :archive-sha256 :files :bytes])
              :containment (:backing result)
              :checks {:first (:first result) :verified (:second result)}
              :builds (:builds result)
              :cache {:misses (count (filter #(= :miss (:cache %)) (:first result)))
                      :verified-hits (count (filter #(= :hit (:cache %)) (:second result)))}}]
    (with-report-cid body)))

(defn pilot-share-report
  "Remove source paths, command output tails, and rejection text. The result is
  a bounded pilot-coordination receipt linked to the full local evidence by
  report CID and machine identity."
  [report]
  {:format pilot-share-format
   :decision (:decision report)
   :report-cid (:report-cid report)
   :subject (select-keys (:subject report) [:definition-closure-cid :files :bytes])
   :policy (-> (select-keys (:policy report) [:cid :target-abi :effects])
               (assoc :capabilities (vec (sort (:capabilities (:policy report))))))
   :machine (select-keys (:machine report) [:id :contract])
   :provider (select-keys (:provider report)
                          [:compiler-cid :module-lock-cid
                           :provider-closure-sha256 :runtime-sha256])
   :containment {:backing (get-in report [:containment :backing])
                 :blocked (vec (sort (get-in report [:containment :blocked])))
                 :leaked-count (count (get-in report [:containment :leaked]))}
   :checks (mapv #(select-keys % [:id :exit :cache :ms])
                 (get-in report [:checks :verified]))
   :builds (mapv #(select-keys % [:id :exit :cache :ms]) (:builds report))})

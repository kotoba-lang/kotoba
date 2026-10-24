(ns fleet.kcm-provider
  "Verification and execution boundary for a content-addressed Kotoba provider.

  The provider is an ordinary tar transport, but neither the archive nor a
  path inside it is trusted. The stable manifest closure is part of the KCM
  identity; the archive digest separately protects transport bytes. After
  extraction every regular file is matched against the closure manifest and
  symlinks are rejected. The provider carries the exact Node executable whose
  bytes are part of the KCM identity; the installed launcher enters through it."
  (:require ["node:child_process" :as cp]
            ["node:fs" :as fs]
            ["node:path" :as path]
            [cljs.reader :as reader]
            [kotoba.lang.text :as str]
            [fleet.kcm :as kcm]))

(def manifest-format :kotoba-provider/v1)

(defn manifest-body [manifest]
  (select-keys manifest [:format :compiler-revision :module-lock-sha256
                         :entry :files]))

(defn closure-sha256 [manifest]
  (kcm/sha256 (manifest-body manifest)))

(defn file-sha256 [p]
  (kcm/sha256-bytes (fs/readFileSync p)))

(defn- regular-files [root]
  (letfn [(walk [dir]
            (mapcat
             (fn [entry]
               (let [p (path/join dir (.-name entry))]
                 (cond
                   (.isSymbolicLink entry)
                   (throw (ex-info (str "provider contains symlink: " p) {:path p}))
                   (.isDirectory entry) (walk p)
                   (.isFile entry) [p]
                   :else (throw (ex-info (str "provider contains special file: " p)
                                         {:path p})))))
             (array-seq (fs/readdirSync dir #js {:withFileTypes true}))))]
    (->> (walk root)
         (map #(str/replace (path/relative root %) #"\\" "/"))
         sort vec)))

(defn- safe-archive-entry? [entry]
  (let [clean (str/replace entry #"^\./" "")
        parts (remove str/blank? (str/split clean #"/"))]
    (and (not (path/isAbsolute clean))
         (not-any? #{".."} parts))))

(defn- safe-relative? [p]
  (and (string? p) (not (str/blank? p)) (not (path/isAbsolute p))
       (not-any? #{".."} (str/split (str/replace p #"\\" "/") #"/"))))

(defn verify-manifest! [manifest expected]
  (let [files (:files manifest)
        paths (mapv :path files)
        {:keys [nbb-cli classpath main runner-classpath kcm-evaluate kcm-verify
                runtime-node sandbox-agent]}
        (:entry manifest)
        runner-paths (remove nil? (concat runner-classpath
                                          [kcm-evaluate kcm-verify runtime-node sandbox-agent]))]
  (when-not (= manifest-format (:format manifest))
    (throw (ex-info "unsupported Kotoba provider manifest" {:actual (:format manifest)})))
  (when-not (= expected (closure-sha256 manifest))
    (throw (ex-info "Kotoba provider closure digest mismatch"
                    {:expected expected :actual (closure-sha256 manifest)})))
  (when-not (and (vector? classpath) (seq classpath)
                 (every? safe-relative? classpath)
                 (safe-relative? nbb-cli) (safe-relative? main))
    (throw (ex-info "invalid Kotoba provider entry" {:entry (:entry manifest)})))
  (when (seq runner-paths)
    (when-not (and (vector? runner-classpath) (seq runner-classpath)
                   (every? safe-relative? runner-paths))
      (throw (ex-info "invalid KCM runner entry" {:entry (:entry manifest)}))))
  (when-not (and (vector? files) (seq files)
                 (= (count paths) (count (distinct paths)))
                 (every? safe-relative? paths)
                 (every? #(and (nat-int? (:size %)) (kcm/sha256-hex? (:sha256 %))) files)
                 (contains? (set paths) nbb-cli)
                 (contains? (set paths) main)
                 (every? #(contains? (set paths) %)
                         (remove nil? [kcm-evaluate kcm-verify runtime-node sandbox-agent])))
    (throw (ex-info "invalid Kotoba provider file manifest" {})))
  manifest))

(defn verify-tree! [root manifest]
  (let [declared (mapv :path (:files manifest))
        actual (regular-files root)]
    (when-not (= (vec (sort declared)) actual)
      (throw (ex-info "Kotoba provider file set mismatch"
                      {:missing (vec (remove (set actual) declared))
                       :extra (vec (remove (set declared) actual))})))
    (doseq [{:keys [path size sha256]} (:files manifest)]
      (let [p (path/join root path)
            stat (fs/statSync p)
            digest (file-sha256 p)]
        (when-not (and (= size (.-size stat)) (= sha256 digest))
          (throw (ex-info (str "Kotoba provider file digest mismatch: " path)
                          {:path path :expected sha256 :actual digest
                           :expected-size size :actual-size (.-size stat)})))))
    root))

(defn prepare!
  "Verify transport/runtime, extract once below ROOT, then verify the complete
  closure. Returns the exact argv prefix used for all KCM checks."
  [spec root]
  (let [{:keys [archive manifest]} (:kcm/provider spec)
        identity (:kcm/identity spec)
        manifest-data (reader/read-string (fs/readFileSync manifest "utf8"))
        expected-archive (get-in spec [:kcm/provider :archive-sha256])
        actual-archive (file-sha256 archive)
        expected-runtime (:runtime-sha256 identity)
        actual-runtime (file-sha256 js/process.execPath)
        provider-root (path/join root "provider")]
    (when-not (= expected-archive actual-archive)
      (throw (ex-info "Kotoba provider archive digest mismatch"
                      {:expected expected-archive :actual actual-archive})))
    (when-not (= expected-runtime actual-runtime)
      (throw (ex-info "KCM Node runtime digest mismatch"
                      {:runtime js/process.execPath
                       :expected expected-runtime :actual actual-runtime})))
    (verify-manifest! manifest-data (:provider-closure-sha256 identity))
    (let [entries (-> (cp/execFileSync "tar" #js ["tf" archive] #js {:encoding "utf8"})
                      str/split-lines)
          verbose (-> (cp/execFileSync "tar" #js ["tvf" archive] #js {:encoding "utf8"})
                      str/split-lines)]
      (when-let [unsafe (first (remove safe-archive-entry? entries))]
        (throw (ex-info (str "unsafe provider archive entry: " unsafe) {:entry unsafe})))
      (when-not (= (count entries) (count verbose))
        (throw (ex-info "provider archive listing disagreement" {})))
      (when-let [special (first (remove #(contains? #{\- \d} (first %)) verbose))]
        (throw (ex-info (str "provider archive contains link or special entry: " special)
                        {:entry special}))))
    (fs/rmSync provider-root #js {:recursive true :force true})
    (fs/mkdirSync provider-root #js {:recursive true})
    (cp/execFileSync "tar" #js ["xf" archive "-C" provider-root])
    (verify-tree! provider-root manifest-data)
    (let [{:keys [nbb-cli classpath main runtime-node]} (:entry manifest-data)
          inside #(path/join provider-root %)]
      (when (and runtime-node
                 (not= expected-runtime (file-sha256 (inside runtime-node))))
        (throw (ex-info "bundled KCM Node runtime digest mismatch" {})))
      {:root provider-root
       :manifest manifest-data
       :argv-prefix (into [(inside runtime-node) "--stack-size=4096"
                           (inside nbb-cli) "--classpath"
                           (str/join (.-delimiter path) (map inside classpath))
                           (inside main)] [])})))

(defn verify-prepared!
  "Re-verify transport, runtime and extracted closure before a cache hit can
  inherit evidence produced by an earlier provider."
  [spec prepared]
  (let [{:keys [archive manifest archive-sha256]} (:kcm/provider spec)
        identity (:kcm/identity spec)
        manifest-data (reader/read-string (fs/readFileSync manifest "utf8"))]
    (when-not (= archive-sha256 (file-sha256 archive))
      (throw (ex-info "Kotoba provider archive digest mismatch" {})))
    (when-not (= (:runtime-sha256 identity) (file-sha256 js/process.execPath))
      (throw (ex-info "KCM Node runtime digest mismatch" {})))
    (verify-manifest! manifest-data (:provider-closure-sha256 identity))
    (verify-tree! (:root prepared) manifest-data)
    prepared))

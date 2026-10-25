(ns provider.scoped-fs-transport
  "Production root-mount store for `provider.scoped-fs` (ADR 0144 / 0147).

  Does NOT define a new capability. Builds the store `(fn [op] -> reply)`
  host injects as `:store` into `provider.scoped-fs/provider`.

  ## No ambient filesystem authority

  There is **no default root** (not CWD, not home, not /tmp). The host must
  supply `:roots` as `{root-kw absolute-directory-path}`. Guest paths are
  resolved with `scoped-fs/resolve-path` then joined under the root; the
  canonical path must remain under the root's canonical directory
  (symlink escape is fail-closed).

  ## Dual runtime (ADR 0147)

  - **`:clj`** — `java.io.File` + NIO read/write + canonical under-root
  - **`:cljs` / nbb** — Node `fs` + `path` sync APIs; realpath of root and
    of existing parents/files before IO"
  (:require [kotoba.lang.text :as str]
            [provider.scoped-fs :as scoped-fs])
  #?(:clj
     (:import (java.io File)
              (java.nio.charset StandardCharsets)
              (java.nio.file Files LinkOption Path Paths))))

(defn under-root?
  "True when `canonical-child` is the root itself or a path strictly under
  `canonical-root` (prefix + separator). Pure string check on already-
  canonical absolute paths."
  [canonical-root canonical-child]
  (let [r (str canonical-root)
        c (str canonical-child)]
    (or (= r c)
        (and (str/starts-with? c r)
             (or (str/ends-with? r "/")
                 (str/starts-with? (subs c (count r)) "/"))))))

(defn absolute-path?
  "True when `p` is an absolute filesystem path."
  [p]
  (and (string? p)
       (not (str/blank? p))
       #?(:clj (.isAbsolute (java.io.File. ^String p))
          :cljs (try
                  (.isAbsolute (js/require "path") p)
                  (catch :default _ false)))))

#?(:clj
   (defn- as-file ^File [p]
     (if (instance? File p) p (File. (str p)))))

#?(:clj
   (defn- canonical ^String [^File f]
     (.getCanonicalPath f)))

#?(:clj
   (defn- resolve-file
     "Map root + guest relative path to a File under root, or error map."
     [root-file relative]
     (let [r (scoped-fs/resolve-path relative)]
       (if-let [err (:error r)]
         {:error err}
         (let [root-c (canonical root-file)
               child (File. root-file ^String (:ok r))
               child-c (try (canonical child)
                            (catch Exception _
                              nil))]
           (cond
             (nil? child-c) {:error :fs/io}
             (not (under-root? root-c child-c)) {:error :fs/escape}
             :else {:file child :path (:ok r)}))))))

#?(:clj
   (defn os-store
     "Build a production filesystem store (JVM).

     opts:
       :roots  required map {qualified-keyword absolute-dir-path-or-File}

     Returns store fn compatible with `provider.scoped-fs` mem-store shape."
     [{:keys [roots]}]
     (when-not (and (map? roots) (seq roots)
                    (every? qualified-keyword? (keys roots)))
       (throw (ex-info "scoped-fs-transport requires non-empty :roots map"
                       {:phase :scoped-fs-transport})))
     (let [root-files
           (into {}
                 (map (fn [[k p]]
                        (let [f (as-file p)]
                          (when-not (.isAbsolute f)
                            (throw (ex-info "scoped-fs-transport roots must be absolute"
                                            {:phase :scoped-fs-transport :root k})))
                          (when-not (and (.exists f) (.isDirectory f))
                            (throw (ex-info "scoped-fs-transport root must be an existing directory"
                                            {:phase :scoped-fs-transport :root k
                                             :path (.getPath f)})))
                          [k f]))
                      roots))]
       (fn [{:keys [op root path value]}]
         (let [rf (get root-files root)]
           (if-not rf
             {:tag :error :code :fs/unknown-root :message "unknown root"}
             (let [resolved (resolve-file rf path)]
               (if-let [err (:error resolved)]
                 {:tag :error :code err :message (name err)}
                 (let [^File f (:file resolved)]
                   (case op
                     :read
                     (if-not (.isFile f)
                       {:tag :error :code :fs/not-found :message "not found"}
                       (try
                         (let [bytes (Files/readAllBytes (.toPath f))
                               s (String. ^bytes bytes StandardCharsets/UTF_8)]
                           (if (> (count (.getBytes s StandardCharsets/UTF_8))
                                  scoped-fs/max-value-bytes)
                             {:tag :error :code :fs/too-large :message "file too large"}
                             {:tag :content :value s}))
                         (catch Exception e
                           {:tag :error :code :fs/io
                            :message (or (.getMessage e) "read failed")})))

                     :write
                     (try
                       (let [parent (.getParentFile f)]
                         (when (and parent (not (.exists parent)))
                           (.mkdirs parent))
                         (Files/writeString (.toPath f) (str value)
                                            StandardCharsets/UTF_8
                                            (into-array
                                             java.nio.file.OpenOption
                                             [java.nio.file.StandardOpenOption/CREATE
                                              java.nio.file.StandardOpenOption/TRUNCATE_EXISTING
                                              java.nio.file.StandardOpenOption/WRITE]))
                         {:tag :written})
                       (catch Exception e
                         {:tag :error :code :fs/io
                          :message (or (.getMessage e) "write failed")}))

                     {:tag :error :code :fs/unknown-op :message "unknown op"}))))))))))

#?(:cljs
   (defn- realpath-or-nil
     [fs p]
     (try
       (.realpathSync fs p)
       (catch :default _ nil))))

#?(:cljs
   (defn- utf8-byte-count
     [s]
     (.-length (.from js/Buffer (str s) "utf8"))))

#?(:cljs
   (defn- prepare-roots
     "Validate host roots and return {kw realpath-string}."
     [roots fs path-mod]
     (when-not (and (map? roots) (seq roots)
                    (every? qualified-keyword? (keys roots)))
       (throw (ex-info "scoped-fs-transport requires non-empty :roots map"
                       {:phase :scoped-fs-transport})))
     (into {}
           (map (fn [[k p]]
                  (let [s (str p)]
                    (when-not (.isAbsolute path-mod s)
                      (throw (ex-info "scoped-fs-transport roots must be absolute"
                                      {:phase :scoped-fs-transport :root k})))
                    (when-not (and (.existsSync fs s)
                                   (.isDirectory (.statSync fs s)))
                      (throw (ex-info "scoped-fs-transport root must be an existing directory"
                                      {:phase :scoped-fs-transport :root k
                                       :path s})))
                    (let [rp (realpath-or-nil fs s)]
                      (when-not rp
                        (throw (ex-info "scoped-fs-transport root realpath failed"
                                        {:phase :scoped-fs-transport :root k})))
                      [k rp])))
                roots))))

#?(:cljs
   (defn- join-under-root
     "Join guest relative under realpath root; pure policy + string under-root."
     [path-mod root-c relative]
     (let [r (scoped-fs/resolve-path relative)]
       (if-let [err (:error r)]
         {:error err}
         (let [joined (.join path-mod root-c (:ok r))]
           (if-not (under-root? root-c joined)
             {:error :fs/escape}
             {:joined joined :rel (:ok r)}))))))

#?(:cljs
   (defn- ensure-parent-under-root
     "mkdir -p parent; realpath parent must stay under root. nil = ok."
     [fs path-mod root-c joined]
     (let [parent (.dirname path-mod joined)]
       (try
         (when-not (.existsSync fs parent)
           (.mkdirSync fs parent #js {:recursive true}))
         (let [pr (realpath-or-nil fs parent)]
           (cond
             (nil? pr) :fs/io
             (not (under-root? root-c pr)) :fs/escape
             :else nil))
         (catch :default _ :fs/io)))))

#?(:cljs
   (defn os-store
     "Build a production filesystem store for nbb/cljs Node hosts (ADR 0147).

     opts:
       :roots  required {qualified-kw absolute-dir}
       :fs     optional Node fs module (tests)
       :path   optional Node path module (tests)"
     [{:keys [roots fs path] :as opts}]
     (let [fs (or fs (js/require "fs"))
           path-mod (or path (js/require "path"))
           root-paths (prepare-roots roots fs path-mod)]
       (fn [{:keys [op root path value]}]
         (let [root-c (get root-paths root)]
           (if-not root-c
             {:tag :error :code :fs/unknown-root :message "unknown root"}
             (let [resolved (join-under-root path-mod root-c path)]
               (if-let [err (:error resolved)]
                 {:tag :error :code err :message (name err)}
                 (let [joined (:joined resolved)]
                   (case op
                     :read
                     (if-not (and (.existsSync fs joined)
                                  (.isFile (.statSync fs joined)))
                       {:tag :error :code :fs/not-found :message "not found"}
                       (try
                         (let [real (realpath-or-nil fs joined)]
                           (cond
                             (nil? real)
                             {:tag :error :code :fs/io :message "realpath failed"}

                             (not (under-root? root-c real))
                             {:tag :error :code :fs/escape :message "escape"}

                             :else
                             (let [s (.readFileSync fs real "utf8")]
                               (if (> (utf8-byte-count s) scoped-fs/max-value-bytes)
                                 {:tag :error :code :fs/too-large :message "file too large"}
                                 {:tag :content :value s}))))
                         (catch :default e
                           {:tag :error :code :fs/io
                            :message (or (.-message e) "read failed")})))

                     :write
                     (if-let [perr (ensure-parent-under-root fs path-mod root-c joined)]
                       {:tag :error :code perr :message (name perr)}
                       (try
                         (.writeFileSync fs joined (str value) "utf8")
                         (let [real (realpath-or-nil fs joined)]
                           (if (and real (under-root? root-c real))
                             {:tag :written}
                             {:tag :error :code :fs/escape :message "escape after write"}))
                         (catch :default e
                           {:tag :error :code :fs/io
                            :message (or (.-message e) "write failed")})))

                     {:tag :error :code :fs/unknown-op :message "unknown op"}))))))))))

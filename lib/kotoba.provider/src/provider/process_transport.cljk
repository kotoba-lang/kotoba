(ns provider.process-transport
  "Production OS spawn transport for `provider.process` (ADR 0144 / 0147).

  Does NOT define a new capability. Builds the `(fn [request] -> reply)`
  host injects as `:spawn` into `provider.process/provider`.

  ## No ambient process authority

  There is **no default PATH scan**. The host must supply an explicit
  `:binaries` map of `{basename absolute-path}` for every command it
  intends to allow. Basename validation remains in `provider.process`;
  this transport only runs binaries the host named.

  ## Bounds

  - stdout/stderr captured up to `:max-stdout-bytes` (truncate rest)
  - wall timeout after `:timeout-ms`
  - never inherits ambient shell; argv is the full command vector
  - `:shell false` on cljs (no `/bin/sh -c`)

  ## Dual runtime (ADR 0147)

  - **`:clj`** — `ProcessBuilder` + `waitFor` timeout + bounded stream drain
  - **`:cljs` / nbb** — `child_process.spawnSync` with absolute binary path,
    `timeout`, `maxBuffer`, encoding utf8 (sync contract for reference host)"
  (:require [kotoba.lang.text :as str]
            [provider.process :as process])
  #?(:clj
     (:import (java.io ByteArrayOutputStream InputStream)
              (java.nio.charset StandardCharsets)
              (java.util.concurrent TimeUnit))))

(defn resolve-binary
  "Look up `basename` in host-supplied `binaries` map. Returns absolute
  path string or nil. Pure map lookup — never searches PATH."
  [binaries basename]
  (when (and (map? binaries) (string? basename))
    (let [p (get binaries basename)]
      (when (and (string? p) (not (str/blank? p)))
        p))))

(defn absolute-path?
  "True when `p` is an absolute filesystem path.
  Pure-ish: clj uses File/isAbsolute; cljs uses Node path.isAbsolute."
  [p]
  (and (string? p)
       (not (str/blank? p))
       #?(:clj (.isAbsolute (java.io.File. ^String p))
          :cljs (try
                  (.isAbsolute (js/require "path") p)
                  (catch :default _ false)))))

(defn- truncate-utf8
  "Return at most `max-bytes` UTF-8 bytes of `s` (string)."
  [s max-bytes]
  (let [s (str s)]
    #?(:clj
       (let [bytes (.getBytes s StandardCharsets/UTF_8)]
         (if (<= (alength bytes) (long max-bytes))
           s
           (String. bytes 0 (int max-bytes) StandardCharsets/UTF_8)))
       :cljs
       (let [buf (.from js/Buffer s "utf8")
             n (long max-bytes)]
         (if (<= (.-length buf) n)
           s
           (.toString (.slice buf 0 n) "utf8"))))))

(defn- validate-binaries!
  [binaries]
  (when-not (and (map? binaries) (seq binaries)
                 (every? string? (keys binaries))
                 (every? string? (vals binaries)))
    (throw (ex-info "process-transport requires non-empty :binaries map"
                    {:phase :process-transport})))
  (doseq [[_ p] binaries]
    (when-not (absolute-path? p)
      (throw (ex-info "process-transport binary paths must be absolute"
                      {:phase :process-transport :path p})))))

#?(:clj
   (defn- read-bounded
     "Drain `in` into a string of at most `max-bytes` UTF-8 bytes."
     [^InputStream in max-bytes]
     (let [buf (byte-array 4096)
           out (ByteArrayOutputStream.)]
       (loop [total 0]
         (let [n (.read in buf)]
           (cond
             (neg? n) (.toString out StandardCharsets/UTF_8)
             (>= total max-bytes) (.toString out StandardCharsets/UTF_8)
             :else
             (let [take (min n (- max-bytes total))]
               (.write out buf 0 take)
               (recur (+ total take)))))))))

#?(:clj
   (defn os-spawn
     "Build a production spawn transport (JVM).

     opts:
       :binaries  required map {\"echo\" \"/bin/echo\", ...}
                  absolute paths only; no ambient PATH.

     Returns `(fn [{:keys [argv max-stdout-bytes timeout-ms]}] -> reply)`
     where reply is `{:tag :ok :exit :stdout :stderr}` or
     `{:tag :error :code :message}`."
     [{:keys [binaries] :as opts}]
     (validate-binaries! binaries)
     (fn [{:keys [argv max-stdout-bytes timeout-ms]
           :or {max-stdout-bytes process/max-stdout-bytes
                timeout-ms 5000}}]
       (let [cmd (first argv)
             bin (resolve-binary binaries cmd)]
         (cond
           (nil? bin)
           {:tag :error
            :code :process/no-binary
            :message (str "no host binary for " cmd)}

           :else
           (try
             (let [pb (doto (ProcessBuilder. ^java.util.List (vec (cons bin (rest argv))))
                        (.redirectErrorStream false))
                   proc (.start pb)
                   finished (.waitFor proc (long timeout-ms) TimeUnit/MILLISECONDS)]
               (if-not finished
                 (do
                   (.destroyForcibly proc)
                   {:tag :error
                    :code :process/timeout
                    :message (str "timeout after " timeout-ms "ms")})
                 (let [out (read-bounded (.getInputStream proc) (long max-stdout-bytes))
                       err (read-bounded (.getErrorStream proc) (long max-stdout-bytes))
                       exit (.exitValue proc)]
                   {:tag :ok
                    :exit (long exit)
                    :stdout (str out)
                    :stderr (str err)})))
             (catch Exception e
               {:tag :error
                :code :process/spawn
                :message (or (.getMessage e) "spawn failed")})))))))

#?(:cljs
   (defn os-spawn
     "Build a production spawn transport for nbb/cljs Node hosts (ADR 0147).

     Uses `child_process.spawnSync` with the host-mapped absolute binary
     (never PATH, never shell). Optional `:spawn-sync` injects a test double
     with the same `(bin args opts-js) -> result-js` shape as spawnSync.

     opts:
       :binaries    required {basename abs-path}
       :spawn-sync  optional (fn [bin args-js opts-js] result)"
     [{:keys [binaries spawn-sync] :as opts}]
     (validate-binaries! binaries)
     (let [spawn-sync
           (or spawn-sync
               (fn [bin args opts]
                 (.spawnSync (js/require "child_process") bin args opts)))]
       (fn [{:keys [argv max-stdout-bytes timeout-ms]
             :or {max-stdout-bytes process/max-stdout-bytes
                  timeout-ms 5000}}]
         (let [cmd (first argv)
               bin (resolve-binary binaries cmd)
               max-out (long max-stdout-bytes)
               t-ms (long timeout-ms)]
           (cond
             (nil? bin)
             {:tag :error
              :code :process/no-binary
              :message (str "no host binary for " cmd)}

             :else
             (try
               (let [args (clj->js (vec (rest argv)))
                     result (spawn-sync bin args
                                        #js {:encoding "utf8"
                                             :timeout t-ms
                                             :maxBuffer max-out
                                             :shell false
                                             :windowsHide true})
                     err (.-error result)]
                 (if err
                   (let [code (.-code err)
                         msg (or (.-message err) "spawn failed")]
                     (if (or (= code "ETIMEDOUT")
                             (str/includes? (str msg) "TIMEDOUT")
                             (str/includes? (str msg) "timeout"))
                       {:tag :error
                        :code :process/timeout
                        :message (str "timeout after " t-ms "ms")}
                       {:tag :error
                        :code :process/spawn
                        :message (str msg)}))
                   {:tag :ok
                    :exit (long (or (.-status result) 1))
                    :stdout (truncate-utf8 (or (.-stdout result) "") max-out)
                    :stderr (truncate-utf8 (or (.-stderr result) "") max-out)}))
               (catch :default e
                 {:tag :error
                  :code :process/spawn
                  :message (or (.-message e) "spawn failed")}))))))))

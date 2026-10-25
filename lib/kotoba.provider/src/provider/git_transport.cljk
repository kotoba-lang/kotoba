(ns provider.git-transport
  "Production git run transport for `provider.git` (ADR 0148–0150).

  Does NOT define a new capability. Builds `(fn [request] -> reply)` for
  injection as `:run` into `provider.git/provider`.

  ## No ambient git authority

  - No PATH scan — host supplies absolute `:git-bin`
  - No ambient CWD — host supplies absolute `:worktree` directory
  - Subcommand policy remains in `provider.git/validate-run`

  ## Dual runtime

  - **`:clj`** — ProcessBuilder with `.directory(worktree)`
  - **`:cljs` / nbb** — `child_process.spawnSync` with `:cwd worktree`
    (ADR 0150; same sync contract as process-transport/os-spawn)"
  (:require [kotoba.lang.text :as str]
            [provider.git :as git]
            [provider.process-transport :as process-transport])
  #?(:clj
     (:import (java.io File)
              (java.util.concurrent TimeUnit))))

(defn echo-run
  "Alias of `provider.git/echo-transport` for transport ns symmetry."
  []
  (git/echo-transport))

(defn- validate-os-run-opts!
  "Shared host config checks for JVM and cljs."
  [{:keys [git-bin worktree]}]
  (when-not (and (string? git-bin)
                 (process-transport/absolute-path? git-bin))
    (throw (ex-info "git-transport/os-run requires absolute :git-bin"
                    {:phase :git-transport})))
  (when-not (and (string? worktree)
                 (process-transport/absolute-path? worktree))
    (throw (ex-info "git-transport/os-run requires absolute :worktree directory"
                    {:phase :git-transport :worktree worktree}))))

#?(:clj
   (defn- read-stream
     [^java.io.InputStream in max-bytes]
     (let [buf (byte-array 4096)
           out (java.io.ByteArrayOutputStream.)]
       (loop [total 0]
         (let [n (.read in buf)]
           (cond
             (neg? n) (.toString out java.nio.charset.StandardCharsets/UTF_8)
             (>= total max-bytes) (.toString out java.nio.charset.StandardCharsets/UTF_8)
             :else
             (let [take (min n (- max-bytes total))]
               (.write out buf 0 take)
               (recur (+ total take)))))))))

#?(:clj
   (defn os-run
     "Build a production git `:run` transport (JVM).

     opts:
       :git-bin    required absolute path to git executable
       :worktree   required absolute directory containing .git (or worktree)
       :timeout-ms optional default timeout if request omits one

     Returns `(fn [{:keys [args max-stdout-bytes timeout-ms]}] -> reply)`."
     [{:keys [git-bin worktree timeout-ms] :as opts}]
     (validate-os-run-opts! {:git-bin git-bin :worktree (str worktree)})
     (let [dir (if (instance? File worktree) worktree (File. (str worktree)))]
       (when-not (and (.isAbsolute dir) (.isDirectory dir))
         (throw (ex-info "git-transport/os-run worktree must be an existing directory"
                         {:phase :git-transport})))
       (when-not (.canExecute (File. ^String git-bin))
         (throw (ex-info "git-transport/os-run :git-bin must be executable"
                         {:phase :git-transport})))
       (fn [{:keys [args max-stdout-bytes timeout-ms]
             :or {max-stdout-bytes git/max-stdout-bytes
                  timeout-ms (or timeout-ms 5000)}}]
         (try
           (let [pb (doto (ProcessBuilder. ^java.util.List (vec (cons git-bin (map str args))))
                      (.directory dir)
                      (.redirectErrorStream false))
                 proc (.start pb)
                 finished (.waitFor proc (long timeout-ms) TimeUnit/MILLISECONDS)]
             (if-not finished
               (do (.destroyForcibly proc)
                   {:tag :error
                    :code :git/timeout
                    :message (str "timeout after " timeout-ms "ms")})
               (let [out (read-stream (.getInputStream proc) (long max-stdout-bytes))
                     err (read-stream (.getErrorStream proc) (long max-stdout-bytes))
                     exit (.exitValue proc)]
                 {:tag :ok
                  :exit (long exit)
                  :stdout (str out)
                  :stderr (str err)})))
           (catch Exception e
             {:tag :error
              :code :git/run
              :message (or (.getMessage e) "git spawn failed")}))))))

#?(:cljs
   (defn- truncate-utf8
     [s max-bytes]
     (let [buf (.from js/Buffer (str s) "utf8")
           n (long max-bytes)]
       (if (<= (.-length buf) n)
         (str s)
         (.toString (.slice buf 0 n) "utf8")))))

#?(:cljs
   (defn os-run
     "Build a production git `:run` transport for nbb/cljs Node (ADR 0150).

     Uses `child_process.spawnSync` with absolute `:git-bin` and
     `cwd: worktree` (never PATH, never shell). Optional `:spawn-sync`
     injects a test double matching spawnSync's result shape.

     opts:
       :git-bin     required absolute path
       :worktree    required absolute directory
       :timeout-ms  optional default
       :spawn-sync  optional (fn [bin args-js opts-js] result)"
     [{:keys [git-bin worktree timeout-ms spawn-sync] :as opts}]
     (validate-os-run-opts! opts)
     (let [spawn-sync
           (or spawn-sync
               (fn [bin args o]
                 (.spawnSync (js/require "child_process") bin args o)))]
       (fn [{:keys [args max-stdout-bytes timeout-ms]
             :or {max-stdout-bytes git/max-stdout-bytes
                  timeout-ms (or timeout-ms 5000)}}]
         (let [max-out (long max-stdout-bytes)
               t-ms (long timeout-ms)]
           (try
             (let [result (spawn-sync git-bin
                                      (clj->js (mapv str args))
                                      #js {:cwd worktree
                                           :encoding "utf8"
                                           :timeout t-ms
                                           :maxBuffer max-out
                                           :shell false
                                           :windowsHide true})
                   err (.-error result)]
               (if err
                 (let [code (.-code err)
                       msg (or (.-message err) "git spawn failed")]
                   (if (or (= code "ETIMEDOUT")
                           (str/includes? (str msg) "TIMEDOUT")
                           (str/includes? (str msg) "timeout"))
                     {:tag :error
                      :code :git/timeout
                      :message (str "timeout after " t-ms "ms")}
                     {:tag :error
                      :code :git/run
                      :message (str msg)}))
                 {:tag :ok
                  :exit (long (or (.-status result) 1))
                  :stdout (truncate-utf8 (or (.-stdout result) "") max-out)
                  :stderr (truncate-utf8 (or (.-stderr result) "") max-out)}))
             (catch :default e
               {:tag :error
                :code :git/run
                :message (or (.-message e) "git spawn failed")})))))))

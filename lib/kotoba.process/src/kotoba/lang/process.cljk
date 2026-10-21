(ns kotoba.lang.process
  "Process spawn policy + host-injected IProcess. Twin of kotoba.lang.fs.

  Pure validation never touches the OS. Effectful spawn lives behind IProcess,
  which a host implements (see kotoba.lang.process-host). An echo-process is
  provided for tests.

  Zero third-party runtime deps; .cljc."
  (:require [kotoba.lang.text :as str])
  #?(:cljs (:require ["child_process" :as cp]))
  #?(:clj
     (:import (java.io ByteArrayOutputStream InputStream)
              (java.nio.charset StandardCharsets)
              (java.util.concurrent TimeUnit)))
  (:require [kotoba.process.process :as process-p]))

(def max-argv 64)
(def max-arg-bytes 4096)
(def max-stdout-bytes 65536)
(def max-timeout-ms 600000)

(def error-types
  "Stable `:type` / validate-spawn keywords. Callers branch on these, never on
  host exception class names."
  #{:process/argv-type :process/empty-argv :process/argv-too-long
    :process/bad-arg :process/path-command :process/not-allowed
    :process/bad-max-stdout :process/bad-timeout
    :process/no-binary :process/timeout :process/spawn})

(defn validate-spawn
  "Pure spawn policy. Returns nil when ok, else an error keyword.

  `argv` is a sequential of strings. `allowed` is a set of permitted basenames
  for argv[0], or nil to skip the allowlist (tests only — production hosts
  must pass a set)."
  ([argv max-out timeout] (validate-spawn argv max-out timeout nil))
  ([argv max-out timeout allowed]
   (cond
     (not (sequential? argv)) :process/argv-type
     (empty? argv) :process/empty-argv
     (> (count argv) max-argv) :process/argv-too-long
     (some #(or (not (string? %)) (str/blank? %)
                (> (count %) max-arg-bytes)) argv)
     :process/bad-arg
     (str/includes? (str (first argv)) "/") :process/path-command
     (str/includes? (str (first argv)) "\\") :process/path-command
     (and allowed (not (contains? allowed (first argv)))) :process/not-allowed
     (not (and (integer? max-out) (pos? max-out) (<= max-out max-stdout-bytes)))
     :process/bad-max-stdout
     (not (and (integer? timeout) (pos? timeout) (<= timeout max-timeout-ms)))
     :process/bad-timeout
     :else nil)))

#?(:clj
   (defn- read-bounded
     "Read `in` fully (bounded by `max-bytes`) as UTF-8. Twin of the helper in
     kotoba.lang.process-host's `sh` — duplicated here (not required) because
     process-host itself requires this namespace, so requiring the other way
     round would be circular."
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

(defn exec
  "Run `argv` as an exec-array — never through a shell — capturing stdout.

  Portable replacement for shelling out in .cljc code: returns
  `{:status N :stdout string :stderr string}`. The command is executed
  directly with `argv` vector (JVM: `java.lang.ProcessBuilder` directly —
  same real-spawn primitive `kotoba.lang.process-host/sh` uses, this library
  does NOT require `clojure.java.shell`; CLJS: `child_process` array exec —
  no `shell: true`, no string shellouts), so argv values never round-trip
  through a shell. A missing/invald command fails closed: non-zero `:status`,
  no throw.

  `argv` must be a non-empty sequential of strings. Bounds match
  `validate-spawn` (max-argv 64, per-arg byte cap, path-command/backslash
  rejection). Pass an optional `allowed` set as the second arg to enforce a
  basename allowlist (production callers should)."
  ([argv] (exec argv nil))
  ([argv allowed]
   (let [err (validate-spawn argv max-stdout-bytes max-timeout-ms allowed)]
     (if err
       {:status 127 :stdout "" :stderr (str "exec rejected: " (name err))}
       #?(:clj
          (try
            (let [pb (doto (ProcessBuilder. ^java.util.List (vec (map str argv)))
                       (.redirectErrorStream false))
                  proc (.start pb)
                  ;; Read stdout/stderr concurrently (same reason sh-transport!
                  ;; does: a large child output must not deadlock against us
                  ;; still holding stdin open).
                  stdout-f (future (read-bounded (.getInputStream proc) (long max-stdout-bytes)))
                  stderr-f (future (read-bounded (.getErrorStream proc) (long max-stdout-bytes)))]
              ;; exec never pipes :in — close stdin immediately so any child
              ;; that reads stdin sees EOF rather than hanging.
              (.close (.getOutputStream proc))
              (let [finished (.waitFor proc (long max-timeout-ms) TimeUnit/MILLISECONDS)]
                (if-not finished
                  (do (.destroyForcibly proc)
                      {:status 127
                       :stdout ""
                       :stderr (str "exec timeout after " max-timeout-ms "ms")})
                  {:status (long (.exitValue proc))
                   :stdout (str @stdout-f)
                   :stderr (str @stderr-f)})))
            ;; ProcessBuilder/.start() throws IOException when the binary is
            ;; missing (it does not fail closed by itself) — this wrapper is
            ;; what turns that (and any other spawn-time failure) into a
            ;; non-zero status, never a throw.
            (catch Exception e
              {:status 127
               :stdout ""
               :stderr (or (.getMessage e) "exec failed")}))
          :cljs
          (try
            (let [r (cp/execFileSync (first argv) (subvec argv 1)
                                     #js {:encoding "utf8"
                                          :maxBuffer max-stdout-bytes
                                          :windowsHide true})]
              {:status 0 :stdout (str r) :stderr ""})
            (catch :default e
              {:status (long (or (.-status e) 1))
               :stdout (str (or (.-stdout e) ""))
               :stderr (str (or (.-stderr e) (.-message e) "exec failed"))})))))))

(def IProcess
  "The protocol itself lives in one repo of its own now. This name is that
  SAME protocol, not a second one: an implementation reified against either
  is accepted by both (ADR-2609091900)."
  process-p/Process)

(def spawn! process-p/spawn!)

(defn echo-process
  "Test double: exit 0, stdout = space-joined argv rest, stderr empty.
  Still runs validate-spawn when `:allowed` is set on the handle."
  ([] (echo-process nil))
  ([allowed]
   (reify IProcess
     (spawn! [_ {:keys [argv max-stdout-bytes timeout-ms]
                 :or {max-stdout-bytes 65536
                      timeout-ms 5000}}]
       (if-let [err (validate-spawn argv max-stdout-bytes timeout-ms allowed)]
         {:tag :error :code err :message (name err)}
         {:tag :ok
          :exit 0
          :stdout (str/join " " (rest argv))
          :stderr ""})))))
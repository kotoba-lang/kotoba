#!/usr/bin/env nbb
;; --- nbb shims (auto, ADR-2607173000) ---------------------------------
(def ^:private __fs (js/require "node:fs"))
(def ^:private __path (js/require "node:path"))
(def ^:private __cp (js/require "node:child_process"))
(def ^:private __os (js/require "node:os"))
(def ^:private __crypto (js/require "node:crypto"))
(defn- __sh [& args]
  (let [opts (when (map? (last args)) (last args))
        cmd (if opts (butlast args) args)
        r (.spawnSync __cp (first cmd) (to-array (rest cmd))
                      (clj->js (merge {:encoding "utf8"} (when opts {:cwd (:dir opts)}))))]
    {:exit (or (.-status r) 1) :out (or (.-stdout r) "") :err (or (.-stderr r) "")}))
(defn- __shell [& args]
  (let [opts (when (map? (first args)) (first args))
        cmd (if opts (rest args) args)
        r (.spawnSync __cp (first cmd) (to-array (rest cmd))
                      (clj->js (merge {:stdio "inherit" :encoding "utf8"}
                                      (when opts {:cwd (:dir opts)}))))]
    (when-not (zero? (or (.-status r) 1))
      (throw (js/Error. (str "shell failed: " (pr-str cmd)))))
    {:exit (or (.-status r) 0) :out "" :err ""}))
;; -----------------------------------------------------------------------
;; build-pywasm.nbb <entry.py> -o <out.wasm>
;;
;; Compile a kotoba_modal guest entry into a kotoba-node WASM component via
;; componentize-py, using the WIT vendored under this package's wit/ directory.

(ns build-pywasm
  (:require                         [clojure.string :as str]))

(def usage "usage: build-pywasm.nbb <entry.py> -o <out.wasm>")

(defn fail! [message code]
  (binding [*out* *err*]
    (println message))
  (.exit js/process code))

(defn parse-args [args]
  (loop [remaining args
         entry nil
         out "index.wasm"]
    (let [[arg next-arg & rest-args] remaining]
      (case arg
        nil {:entry entry :out out}
        ("-h" "--help") (do (println usage) (.exit js/process 0))
        ("-o" "--output") (if next-arg
                             (recur rest-args entry next-arg)
                             (fail! usage 2))
        (recur (rest remaining) arg out)))))

(defn executable? [cmd]
  (or (fs/which cmd)
      (when (and (or (str/includes? cmd "/") (str/includes? cmd "\\"))
                 (fs/exists? cmd))
        cmd)))

(defn env-command [name default-value]
  (let [value (System/getenv name)]
    (cond
      (nil? value) default-value
      (str/blank? value) (fail! (str name " resolved to an empty command") 2)
      :else (str/trim value))))

(let [{:keys [entry out]} (parse-args *command-line-args*)
      package-root (-> *file* fs/absolutize fs/parent fs/parent str)
      wit-dir (str (fs/path package-root "wit"))
      componentize-py (env-command "COMPONENTIZE_PY" "componentize-py")]
  (when (str/blank? entry)
    (fail! usage 2))
  (when-not (fs/regular-file? entry)
    (fail! (str "entry not found: " entry) 2))
  (when-not (executable? componentize-py)
    (fail! "componentize-py not found (set COMPONENTIZE_PY)" 127))
  (let [entry-dir (-> entry fs/absolutize fs/parent str)
        app (str/replace (fs/file-name entry) #"\.py$" "")
        proc (process/process [componentize-py "-d" wit-dir "-w" "kotoba-node"
                               "componentize" app "-p" entry-dir "-p" package-root
                               "-o" out]
                              {:out :inherit :err :inherit :in :inherit})]
    (.exit js/process (:exit @proc))))

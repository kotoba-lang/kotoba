#!/usr/bin/env nbb
(ns build-pywasm
  (:require [clojure.string :as str]))

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
  (let [probe (.spawnSync __cp "sh" #js ["-c" "command -v \"$1\"" "sh" cmd]
                          #js {:encoding "utf8"})]
    (zero? (or (.-status probe) 1))))

(defn env-command [name default-value]
  (let [value (aget (.-env js/process) name)]
    (cond
      (nil? value) default-value
      (str/blank? value) (fail! (str name " resolved to an empty command") 2)
      :else (str/trim value))))

(let [{:keys [entry out]} (parse-args (js->clj (.slice (.-argv js/process) 2)))
      package-root (.dirname __path (.dirname __path (aget (.-argv js/process) 1)))
      wit-dir (.join __path package-root "wit")
      componentize-py (env-command "COMPONENTIZE_PY" "componentize-py")]
  (when (str/blank? entry)
    (fail! usage 2))
  (when-not (and (.existsSync __fs entry) (.isFile (.statSync __fs entry)))
    (fail! (str "entry not found: " entry) 2))
  (when-not (executable? componentize-py)
    (fail! "componentize-py not found (set COMPONENTIZE_PY)" 127))
  (let [absolute (.resolve __path entry)
        entry-dir (.dirname __path absolute)
        app (str/replace (.basename __path entry) #"\.py$" "")
        proc (.spawnSync __cp componentize-py
                         (clj->js ["-d" wit-dir "-w" "kotoba-node"
                                   "componentize" app "-p" entry-dir "-p" package-root
                                   "-o" out])
                         #js {:stdio "inherit"})]
    (.exit js/process (or (.-status proc) 1))))

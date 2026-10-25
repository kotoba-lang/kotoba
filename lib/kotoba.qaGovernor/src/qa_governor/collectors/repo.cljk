(ns qa-governor.collectors.repo
  "kotoba-lang/qa-governor — top-level JVM host adapter: runs every
  deterministic collector currently implemented (ADR-2607031100) against a
  single project directory and returns one combined proposal covering as
  many rubric categories as this library can measure mechanically today
  (correctness, consistency, stability, robustness, documentation). No LLM
  involved — this is the mechanically-verifiable floor a future LLM
  scoring node would sit on top of."
  (:require [qa-governor.collectors.clojure-project :as clojure-project]
            [qa-governor.collectors.clojure-project-shell :as clojure-project-shell]
            [qa-governor.collectors.static-analysis-shell :as static-analysis]))

(defn collect
  "project-dirに対して全collectorを実行し、proposal(entryのvector)を返す。"
  [project-dir]
  (let [{:keys [test-output lint-output elapsed-test-ms]}
        (clojure-project-shell/run-test+lint project-dir)]
    (into [(clojure-project/correctness-entry test-output)
           (clojure-project/consistency-entry lint-output)]
          (static-analysis/collect project-dir elapsed-test-ms))))

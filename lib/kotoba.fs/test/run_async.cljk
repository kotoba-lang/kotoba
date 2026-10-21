(ns run-async
  (:require [kotoba.lang.fs :as fs]
            [kotoba.lang.fs-host :as host]))

(def node-fs (js/require "fs"))
(def node-path (js/require "path"))
(def node-os (js/require "os"))
(def root (.mkdtempSync node-fs (.join node-path (.tmpdir node-os) "fs-async-test-")))
(def handle (host/async-host-filesystem {:root root :max-bytes 32}))

(defn assert! [truth label]
  (when-not truth (throw (js/Error. (str "async fs assertion failed: " label)))))

(-> (fs/write-async handle "dir/a.txt" "hello")
    (.then (fn [_] (fs/read-async handle "dir/a.txt")))
    (.then (fn [s]
             (assert! (= "hello" s) "roundtrip")
             (fs/list-async handle "dir")))
    (.then (fn [items]
             (assert! (= ["a.txt"] items) "list")
             (fs/exists-async? handle "dir/a.txt")))
    (.then (fn [present]
             (assert! present "exists")
             (fs/read-async handle "../secret")))
    (.then (fn [_] (throw (js/Error. "escape unexpectedly succeeded"))))
    (.catch (fn [e]
              (assert! (= :fs/escape (fs/eventual-error-type e)) "typed escape refusal")
              (fs/delete-async handle "dir/a.txt")))
    (.then (fn [_] (fs/exists-async? handle "dir/a.txt")))
    (.then (fn [present]
             (assert! (false? present) "delete")
             (println "async filesystem capability probe: OK")))
    (.catch (fn [e]
              (js/console.error e)
              (js/process.exit 1))))

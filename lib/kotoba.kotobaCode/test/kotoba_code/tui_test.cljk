(ns kotoba-code.tui-test
  (:require [kotoba.lang.text :as str]
            [clojure.test :refer [deftest is]]
            [kotoba-code.tui :as tui]))

(deftest header-exposes-runtime-context
  (let [out (tui/header {:root "/work/demo"
                         :model "murakumo:test"
                         :session "review"
                         :datom? true})]
    (is (str/includes? out "kotoba"))
    (is (str/includes? out "/work/demo"))
    (is (str/includes? out "murakumo:test"))
    (is (str/includes? out "review"))
    (is (str/includes? out "durable"))))

(deftest captured-block-keeps-prompt-and-result-together
  (let [out (tui/capture-block "/status" " M src/core.clj\n")]
    (is (str/includes? out "❯ /status"))
    (is (str/includes? out "M src/core.clj"))))

(ns kotobase.storage.postgres-test
  (:require [clojure.test :refer [deftest is]]
            [kotobase.storage.postgres :as postgres]))

(deftest datasource-is-required
  (is (thrown? clojure.lang.ExceptionInfo (postgres/open {}))))

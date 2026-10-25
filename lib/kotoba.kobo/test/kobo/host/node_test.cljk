(ns kobo.host.node-test
  "Proves the loop closes: open a terminal, run a command, and the result is
  in the same workbench value the console renders."
  (:require [cljs.test :refer [deftest is testing]]
            [kotoba.lang.text :as str]
            [kobo.host.node :as host]
            [kobo.ui :as ui]
            [kobo.workbench :as wb]))

(def node (.-execPath js/process))

(defn- open []
  (-> (wb/workbench "bafkreitestrepo") (wb/open-terminal "t1" :terminal-repo)))

(deftest receipt-lands-in-the-workbench
  (let [w (host/run (open) "t1" [node "-e" "process.stdout.write('hi')"]
                    {:repo-root "."})
        [r] (:kobo/receipts w)]
    (is (= 1 (count (:kobo/receipts w))))
    (is (= 0 (:kuro/exit-code r)))
    (is (= "hi" (:kuro/stdout r)))
    (is (str/starts-with? (:kuro/stdout-cid r) "bafkrei"))
    (testing "and reaches the console"
      (is (str/includes? (ui/console w) "bafkrei")))))

(deftest denial-lands-too
  (testing "a refused command is recorded, not dropped — an empty receipt list
            must not mean both 'denied' and 'never typed'"
    (let [w (-> (wb/workbench "bafkreitestrepo")
                (wb/open-terminal "t1" :terminal-repo)
                (host/run "t1" [node "-e" "0"]
                          {:repo-root "." :kuro/requires #{"secrets/get"}}))]
      (is (empty? (:kobo/receipts w)))
      (is (= 1 (count (:kobo/denials w))))
      (is (= ["secrets/get"] (:kuro/missing (first (:kobo/denials w)))))
      (is (str/includes? (ui/console w) "secrets/get")))))

(deftest unknown-terminal-is-an-error-not-a-silent-noop
  (is (thrown? ExceptionInfo (host/run (open) "nope" [node "-e" "0"] {:repo-root "."}))))

(deftest receipts-accumulate-in-order
  (let [w (-> (open)
              (host/run "t1" [node "-e" "process.stdout.write('1')"] {:repo-root "."})
              (host/run "t1" [node "-e" "process.exit(2)"] {:repo-root "."}))]
    (is (= ["1" ""] (mapv :kuro/stdout (:kobo/receipts w))))
    (is (= [0 2] (mapv :kuro/exit-code (:kobo/receipts w))))))

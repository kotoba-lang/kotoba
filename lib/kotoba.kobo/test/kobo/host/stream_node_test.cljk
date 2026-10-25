(ns kobo.host.stream-node-test
  "実行中の状態が workbench に載り、終わったら receipt に移ることを確認する。"
  (:require [cljs.test :refer [deftest is testing async]]
            [kotoba.lang.text :as str]
            [kobo.host.stream-node :as sh]
            [kobo.ui :as ui]
            [kobo.workbench :as wb]))

(def node (.-execPath js/process))

(defn- open-atom []
  (atom (-> (wb/workbench "bafkreitestrepo") (wb/open-terminal "t1" :terminal-repo))))

(deftest running-then-receipt
  (async done
    (let [a (open-atom)]
      (sh/start a "t1" [node "-e" "process.stdout.write('hi'); setTimeout(()=>process.exit(0), 40)"]
                {:repo-root "."
                 :on-exit (fn [_]
                            (testing "finished: out of :kobo/running, into :kobo/receipts"
                              (is (empty? (:kobo/running @a)))
                              (is (= 1 (count (:kobo/receipts @a))))
                              (is (= "hi" (:kuro/stdout (first (:kobo/receipts @a))))))
                            (done))})
      (testing "visible as running before any output arrives"
        (is (= 1 (count (:kobo/running @a))))
        (is (empty? (:kobo/receipts @a)))
        (is (str/includes? (ui/console @a) "running"))))))

(deftest live-output-reaches-the-console
  (async done
    (let [a (open-atom)
          seen (atom nil)]
      (sh/start a "t1" [node "-e" "process.stdout.write('partial'); setTimeout(()=>process.exit(0), 60)"]
                {:repo-root "."
                 :on-chunk (fn [_ _] (when-not @seen (reset! seen (ui/console @a))))
                 :on-exit (fn [_]
                            (is (str/includes? @seen "partial")
                                "output was renderable while the command was still running")
                            (done))}))))

(deftest denial-starts-nothing
  (let [a (open-atom)
        out (sh/start a "t1" [node "-e" "process.stdout.write('NO')"]
                      {:repo-root "." :kuro/requires #{"secrets/get"}})]
    (is (false? (:kuro/allowed? out)))
    (is (nil? (:pid out)))
    (is (empty? (:kobo/running @a)))
    (is (= 1 (count (:kobo/denials @a))))))

(deftest kill-lands-a-receipt
  (async done
    (let [a (open-atom)
          h (sh/start a "t1" [node "-e" "setInterval(()=>{},1000)"]
                      {:repo-root "." :timeout-ms 10000
                       :on-exit (fn [_]
                                  (is (empty? (:kobo/running @a)))
                                  (is (= 1 (count (:kobo/receipts @a))))
                                  (done))})]
      (js/setTimeout #((:kill h)) 30))))

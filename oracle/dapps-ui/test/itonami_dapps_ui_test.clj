(ns itonami-dapps-ui-test
  "Structural oracle for the AWAI-2793 session UI twins: the .cljc facts
  must equal the .kotoba documents case for case. Run it with Babashka,
  one-shot, never from CI:
  bb -cp src:test test/itonami_dapps_ui_test.clj"
  (:require [clojure.test :refer [deftest is run-tests testing]]
            [clojure.string :as string]
            [clojure.set :as set]
            [itonami-dapps-ui :as ui]))

(deftest documents-mirror-the-kotoba-records
  (testing "id, title, lede, bind and note equal the .kotoba documents"
    (is (= {:id "sound" :title "Sound"
            :lede "音量とミュート。最後の設定が保存されます。"
            :bind "sound" :note "最後の設定が保存されます。"}
           (select-keys (first (filter #(= "sound" (:id %)) ui/documents))
                        [:id :title :lede :bind :note])))
    (is (= {:id "display" :title "Display"
            :lede "画面の明るさ。最後の設定が保存されます。"
            :bind "display" :note "最後の設定が保存されます。"}
           (select-keys (first (filter #(= "display" (:id %)) ui/documents))
                        [:id :title :lede :bind :note])))
    (is (= {:id "soshiki" :title "Soshiki"
            :lede "サークルとロールで組織を作り、Botにプロフィールを持たせる。"
            :bind "soshiki" :note "サークルとロールの概要をこのデバイスから読みます。"}
           (select-keys (first (filter #(= "soshiki" (:id %)) ui/documents))
                        [:id :title :lede :bind :note])))))

(deftest hiccup-carries-the-record-identity-and-bind
  (testing "every document renders its id, title, lede and data-bind"
    (doseq [{:keys [id title lede bind]} ui/documents]
      (let [html (pr-str (ui/hiccup id))]
        (is (string/includes? html id))
        (is (string/includes? html title))
        (is (string/includes? html lede))
        (is (string/includes? html bind))))))

(deftest classes-stay-inside-the-shared-set
  (testing "no document invents a stylesheet class"
    (is (= #{} (set/difference (ui/used-classes) ui/shared-classes)))))

(deftest styles-add-no-view-scoped-rules
  (testing "the Garden data stays empty"
    (is (= [] ui/styles))))

(deftest unknown-documents-refuse
  (testing "an id no record names is an error map, not a document"
    (is (= "unknown-document" (:error (ui/hiccup "no-such-dapp"))))))

(run-tests)

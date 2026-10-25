(ns hata.ui-test
  "UI への局所 API — 機 は entry と型を指示するだけで、表示は 宿 の仕事。"
  (:require #?(:clj [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing]])
            [hata.ui :as ui]))

(def bundle-with-ui
  {:manifest {:kotoba.app/id "itonami-hello"}
   :ui {:cid "bafyUi" :entry "index.html" :bytes "html-bytes"}})

(deftest the-ui-entry-names-what-to-open
  (is (= {:entry "index.html" :bytes "html-bytes"
          :content-type "text/html; charset=utf-8"}
         (ui/ui-entry bundle-with-ui))))

(deftest the-serve-plan-stays-on-the-local-origin
  (let [plan (ui/serve-plan bundle-with-ui :origin "http://127.0.0.1:51766")]
    (is (= "http://127.0.0.1:51766" (:origin plan)))
    (is (= "/index.html" (:path plan)))
    (is (= "itonami-hello" (:app-id plan)))))

(deftest a-ui-less-app-prepends-nothing
  (is (nil? (ui/ui-entry {:manifest {:kotoba.app/id "x"} :ui nil})))
  (is (nil? (ui/serve-plan {:manifest {:kotoba.app/id "x"}}))))

(deftest unknown-extensions-are-not-guessed
  (is (= "application/octet-stream"
         (:content-type (ui/ui-entry {:ui {:entry "art.bin" :bytes "b"}})))))

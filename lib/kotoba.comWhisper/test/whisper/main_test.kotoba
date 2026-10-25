(ns whisper.main-test
  (:require [clojure.test :refer [deftest is testing]]
            [whisper.main :as w]))

(deftest transcribe-materializes-final
  (testing "non-streaming transcribe emits namespaced facts + a final Transcription"
    (binding [w/*store* (atom {})]
      (let [{:keys [id entity facts]} (w/transcribe {:modelId "whisper_mod_1"
                                                      :text "予約をお願いします"})]
        (is (string? id))
        (is (true? (:final entity)))
        (is (= "予約をお願いします" (:text entity)))
        (is (some (fn [[_ a _]] (= a :whisper.Transcription/text)) facts))))))

(deftest transcribe-requires-model
  (testing "missing modelId is refused"
    (is (thrown? #?(:clj clojure.lang.ExceptionInfo :cljs cljs.core/ExceptionInfo)
                 (w/transcribe {:text "x"})))))

(deftest stream-emits-partials-then-final
  (testing "streaming yields partial segments (final=false) then one final transcription"
    (binding [w/*store* (atom {})]
      (let [{:keys [segments final]} (w/stream-transcribe {:modelId "whisper_mod_1"}
                                                          ["もしもし" "予約を" "お願いします"])]
        (is (= 3 (count segments)))
        (is (every? #(false? (:final %)) segments))
        (is (true? (:final final)))
        (is (= "もしもし 予約を お願いします" (:text final)))
        (is (every? #(= (:transcriptionId %) (:transcriptionId final)) segments))))))

(deftest solve-is-r0-gated
  (testing "live audio ingest raises at R0 (G7)"
    (is (thrown? #?(:clj clojure.lang.ExceptionInfo :cljs cljs.core/ExceptionInfo)
                 (w/solve {})))))

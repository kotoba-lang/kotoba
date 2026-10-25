(ns whisper.engine-test
  "The engine binding, and mostly one property.

  A telephone dialog reads an empty transcript as 'the caller said nothing' and
  acts on it. So the thing under test here is not that transcription works —
  that is measured against real audio on a fleet node, not asserted — but that
  **every way this can fail is distinguishable from a caller who stayed quiet**.
  A missing model, an absent engine, a crashed process and a silent room must not
  converge on the same value."
  (:require [clojure.test :refer [deftest is testing]]
            [whisper.engine :as engine]))

(defn- runner [result] (fn [_argv] result))

(def ^:private base
  {:model "/models/ggml-large-v3-turbo.bin" :audio "/tmp/call.wav"})

(defn- run-with [result & kvs]
  (engine/transcribe-file (merge base {:run (runner result)} (apply hash-map kvs))))

;; ── the property ─────────────────────────────────────────────────────────────

(deftest test-no-failure-mode-produces-a-transcript
  (doseq [[label result]
          [["no engine runner injected" (engine/transcribe-file base)]
           ["no model"    (engine/transcribe-file (assoc base :model "" :run (runner {:exit 0 :out "はい"})))]
           ["no audio"    (engine/transcribe-file (assoc base :audio "" :run (runner {:exit 0 :out "はい"})))]
           ["engine exited non-zero" (run-with {:exit 1 :err "failed to load model"})]
           ["engine produced nothing" (run-with {:exit 0 :out nil})]
           ["engine threw" (engine/transcribe-file (assoc base :run (fn [_] (throw (ex-info "boom" {})))))]]]
    (testing label
      (is (nil? (engine/transcript result)) "no words come out of a failure")
      (is (not (engine/heard? result)))
      (is (some? (:whisper/failed result)) "and the failure says which one it was"))))

(deftest test-a-crash-that-exits-zero-is-not-silence
  ;; Observed 2026-08-15, not imagined: a half-downloaded model made whisper-cli
  ;; abort with a stack trace on stderr and EXIT 0, printing nothing. The first
  ;; version of `parse` called that silence, and eight test utterances came back
  ;; as eight quiet callers with the crash invisible.
  (let [crashed (run-with {:exit 0 :out ""
                           :err "6 libsystem_c.dylib __cxa_finalize_ranges + 480"})]
    (is (= :engine-produced-no-transcript (:whisper/failed crashed)))
    (is (nil? (engine/transcript crashed)))
    (is (not (:whisper/silence crashed)) "empty output is not a statement of silence")
    (testing "and the stderr that said why is carried, not discarded"
      (is (re-find #"libsystem_c" (str (:whisper/detail crashed)))))))

(deftest test-silence-must-be-stated-by-the-engine
  (let [silent (run-with {:exit 0 :out "[BLANK_AUDIO]\n"})]
    (testing "a quiet caller is not a failure"
      (is (:whisper/silence silent))
      (is (nil? (:whisper/failed silent))))
    (testing "but is still not something a dialog may act on"
      (is (nil? (engine/transcript silent)))
      (is (not (engine/heard? silent))))
    (testing "and is distinguishable from every failure"
      (is (not= silent (run-with {:exit 1 :err "x"}))))))

(deftest test-transcript-is-never-an-empty-string
  (testing "an empty string is the value that would read as 'they said nothing'"
    (doseq [out ["" "   " "\n" "[BLANK_AUDIO]" "[Music]" "[ Silence ]"]]
      (is (not= "" (engine/transcript (run-with {:exit 0 :out out})))
          (str "out=" (pr-str out)))
      (is (nil? (engine/transcript (run-with {:exit 0 :out out})))))))

(deftest test-a-real-utterance-comes-through
  (let [r (run-with {:exit 0 :out "  予約をお願いします\n"})]
    (is (= "予約をお願いします" (engine/transcript r)))
    (is (engine/heard? r))))

(deftest test-engine-annotations-are-stripped-but-words-are-kept
  (is (= "はい お願いします"
         (engine/transcript (run-with {:exit 0 :out "[BLANK_AUDIO] はい  お願いします\n"})))))

;; ── the command ──────────────────────────────────────────────────────────────

(deftest test-language-is-stated-not-detected
  (testing "auto-detection on 'はい' produces confident nonsense rather than an error"
    (let [argv (engine/command (assoc base :language "ja"))]
      (is (some #{"-l"} argv))
      (is (some #{"ja"} argv))))
  (testing "and japanese is the default rather than auto"
    (is (some #{"ja"} (engine/command base)))))

(deftest test-the-command-names-the-model-and-the-audio
  (let [argv (engine/command base)]
    (is (some #{(:model base)} argv))
    (is (some #{(:audio base)} argv))))

;; ── the audio a telephone actually delivers ──────────────────────────────────

(deftest test-the-conversion-goes-from-carrier-format-to-engine-format
  (is (= {:codec :ulaw :sample-rate 8000 :channels 1} (:carrier engine/telephony-format)))
  (is (= {:codec :pcm-s16le :sample-rate 16000 :channels 1} (:engine engine/telephony-format)))
  (let [argv (engine/telephony-conversion "/tmp/in.wav" "/tmp/out.wav")]
    (is (some #{"LEI16@16000"} argv))
    (is (= "/tmp/out.wav" (last argv)))))

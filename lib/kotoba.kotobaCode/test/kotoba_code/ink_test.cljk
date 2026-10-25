(ns kotoba-code.ink-test
  (:require [kotoba-code.ink-runtime :as runtime]
            [kotoba-code.composer-input :as composer]
            [kotoba-code.slash-commands :as commands]
            [kotoba-code.ui-state :as state]))

(defn assert= [expected actual label]
  (when-not (= expected actual)
    (throw (js/Error. (str label ": expected " expected ", got " actual)))))

(defn -main []
  (let [submitted (state/reduce-event state/initial-state
                                      {:event/type :turn/submitted :text "hello"})
        started (state/reduce-event submitted
                                   {:event/type :tool/started :id "t1" :name "search"})
        completed (state/reduce-event started
                                     {:event/type :tool/completed :id "t1"
                                      :name "search" :summary "2 matches"})
        answered (state/reduce-event completed
                                    {:event/type :assistant/completed :text "hi"})]
    (assert= :working (:status submitted) "submitted status")
    (assert= :done (get-in completed [:tools 0 :status]) "tool status")
    (assert= :ready (:status answered) "answer status")
    (assert= "hi" (get-in answered [:messages 1 :text]) "answer text")
    (let [parser (atom {:tail "" :mode nil :answer [] :tool-ids {}
                        :stderr [] :diagnostics [] :failed? false})
          events (atom [])]
      (runtime/parse-output!
       parser
       "-- supervisor -- refusing task: loop status is interrupted. Use :resume to continue.\n"
       #(swap! events conj %))
      (assert= :turn/failed (:event/type (first @events)) "refusal event")
      (assert= true (:failed? @parser) "refusal failed state")
      (assert= true
               (boolean (re-find #"/resume" (:message (first @events))))
               "refusal resume hint"))
    (let [fallback (state/reduce-event
                    state/initial-state
                    {:event/type :model/fallback :model "openrouter/free"})]
      (assert= :system (get-in fallback [:messages 0 :role]) "fallback role")
      (assert= true
               (boolean (re-find #"openrouter/free"
                                 (get-in fallback [:messages 0 :text])))
               "fallback model message"))
    (assert= {:command "/codex" :args ["gpt-5.6-sol"]}
             (commands/parse-command "/codex gpt-5.6-sol")
             "command parsing")
    (assert= ["/claude"]
             (mapv :name (commands/suggestions "/clau"))
             "command suggestions")
    (assert= {:command "/subtask" :args ["inspect" "README.md"]}
             (commands/parse-command "/subtask inspect README.md")
             "subtask parsing")
    (assert= {:command "/subtask" :args ["--write" "fix" "README.md"]}
             (commands/parse-command "/subtask --write fix README.md")
             "write subtask parsing")
    (assert= ["/loop"]
             (mapv :name (commands/suggestions "/loo"))
             "loop suggestion")
    (assert= ["日" "本" "語" "👨‍👩‍👧‍👦" "a"]
             (composer/graphemes "日本語👨‍👩‍👧‍👦a")
             "grapheme segmentation")
    (let [{:keys [before cursor after left-clipped?]}
          (composer/viewport (composer/graphemes "日本語入力テスト") 8 10)]
      (assert= true left-clipped? "CJK viewport clips left")
      (assert= true
               (<= (+ (composer/width before)
                      (composer/width cursor)
                      (composer/width after)
                      1)
                   10)
               "CJK viewport stays within terminal columns"))
    (let [cleared (state/reduce-event
                   (assoc state/initial-state
                          :messages [{:role :user :text "old"}])
                   {:event/type :conversation/cleared})]
      (assert= [] (:messages cleared) "clear conversation"))
    (println "ink state tests passed")))

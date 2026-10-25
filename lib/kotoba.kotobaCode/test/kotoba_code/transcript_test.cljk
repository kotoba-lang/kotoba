(ns kotoba-code.transcript-test
  (:require [clojure.test :refer [deftest is]]
            [langchain.message :as msg]
            [kotoba-code.transcript :as transcript]))

(deftest extracts-tool-events-from-final-state
  (let [final {:messages [(msg/user "task")
                          (msg/ai "" {:tool-calls [{:id "t1"
                                                    :name "read_file"
                                                    :input {:path "src/x.clj"}}]})
                          (msg/tool-result "t1" "(ns x)\n(def x 1)")]}
        [event] (transcript/tool-events final)]
    (is (= :tool-call (:type event)))
    (is (= {:id "t1"
            :name "read_file"
            :input {:path {:text "src/x.clj" :chars 9}}
            :result-tail "(ns x)\n(def x 1)"
            :error? false}
           (:payload event)))
    (is (= 1 (transcript/tool-count final)))
    (is (= ["OK  read_file -> (ns x)\n(def x 1)"] (transcript/lines final)))))

(deftest transcript-redacts-secrets-from-inputs-and-results
  (let [final {:messages [(msg/user "task")
                          (msg/ai "" {:tool-calls [{:id "t1"
                                                    :name "shell"
                                                    :input {:command "echo ok"
                                                            :api_key "sk-or-secret"
                                                            :nested {:password "p4ss"}}}]})
                          (msg/tool-result "t1" "Authorization: Bearer sk-or-secret\ntoken=abc123\nok")]}
        [event] (transcript/tool-events final)
        payload (:payload event)]
    (is (= "[REDACTED]" (get-in payload [:input :api_key :text])))
    (is (= "[REDACTED]" (get-in payload [:input :nested :password :text])))
    (is (re-find #"\[REDACTED\]" (:result-tail payload)))
    (is (not (re-find #"sk-or-secret|abc123|p4ss" (pr-str event))))
    (is (not (re-find #"sk-or-secret|abc123|p4ss"
                      (str (transcript/lines final)))))))

(deftest transcript-summarizes-large-tool-inputs
  (let [huge (apply str (repeat 1000 "x"))
        final {:messages [(msg/user "task")
                          (msg/ai "" {:tool-calls [{:id "t1"
                                                    :name "write_file"
                                                    :input {:path "src/x.clj"
                                                            :content huge}}]})
                          (msg/tool-result "t1" "written src/x.clj")]}
        [event] (transcript/tool-events final)
        content (get-in event [:payload :input :content])]
    (is (= 1000 (:chars content)))
    (is (= true (:truncated? content)))
    (is (< (count (:text content)) 260))
    (is (not (re-find (re-pattern huge) (pr-str event))))))

(deftest transcript-classifies-tool-error-results-as-errors
  (let [final {:messages [(msg/user "task")
                          (msg/ai "" {:tool-calls [{:id "t1"
                                                    :name "replace_text"
                                                    :input {:path "src/x.clj"}}]})
                          (msg/tool-result "t1" "TOOL_ERROR: replace_text: missing required argument")]}
        [event] (transcript/tool-events final)]
    (is (= true (get-in event [:payload :error?])))
    (is (= ["ERR replace_text -> TOOL_ERROR: replace_text: missing required argument"]
           (transcript/lines final)))))

(deftest transcript-is-empty-without-tool-results
  (is (= [] (transcript/tool-events {:messages [(msg/user "task") (msg/ai "DONE")]})))
  (is (= 0 (transcript/tool-count nil))))

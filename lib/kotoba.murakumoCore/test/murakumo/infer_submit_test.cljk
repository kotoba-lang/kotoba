(ns murakumo.infer-submit-test
  "Offline tests for the qwen38-generate submit command. No network, no torch:
  the tokenizer is injected, so this whole namespace runs with
  `--classpath src:test` and nothing else."
  (:require [cljs.test :refer [async deftest is run-tests testing]]
            [murakumo.infer.submit :as submit]
            ["node:fs" :as fs]
            ["node:os" :as os]))

;; ── reading the prompt ──────────────────────────────────────────────────────

(deftest tokens-file-accepts-a-bare-vector-or-a-whole-job
  (is (= {:tokens [248044 9707]}
         (submit/parse-tokens-file "[248044 9707]")))
  (is (= {:tokens [1 2] :max-tokens 32 :stop-tokens [248046]}
         (submit/parse-tokens-file
          "{:tokens [1 2] :max-tokens 32 :stop-tokens [248046]}")))
  (testing "keys the job does not own are dropped rather than forwarded"
    (is (= {:tokens [1]}
           (submit/parse-tokens-file "{:tokens [1] :price 999 :kind \"other\"}"))))
  (testing "a file that is neither shape is refused where it is read"
    (is (thrown? js/Error (submit/parse-tokens-file "\"248044 9707\"")))
    (is (thrown? js/Error (submit/parse-tokens-file "42")))))

(deftest prompt-shape-is-checked-locally-but-bounds-are-the-server-s
  (is (submit/token-vector? [0 1 248319]))
  (testing "structural rejections happen before the request is built"
    (is (not (submit/token-vector? [])))
    (is (not (submit/token-vector? nil)))
    (is (not (submit/token-vector? [1 -1])))
    (is (not (submit/token-vector? [1 2.5])))
    (is (not (submit/token-vector? '(1 2))))
    (is (thrown? js/Error (submit/job-input {:tokens []} {}))))
  (testing "an id far past the vocabulary is NOT refused here -- the server
            owns that bound, and a second copy of it would drift"
    (is (submit/token-vector? [999999999]))
    (is (= [999999999] (:tokens (submit/job-input {:tokens [999999999]} {}))))))

;; ── the job that gets built ─────────────────────────────────────────────────

(deftest job-input-defaults-to-greedy-and-stops-at-eos
  (is (= {:tokens [248044 9707]
          :max-tokens 64
          :stop-tokens [248046]
          :temperature 0}
         (submit/job-input {:tokens [248044 9707]} {})))
  (testing "an explicit flag wins over the tokens file, which wins over the default"
    (is (= 32 (:max-tokens (submit/job-input {:tokens [1] :max-tokens 32} {}))))
    (is (= 8 (:max-tokens (submit/job-input {:tokens [1] :max-tokens 32}
                                            {:max-tokens "8"}))))
    (is (= [7 9] (:stop-tokens (submit/job-input {:tokens [1]}
                                                 {:stop-tokens "7,9"}))))
    (is (= [11] (:stop-tokens (submit/job-input {:tokens [1] :stop-tokens [11]}
                                                {})))))
  (testing "v3 is greedy: temperature is not a flag, it is a constant"
    (is (= 0 (:temperature (submit/job-input {:tokens [1]}
                                             {:temperature "0.7"}))))))

(deftest submit-body-carries-the-kind-and-the-placement-contract
  (let [input (submit/job-input {:tokens [1 2]} {})]
    (is (= {:kind "qwen38-generate" :price 1 :input input}
           (submit/submit-body input {})))
    (is (= {:kind "qwen38-generate" :price 5 :input input
            :target-did "did:key:z6MkAiueosK16"}
           (submit/submit-body input {:price "5"
                                      :target-did "did:key:z6MkAiueosK16"})))
    (testing "a job with only :prompt is not something this command can build"
      (is (thrown? js/Error (submit/job-input {:prompt "hello"} {}))))))

(deftest auth-is-cacao-or-bearer-and-an-explicit-flag-wins
  (is (= {:kind :bearer :credential "env"}
         (submit/control-auth {} {"MURAKUMO_SERVICE_TOKEN" "env"})))
  (is (= {:kind :cacao :credential "flag"}
         (submit/control-auth {:cacao "flag"} {"MURAKUMO_SERVICE_TOKEN" "env"})))
  (is (nil? (submit/control-auth {} {})))
  (is (= "Bearer t" (get (submit/auth-headers {:kind :bearer :credential "t"})
                         "authorization")))
  (is (= "CACAO c" (get (submit/auth-headers {:kind :cacao :credential "c"})
                        "authorization"))))

(deftest result-tokens-distinguishes-pending-from-an-empty-generation
  (is (= [2005 17] (submit/result-tokens {:output-tokens [2005 17]})))
  (testing "an aborted generation settled an empty array; that is not pending"
    (is (= [] (submit/result-tokens {:output-tokens [] :stop-reason "error"}))))
  (testing "a job with no array yet is pending"
    (is (nil? (submit/result-tokens {:text nil})))
    (is (nil? (submit/result-tokens {:error "result pending"})))))

;; ── the whole command, with fetch and the tokenizer injected ────────────────

(defn- recording-fetch
  "A fetch double that records calls and replays scripted responses."
  [calls responses]
  (fn [url options]
    (swap! calls conj {:url url
                       :method (.-method options)
                       :body (some-> (.-body options) js/JSON.parse
                                     (js->clj :keywordize-keys true))})
    (let [{:keys [status body]} (first @responses)]
      (swap! responses rest)
      (js/Promise.resolve
       #js {:status status
            :text (fn [] (js/Promise.resolve (js/JSON.stringify (clj->js body))))}))))

(deftest a-tokens-file-is-submitted-with-its-placement-contract
  (async done
    (let [path (str (.tmpdir os) "/murakumo-v3-tokens-" (js/Date.now) ".edn")
          _ (fs/writeFileSync path "{:tokens [248044 9707] :max-tokens 24}")
          calls (atom [])
          responses (atom [{:status 201 :body {:job-id "1788078031098390"}}])]
      (-> (submit/run!
           {:fetch (recording-fetch calls responses)
            :args ["--tokens-file" path
                   "--base" "https://api.example/"
                   "--target-did" "did:key:z6MkAiueosK16"]
            :env {"MURAKUMO_SERVICE_TOKEN" "t"}
            :log (fn [_])
            ;; --tokens-file wins; this encode must never be reached.
            :encode (fn [_ _] (throw (ex-info "tokenizer must not run" {})))})
          (.then
           (fn [outcome]
             (fs/unlinkSync path)
             (is (= :submitted outcome))
             (is (= 1 (count @calls)))
             (is (= {:kind "qwen38-generate"
                     :price 1
                     :input {:tokens [248044 9707]
                             :max-tokens 24
                             :stop-tokens [248046]
                             :temperature 0}
                     :target-did "did:key:z6MkAiueosK16"}
                    (:body (first @calls))))
             (is (= "https://api.example/infer/queue" (:url (first @calls))))
             (done)))))))

(deftest a-tokenized-prompt-becomes-the-job-input
  (async done
    (let [calls (atom [])
          responses (atom [{:status 201 :body {:job-id "42"}}])]
      (-> (submit/run!
           {:fetch (recording-fetch calls responses)
            :args ["--tokenize-with" "torch"
                   "--vocab-file" "/dev/null"
                   "--prompt" "hello"
                   "--max-tokens" "16"
                   "--base" "https://api.example"]
            :env {"MURAKUMO_SERVICE_TOKEN" "t"}
            :log (fn [_])
            :encode (fn [_vocab prompt]
                      (is (= "hello" prompt))
                      [248044 15339])})
          (.then
           (fn [outcome]
             (is (= :submitted outcome))
             (is (= 1 (count @calls)))
             (let [call (first @calls)]
               (is (= "https://api.example/infer/queue" (:url call)))
               (is (= "POST" (:method call)))
               (is (= {:kind "qwen38-generate"
                       :price 1
                       :input {:tokens [248044 15339]
                               :max-tokens 16
                               :stop-tokens [248046]
                               :temperature 0}}
                      (:body call))))
             (done)))))))

(deftest a-server-rejection-is-reported-verbatim-and-not-paraphrased
  (async done
    (let [literal ":input :tokens must all be below the 248320-entry vocabulary"
          calls (atom [])
          responses (atom [{:status 400 :body {:error literal}}])
          printed (atom [])]
      (-> (submit/run!
           {:fetch (recording-fetch calls responses)
            :args ["--tokenize-with" "torch" "--vocab-file" "/dev/null"
                   "--prompt" "x"]
            :env {"MURAKUMO_SERVICE_TOKEN" "t"}
            :log (fn [s] (swap! printed conj (str s)))
            :encode (fn [_ _] [999999])})
          (.then
           (fn [outcome]
             (is (= :rejected outcome))
             (is (some #(.includes % literal) @printed)
                 "the server's own literal must reach the operator")
             (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest waiting-polls-until-the-device-settles-the-array
  (async done
    (let [calls (atom [])
          responses (atom [{:status 201 :body {:job-id "42"}}
                           {:status 200
                            :body {:job-id "42"
                                   :output-tokens [2005 17 42]
                                   :output-sha256 "bfc850f9"
                                   :output-token-count 3
                                   :stop-reason "eos"
                                   :text nil}}])]
      (-> (submit/run!
           {:fetch (recording-fetch calls responses)
            :args ["--tokenize-with" "torch" "--vocab-file" "/dev/null"
                   "--prompt" "x" "--wait" "30" "--base" "https://api.example"]
            :env {"MURAKUMO_SERVICE_TOKEN" "t"}
            :log (fn [_])
            :encode (fn [_ _] [248044])})
          (.then
           (fn [outcome]
             (is (= :settled outcome))
             (is (= 2 (count @calls)))
             (is (= "https://api.example/infer/queue/42/result"
                    (:url (second @calls))))
             (done)))))))

(defmethod cljs.test/report [:cljs.test/default :end-run-tests] [m]
  (println (str "\n" (:test m) " tests, " (:pass m) " assertions, "
                (:fail m) " failures, " (:error m) " errors"))
  (when-not (cljs.test/successful? m) (js/process.exit 1)))

(run-tests)

(ns kotoba-code.agent-test
  "Proves the kotoba-code ReAct loop drives tools and the gate enforces green/rollback,
  using a deterministic mock model + an in-memory mock host (no network, no fs, no shell)."
  (:require [clojure.test :refer [deftest is testing]]
            [langchain.model :as model]
            [langchain.message :as msg]
            [kotoba-code.agent :as agent]
            [kotoba-code.gate :as gate]
            [kotoba-code.tools :as tools]))

(defn- mock-host [{:keys [test-output]}]
  (let [calls (atom [])]
    {:calls calls
     :read-file   (fn [p]   (swap! calls conj [:read p])  "(ns x)")
     :read-file-numbered (fn [p start end]
                           (swap! calls conj [:read-numbered p start end])
                           "    1 | (ns x)")
     :write-file  (fn [p _] (swap! calls conj [:write p]) (str "written " p))
     :apply-patch (fn [p]   (swap! calls conj [:patch p]) "patch applied")
     :replace-text (fn [p old new] (swap! calls conj [:replace p old new]) "replaced 1 occurrence")
     :replace-range (fn [p start end replacement]
                      (swap! calls conj [:replace-range p start end replacement])
                      "replaced lines")
     :run-clojure (fn [f]   (swap! calls conj [:clj f])   "nil")
     :run-tests   (fn []    (swap! calls conj [:test])    test-output)
     :list-dir    (fn [p]   (swap! calls conj [:ls p])    "src/\ntest/")
     :search      (fn [pat] (swap! calls conj [:search pat]) "src/demo/math.clj:4: (defn add …)")
     :git-status  (fn []    (swap! calls conj [:status]) " M src/x.clj")
     :git-diff    (fn []    (swap! calls conj [:diff])   "diff --git a/src/x.clj b/src/x.clj")
     :shell       (fn [cmd] (swap! calls conj [:shell cmd]) "shell output")
     :rollback    (fn []    (swap! calls conj [:rollback]) :rolled-back)}))

;; model that drives one tool call, then finishes once it has seen a tool result
(defn- one-tool-then-done [tool-name tool-input]
  (model/mock-model
   (fn [messages _opts]
     (if (some #(= :tool (:role %)) messages)
       (msg/ai "DONE")
       (msg/ai "" {:tool-calls [{:id "t1" :name tool-name :input tool-input}]})))))

(deftest react-loop-executes-a-tool-and-finishes
  (let [host  (mock-host {:test-output "Ran 1 tests containing 1 assertions.\n0 failures, 0 errors."})
        model (one-tool-then-done "run_tests" {})
        a     (agent/build-agent {:model model :host host})
        final (agent/run-task a "make the suite pass")
        roles (map :role (:messages final))]
    (testing "the loop actually executed a tool (a :tool message is present)"
      (is (some #(= :tool %) roles)))
    (testing "run_tests was invoked on the host"
      (is (some #(= [:test] %) @(:calls host))))
    (testing "the loop terminated with a final assistant answer"
      (is (re-find #"DONE" (agent/answer final))))))

(deftest gate-passes-when-suite-is-green
  (let [host  (mock-host {:test-output "Ran 3 tests containing 9 assertions.\n0 failures, 0 errors."})
        model (one-tool-then-done "run_tests" {})
        a     (agent/build-agent {:model model :host host})
        {:keys [green? rolled-back?]} (gate/run-gated a "task" host {})]
    (is (true? green?))
    (is (false? rolled-back?))
    (is (not (some #(= [:rollback] %) @(:calls host))) "no rollback on green")))

(deftest conversation-skips-test-gate
  (let [host (mock-host {:test-output "1 failures, 0 errors."})
        a (agent/build-agent {:model (model/mock-model [(msg/ai "Hello!")])
                              :host host})
        {:keys [green? gate-skipped? answer]} (gate/run-gated a "hello" host {})]
    (is (true? green?))
    (is (true? gate-skipped?))
    (is (= "Hello!" answer))
    (is (not (some #(= [:test] %) @(:calls host))))))

(deftest gate-rolls-back-when-suite-is-red
  (let [host  (mock-host {:test-output "Ran 2 tests containing 4 assertions.\n1 failures, 0 errors."})
        ;; model writes a (bad) file, then claims done
        model (one-tool-then-done "write_file" {:path "src/x.clj" :content "(ns x) bad"})
        a     (agent/build-agent {:model model :host host})
        {:keys [green? rolled-back?]} (gate/run-gated a "task" host {})]
    (is (false? green?))
    (is (true? rolled-back?))
    (is (some #(= [:rollback] %) @(:calls host)) "rollback fired on red")))

(deftest gate-reports-rollback-failure-on-red-suite
  (let [host  (assoc (mock-host {:test-output "Ran 2 tests containing 4 assertions.\n1 failures, 0 errors."})
                     :rollback (fn [] (throw (ex-info "rollback exploded" {}))))
        model (one-tool-then-done "write_file" {:path "src/x.clj" :content "(ns x) bad"})
        a     (agent/build-agent {:model model :host host})
        {:keys [green? rolled-back? rollback-error]} (gate/run-gated a "task" host {})]
    (is (false? green?))
    (is (true? rolled-back?))
    (is (= "rollback exploded" rollback-error))))

(deftest react-loop-can-drive-the-new-tools
  (let [host  (mock-host {:test-output "0 failures, 0 errors."})
        model (one-tool-then-done "list_dir" {:path "."})
        a     (agent/build-agent {:model model :host host})
        final (agent/run-task a "explore the project")]
    (is (some #(= :tool (:role %)) (:messages final)))
    (is (some #(= [:ls "."] %) @(:calls host)) "list_dir tool reached the host")))

(deftest tool-catalog-is-derived-from-tool-definitions-without-functions
  (let [catalog (tools/tool-catalog)
        replace-text (some #(when (= "replace_text" (:name %)) %) catalog)
        read-numbered (some #(when (= "read_file_numbered" (:name %)) %) catalog)
        list-dir (some #(when (= "list_dir" (:name %)) %) catalog)
        shell (some #(when (= "shell" (:name %)) %) catalog)]
    (is (seq catalog))
    (is (every? #(not (contains? % :fn)) catalog))
    (is (= :edit (:kind replace-text)))
    (is (= ["path" "old" "new"] (get-in replace-text [:schema :required])))
    (is (= 200000 (get-in replace-text [:limits :max-replacement-bytes])))
    (is (= true (get-in replace-text [:limits :exactly-one-occurrence?])))
    (is (= 400 (get-in read-numbered [:limits :max-lines])))
    (is (= 400 (get-in list-dir [:limits :max-entries])))
    (is (seq (:notes shell)))
    (is (some #{:shell-metacharacters} (get-in shell [:limits :rejects])))
    (is (= true (:restricted? shell)))))

(deftest tool-functions-validate-required-args-before-host-call
  (let [calls (atom [])
        host (assoc (mock-host {:test-output "0 failures, 0 errors."})
                    :replace-text (fn [& args]
                                    (swap! calls conj args)
                                    "should not happen"))
        replace-text (:fn (some #(when (= "replace_text" (:name %)) %)
                                (tools/coding-tools host)))]
    (let [out (replace-text {:path "src/x.clj" :old "a"})]
      (is (re-find #"TOOL_ERROR: replace_text" out))
      (is (re-find #"missing required argument" out))
      (is (re-find #"\"new\"" out)))
    (is (empty? @calls))))

(deftest tool-functions-normalize-string-keys
  (let [host (mock-host {:test-output "0 failures, 0 errors."})
        replace-text (:fn (some #(when (= "replace_text" (:name %)) %)
                                (tools/coding-tools host)))]
    (is (= "replaced 1 occurrence"
           (replace-text {"path" "src/x.clj"
                          "old" "a"
                          "new" "b"})))
    (is (some #(= [:replace "src/x.clj" "a" "b"] %)
              @(:calls host)))))

(deftest tool-functions-validate-types-and-minimum-before-host-call
  (let [calls (atom [])
        host (assoc (mock-host {:test-output "0 failures, 0 errors."})
                    :replace-range (fn [& args]
                                     (swap! calls conj args)
                                     "should not happen"))
        replace-range (:fn (some #(when (= "replace_range" (:name %)) %)
                                 (tools/coding-tools host)))]
    (let [out (replace-range {:path "src/x.clj"
                              :start_line 0
                              :end_line 1
                              :replacement "x"})]
      (is (re-find #"TOOL_ERROR: replace_range" out))
      (is (re-find #"start_line" out))
      (is (re-find #"minimum 1" out)))
    (let [out (replace-range {:path "src/x.clj"
                              :start_line "1"
                              :end_line 1
                              :replacement "x"})]
      (is (re-find #"TOOL_ERROR: replace_range" out))
      (is (re-find #"start_line" out))
      (is (re-find #"integer" out)))
    (is (empty? @calls))))

(deftest tool-functions-validate-max-length-before-host-call
  (let [calls (atom [])
        host (assoc (mock-host {:test-output "0 failures, 0 errors."})
                    :write-file (fn [& _]
                                  (swap! calls conj :write)
                                  "written")
                    :search (fn [& _]
                              (swap! calls conj :search)
                              "found"))
        write-file (:fn (some #(when (= "write_file" (:name %)) %)
                               (tools/coding-tools host)))
        search (:fn (some #(when (= "search" (:name %)) %)
                           (tools/coding-tools host)))
        huge (apply str (repeat 200001 "x"))]
    (let [out (write-file {:path "src/x.clj" :content huge})]
      (is (re-find #"TOOL_ERROR: write_file" out))
      (is (re-find #"content" out))
      (is (re-find #"maxLength 200000" out)))
    (let [out (search {:pattern (apply str (repeat 1001 "x"))})]
      (is (re-find #"TOOL_ERROR: search" out))
      (is (re-find #"pattern" out))
      (is (re-find #"maxLength 1000" out)))
    (is (= [] @calls))))

(deftest tool-functions-reject-unknown-args-before-host-call
  (let [calls (atom [])
        host (assoc (mock-host {:test-output "0 failures, 0 errors."})
                    :replace-text (fn [& args]
                                    (swap! calls conj args)
                                    "should not happen"))
        replace-text (:fn (some #(when (= "replace_text" (:name %)) %)
                                (tools/coding-tools host)))]
    (let [out (replace-text {:path "src/x.clj"
                             :old "a"
                             :new "b"
                             :newline "typo"})]
      (is (re-find #"TOOL_ERROR: replace_text" out))
      (is (re-find #"unknown argument" out))
      (is (re-find #"newline" out)))
    (is (empty? @calls))))

(deftest tool-functions-return-tool-error-on-host-exception
  (let [host (assoc (mock-host {:test-output "0 failures, 0 errors."})
                    :read-file (fn [_]
                                 (throw (ex-info "disk went away" {}))))
        read-file (:fn (some #(when (= "read_file" (:name %)) %)
                              (tools/coding-tools host)))
        out (read-file {:path "src/x.clj"})]
    (is (re-find #"TOOL_ERROR: read_file" out))
    (is (re-find #"disk went away" out))))

(deftest react-loop-survives-malformed-tool-arguments
  (let [host (mock-host {:test-output "0 failures, 0 errors."})
        model (model/mock-model
               (fn [messages _opts]
                 (if (some #(and (= :tool (:role %))
                                 (re-find #"TOOL_ERROR" (str (msg/text %))))
                           messages)
                   (msg/ai "DONE")
                   (msg/ai "" {:tool-calls [{:id "bad-call"
                                             :name "replace_text"
                                             :input {:path "src/x.clj"
                                                     :old "a"}}]}))))
        a (agent/build-agent {:model model :host host})
        final (agent/run-task a "recover from malformed tool args")]
    (is (re-find #"DONE" (agent/answer final)))
    (is (empty? @(:calls host)) "invalid args never reached host I/O")))

(deftest react-loop-can-drive-patch-and-git-tools
  (doseq [[tool input expected] [["apply_patch" {:patch "diff --git a/src/x.clj b/src/x.clj"} :patch]
                                 ["read_file_numbered" {:path "src/x.clj" :start_line 1 :end_line 3}
                                  :read-numbered]
                                 ["replace_text" {:path "src/x.clj" :old "a" :new "b"} :replace]
                                 ["replace_range" {:path "src/x.clj" :start_line 1 :end_line 1
                                                   :replacement "b"} :replace-range]
                                 ["git_status" {} :status]
                                 ["git_diff" {} :diff]
                                 ["shell" {:command "rg foo"} :shell]]]
    (let [host  (mock-host {:test-output "0 failures, 0 errors."})
          model (one-tool-then-done tool input)
          a     (agent/build-agent {:model model :host host})]
      (agent/run-task a (str "use " tool))
      (is (some #(= expected (first %)) @(:calls host)) (str tool " reached host")))))

(deftest gate-feedback-loop-recovers-a-red-then-green
  ;; round 1 leaves the suite red; the failure is fed back and round 2 turns it green.
  ;; (the model just calls run_tests; the host returns red first, green after.)
  (let [outs  (atom ["1 failures, 0 errors." "0 failures, 0 errors."])
        calls (atom [])
        host  {:read-file (fn [_] "x") :write-file (fn [p _] (str "w " p))
               :run-clojure (fn [_] "nil")
               :run-tests (fn [] (swap! calls conj :test) (let [o (first @outs)] (swap! outs rest) o))
               :rollback (fn [] (swap! calls conj :rollback) :rb)
               :list-dir (fn [_] "") :search (fn [_] "")
               :read-file-numbered (fn [_ _ _] "")
               :apply-patch (fn [_] "patch applied")
               :replace-text (fn [_ _ _] "replaced")
               :replace-range (fn [_ _ _ _] "replaced")
               :git-status (fn [] "")
               :git-diff (fn [] "")
               :shell (fn [_] "")}
        ;; model edits a file then DONEs each round; the gate (not the model) runs tests,
        ;; so run-tests is consumed only by the gate: round1 red, round2 green.
        model (model/mock-model
               (fn [messages _]
                 (if (some #(= :tool (:role %)) messages)
                   (msg/ai "DONE")
                   (msg/ai "" {:tool-calls [{:id "t" :name "write_file"
                                             :input {:path "src/x.clj" :content "x"}}]}))))
        a     (agent/build-agent {:model model :host host})
        {:keys [green? rounds]} (gate/run-gated a "make it pass" host {:rounds 3})]
    (is (true? green?) "second round goes green")
    (is (= 2 rounds) "took 2 rounds")
    (is (not (some #{:rollback} @calls)) "no rollback once green")))

(deftest gate-rolls-back-when-agent-throws
  ;; a crashing agent loop (e.g. model error after retries) must still roll back —
  ;; otherwise partial edits leak into the next run (the Phase 2c segment-44 leak).
  (let [host  (mock-host {:test-output "0 failures, 0 errors."})
        model (model/mock-model
               (fn [_ _] (throw (ex-info "model error after retries" {:status 503}))))
        a     (agent/build-agent {:model model :host host})
        {:keys [green? error]} (gate/run-gated a "task" host {})]
    (is (false? green?))
    (is (= "model error after retries" error))
    (is (some #(= [:rollback] %) @(:calls host)) "rollback fired on agent throw")))

(deftest gate-preserves-agent-error-when-rollback-fails
  (let [host  (assoc (mock-host {:test-output "0 failures, 0 errors."})
                     :rollback (fn [] (throw (ex-info "rollback exploded" {}))))
        model (model/mock-model
               (fn [_ _] (throw (ex-info "model error after retries" {:status 503}))))
        a     (agent/build-agent {:model model :host host})
        {:keys [green? error rolled-back? rollback-error]} (gate/run-gated a "task" host {})]
    (is (false? green?))
    (is (= "model error after retries" error))
    (is (true? rolled-back?))
    (is (= "rollback exploded" rollback-error))))

(deftest green?-detects-suite-state
  (is (gate/green? "Ran 1 tests containing 1 assertions.\n0 failures, 0 errors."))
  (is (not (gate/green? "Ran 1 tests containing 1 assertions.\n1 failures, 0 errors.")))
  (is (not (gate/green? nil))))

(deftest green?-rejects-failure-counts-ending-in-zero
  (is (not (gate/green? "Ran 40 tests containing 120 assertions.\n10 failures, 0 errors."))
      "regression: green? used an unanchored `0 failures,\\s*0 errors` literal
       substring match -- \"10 failures, 0 errors\" contains that exact
       substring, so a genuinely RED suite with a failure count ending in
       0 was misreported as green, silently disabling run-gated's rollback
       safety net")
  (is (not (gate/green? "Ran 400 tests.\n20 failures, 0 errors.")))
  (is (not (gate/green? "Ran 4000 tests.\n100 failures, 0 errors.")))
  (is (not (gate/green? "0 failures, 5 errors.")) "an all-zero-EXCEPT-errors count must also be red")
  (is (gate/green? "0 failures, 0 error.") "singular \"error\" phrasing is still recognized"))

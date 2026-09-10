(ns kotoba.doctor-test
  "Controls for the repairs `kotoba doctor` applies.

   Every test here is a PAIR: the repair must fire in one direction and stand
   down in the other. A control that only demonstrates the wanted outcome
   cannot tell a working repair from one that always says yes -- which is the
   failure mode CLAUDE.md's sixth question is about, and which this session
   walked into twice while writing the thing being tested.

   Runs JVM-free under nbb:
     nbb --classpath src:test -e \"(require '[kotoba.doctor-test])(kotoba.doctor-test/run)\""
  (:require [clojure.test :refer [deftest is testing run-tests]]
            [kotoba.doctor :as doc]
            [kotoba.adl.reader :as r]))

(def ^:private only-fns
  "(ns m ...)\n\n(defn twice [x :i64] :i64 (* x 2))\n")

(def ^:private with-value
  "(ns m ...)\n\n(def answer 42)\n\n(defn twice [x :i64] :i64 (* x 2))\n")

(def ^:private private-only
  "(ns m ...)\n\n(defn- helper [x :i64] :i64 x)\n")

(def ^:private meta-private
  "(ns m ...)\n\n(defn ^:private helper [x :i64] :i64 x)\n\n(defn twice [x :i64] :i64 (* x 2))\n")

(def ^:private private-word-in-a-docstring
  "(ns m ...)\n\n(defn twice \"mentions ^:private in prose\" [x :i64] :i64 (* x 2))\n")

(def ^:private no-ns
  "(defn twice [x :i64] :i64 (* x 2))\n")

(def ^:private trailing-trivia-in-ns
  "The shape kotoba.set.union actually has: the ns form's last non-trivia
   child is the docstring, and there is whitespace between it and the closing
   paren. Every fixture above happens to end its ns form flush, so an
   insertion that DROPS the children after the insertion point passes all of
   them -- measured 2026-09-10 by mutation, and it was the one mutation of
   four the controls did not catch."
  "(ns m\n  \"doc\"\n  )\n\n(defn twice [x :i64] :i64 (* x 2))\n")

(defn- nodes [txt] (r/read-cst txt :source))

;; ---------------------------------------------------------------- surface

(deftest public-definitions-separates-functions-from-values
  (testing "a def constant is reported, never quietly folded in with the fns"
    ;; amu, measured 2026-09-10: `answer is a def constant, not a function`.
    ;; The repair has to see the difference to be able to refuse.
    (is (= {:functions ["twice"] :values []} (doc/public-definitions (nodes only-fns))))
    (is (= {:functions ["twice"] :values ["answer"]}
           (doc/public-definitions (nodes with-value))))))

(deftest privacy-is-read-off-the-cst-not-the-text
  (testing "defn- and ^:private are excluded"
    (is (= [] (:functions (doc/public-definitions (nodes private-only)))))
    (is (= ["twice"] (:functions (doc/public-definitions (nodes meta-private))))))
  (testing "and the same words INSIDE A STRING exclude nothing"
    ;; The other half, and the one that catches a text scan. Without it a
    ;; scanner that greps for ^:private passes the test above and silently
    ;; unpublishes any function whose docstring mentions the word.
    (is (= ["twice"]
           (:functions (doc/public-definitions (nodes private-word-in-a-docstring)))))))

;; ---------------------------------------------------------------- repair

(deftest repair-adds-the-vector-it-computed
  (let [out (doc/repair-missing-export only-fns)]
    (is (= ["twice"] (:names out)))
    (is (re-find #"\(:export \[twice\]\)" (:text out)))))

(deftest repair-refuses-rather-than-narrowing-the-public-surface
  (testing "a public def is a refusal, not an export vector without it"
    ;; Emitting (:export [twice]) here would produce a module that links and
    ;; publishes less than the source did.
    (is (= {:skip :public-def-is-not-a-function} (doc/repair-missing-export with-value))))
  (testing "nothing public is a refusal, not (:export [])"
    ;; (:export []) satisfies amu's presence check while publishing nothing --
    ;; passing a gate by shrinking what it asks for.
    (is (= {:skip :no-public-definitions} (doc/repair-missing-export private-only))))
  (testing "no ns form is a refusal"
    (is (= {:skip :no-ns-form} (doc/repair-missing-export no-ns)))
    (is (nil? (doc/insert-export (nodes no-ns) ["twice"])))))

(deftest repair-touches-nothing-outside-the-ns-form
  (testing "removing the inserted clause returns the original, byte for byte"
    ;; The repair claims to carry every other byte across untouched. This is
    ;; that claim, checked -- not `the output looks right`.
    (let [out (doc/repair-missing-export only-fns)
          undone (clojure.string/replace (:text out) "\n  (:export [twice])" "")]
      (is (= only-fns undone))
      (is (not= only-fns (:text out))))))

(deftest repair-keeps-the-bytes-after-the-insertion-point
  (testing "trivia between the last clause and the closing paren survives"
    (let [out (doc/repair-missing-export trailing-trivia-in-ns)
          undone (clojure.string/replace (:text out) "\n  (:export [twice])" "")]
      (is (= trailing-trivia-in-ns undone))
      ;; And the clause really did land inside the ns form, not after it.
      (is (re-find #"\(ns m[\s\S]*\(:export \[twice\]\)[\s\S]*\)\s*\n\n\(defn" (:text out))))))

(deftest fidelity-check-answers-both-ways
  (is (true? (doc/fidelity-ok? only-fns)))
  ;; Unreadable source must answer false, not throw and not true.
  (is (false? (doc/fidelity-ok? "(ns m"))))

;; ---------------------------------------------------------------- verdict

(def ^:private missing {:ok? false :message doc/export-missing :source "m.kotoba"})

(deftest repair-progressed-discriminates
  (testing "the same finding, still about this file, is NO progress"
    ;; The arm that makes the whole thing honest: without it the doctor would
    ;; keep every edit it made, which is edit-and-hope.
    (is (false? (boolean (doc/repair-progressed? missing missing "m.kotoba")))))
  (testing "admitted is progress"
    (is (true? (boolean (doc/repair-progressed? missing {:ok? true} "m.kotoba")))))
  (testing "a different finding is progress"
    ;; Measured 2026-09-10: kotoba.set.union goes from this class to
    ;; `variadic parameters are outside the multi-arity profile`. Requiring a
    ;; clean file instead would have reverted that correct repair.
    (is (true? (boolean (doc/repair-progressed?
                         missing
                         {:ok? false :message "variadic parameters are outside the multi-arity profile"
                          :source "union.kotoba"}
                         "union.kotoba")))))
  (testing "the same finding authored about ANOTHER file is progress"
    (is (true? (boolean (doc/repair-progressed?
                         missing
                         (assoc missing :source "source.kotoba")
                         "m.kotoba")))))
  (testing "and a missing :source does not turn a stuck file into progress"
    ;; :source is necessary and not sufficient -- amu does not always author
    ;; the diagnostic against the module that actually lacks the vector. When
    ;; it is absent the predicate must fall back to `no progress`, not admit.
    (is (false? (boolean (doc/repair-progressed?
                          missing (dissoc missing :source) "m.kotoba"))))))

(defn run [] (run-tests 'kotoba.doctor-test))

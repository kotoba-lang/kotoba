(ns kotoba.gitoffice-test
  "Round-trip + invariant tests for the GitOffice Phase 0 converters.
   Run: bb test  (from this dir)."
  (:require [clojure.test :refer [deftest is testing run-tests]]
            [kotoba.gitoffice :as g]))

;; ---------------------------------------------------------------------------
;; fractional indexing
;; ---------------------------------------------------------------------------

(deftest order-strictly-increasing
  (let [ks (g/initial-orders 50)]
    (is (= 50 (count ks)))
    (is (= ks (sort ks)) "initial order keys are lexicographically increasing")
    (is (apply distinct? ks) "no duplicate order keys")))

(deftest order-between-rejects-noncanonical
  (testing "trailing-zero / empty / non-ascending keys are rejected, not silently corrupted"
    (is (thrown? clojure.lang.ExceptionInfo (g/order-between "1" "10")))  ; trailing-zero upper
    (is (thrown? clojure.lang.ExceptionInfo (g/order-between "10" nil)))  ; trailing-zero lower
    (is (thrown? clojure.lang.ExceptionInfo (g/order-between "" "")))     ; empty upper
    (is (thrown? clojure.lang.ExceptionInfo (g/order-between "b" "a")))   ; non-ascending
    (testing "canonical keys with a shared prefix still work"
      (let [k (g/order-between "1" "11")]
        (is (< (compare "1" k) 0))
        (is (< (compare k "11") 0))))))

(deftest order-between-inserts
  (testing "a key can always be inserted between two adjacent keys"
    (let [[a b] (g/initial-orders 2)
          mid   (g/order-between a b)]
      (is (< (compare a mid) 0))
      (is (< (compare mid b) 0)))
    (testing "repeated head-inserts stay ordered"
      (let [b (first (g/initial-orders 1))
            k1 (g/order-between nil b)
            k2 (g/order-between nil k1)]
        (is (< (compare k1 b) 0))
        (is (< (compare k2 k1) 0))))))

;; ---------------------------------------------------------------------------
;; A1 notation
;; ---------------------------------------------------------------------------

(deftest a1-roundtrip
  (is (= "A" (g/col->a1 0)))
  (is (= "B" (g/col->a1 1)))
  (is (= "Z" (g/col->a1 25)))
  (is (= "AA" (g/col->a1 26)))
  (is (= "AB" (g/col->a1 27)))
  (doseq [c [0 1 25 26 27 51 52 700]]
    (is (= c (g/a1->col (g/col->a1 c))) (str "col " c " round-trips")))
  (is (= "Sheet1!B2" (g/cell-id "Sheet1" 1 1))))

;; ---------------------------------------------------------------------------
;; docs: bodyJson <-> blocks
;; ---------------------------------------------------------------------------

(def sample-body
  [{:elementId "el0" :kind "heading" :headingLevel 1 :text "概要"}
   {:elementId "el1" :kind "paragraph" :text "原材料費が上昇した。"}
   {:elementId "el2" :kind "listItem" :text "項目A"}
   {:elementId "el3" :kind "paragraph" :text ""}])

(deftest body-roundtrip
  (let [ds (g/body->blocks "doc1" sample-body)
        b' (g/blocks->body ds "doc1")]
    (is (= sample-body b') "bodyJson -> blocks -> bodyJson is identity")
    (testing "blocks are children of the doc with a heading-level only where present"
      (is (= "doc1" (g/v-one ds "el1" :block/parent)))
      (is (= 1 (g/v-one ds "el0" :block/heading-level)))
      (is (nil? (g/v-one ds "el1" :block/heading-level))))))

(deftest body-normalize-idempotent
  (testing "re-normalizing keeps the same stable block ids (elementId)"
    (let [ds1 (g/body->blocks "doc1" sample-body)
          b'  (g/blocks->body ds1 "doc1")
          ds2 (g/body->blocks "doc1" b')]
      (is (= (set ds1) (set ds2))))))

;; ---------------------------------------------------------------------------
;; sheets: gridJson <-> cells
;; ---------------------------------------------------------------------------

(def sample-grid
  {"Sheet1" [["売上" "Q1" "Q2"]
             ["製品A" "100" "120"]
             ["製品B" "" "80"]]})

(deftest grid-roundtrip
  (let [ds (g/grid->cells "book1" sample-grid)
        g' (g/cells->grid ds "book1")]
    (is (= (update sample-grid "Sheet1" g/trim-grid) g')
        "gridJson -> sparse cells -> gridJson equals the trimmed grid")
    (testing "cells are sparse (the empty B3 is not stored)"
      (is (nil? (g/v-one ds "Sheet1!B3" :cell/value)))
      (is (= "120" (g/v-one ds "Sheet1!C2" :cell/value))))))

(deftest grid-trailing-empties-trim
  (testing "trailing empty rows/cols are dropped by the sparse canonical form"
    (let [grid {"S" [["x" "" ""] ["" "" ""]]}
          ds   (g/grid->cells "bk" grid)
          g'   (g/cells->grid ds "bk")]
      (is (= {"S" [["x"]]} g')))))

;; ---------------------------------------------------------------------------
;; revision <-> commit bridge
;; ---------------------------------------------------------------------------

(deftest rev-roundtrip
  (is (= 7 (g/parse-rev "rev-7")))
  (is (= 7 (g/parse-rev "7")))
  (let [r {:id "r1" :of "doc1" :label "rev-3" :seq 3 :commit "bafy..."}
        ds (g/rev->datoms r)]
    (is (= r (g/datoms->rev ds "r1")))
    (testing "commit is optional before commit() runs"
      (let [r2 {:id "r2" :of "doc1" :label "rev-0" :seq 0}]
        (is (= r2 (g/datoms->rev (g/rev->datoms r2) "r2")))))))

;; ---------------------------------------------------------------------------
;; collaboration metadata <-> datoms
;; ---------------------------------------------------------------------------

(deftest issue-roundtrip
  (let [i {:id "i1" :repo "repo1" :number 1 :title "色が崩れる"
           :body "スライド3の表" :author "did:key:zAlice" :state :issue.state/open
           :created-at 1719100000000 :labels #{"bug" "slides"}
           :anchors #{"ocz1:abc"}}]
    (is (= i (g/datoms->issue (g/issue->datoms i) "i1")))))

(deftest pr-roundtrip
  (let [p {:id "pr1" :repo "repo1" :number 2 :title "色を修正"
           :author "did:key:zBob" :base-ref "refs/heads/main"
           :head-ref "refs/heads/fix-color" :base-commit "bafyBASE"
           :head-commit "bafyHEAD" :merge-base "bafyMB" :state :pr.state/open
           :closes-issues #{"i1"}}]
    (is (= p (g/datoms->pr (g/pr->datoms p) "pr1"))))
  (testing "optional merge-base/merged-commit omitted"
    (let [p {:id "pr2" :repo "repo1" :number 3 :title "x" :author "did:key:zC"
             :base-ref "refs/heads/main" :head-ref "refs/heads/y"
             :base-commit "b" :head-commit "h" :state :pr.state/draft
             :closes-issues #{}}]
      (is (= p (g/datoms->pr (g/pr->datoms p) "pr2"))))))

(deftest review-roundtrip
  (let [r {:id "rv1" :pr "pr1" :reviewer "did:key:zCarol"
           :state :review.state/approved :at-commit "bafyHEAD" :vc "bafyVC"}]
    (is (= r (g/datoms->review (g/review->datoms r) "rv1")))))

(deftest comment-roundtrip
  (let [c {:id "c1" :on "pr1" :author "did:key:zCarol"
           :body "ここは赤すぎる" :anchor "ocz1:abc" :side :side/head
           :resolved false :created-at 1719100001000}]
    (is (= c (g/datoms->comment (g/comment->datoms c) "c1")))))

;; ---------------------------------------------------------------------------
;; cross-cutting invariant: a normalized doc round-trips THROUGH the blob the
;; deployed app stores, with the collaboration layer attached but separable.
;; ---------------------------------------------------------------------------

(deftest stale-review-detectable
  (testing "an approval at an old head is distinguishable from one at the current head"
    (let [pr  (g/pr->datoms {:id "pr1" :repo "r" :number 1 :title "t"
                             :author "did:key:zB" :base-ref "refs/heads/main"
                             :head-ref "refs/heads/x" :base-commit "b"
                             :head-commit "HEAD2" :state :pr.state/open
                             :closes-issues #{}})
          rv  (g/review->datoms {:id "rv1" :pr "pr1" :reviewer "did:key:zC"
                                 :state :review.state/approved :at-commit "HEAD1"})
          ds  (into pr rv)
          head (g/v-one ds "pr1" :pr/head-commit)
          approved-at (g/v-one ds "rv1" :review/at-commit)]
      (is (not= head approved-at) "review.at-commit != pr.head-commit => stale"))))

(defn -main []
  (let [{:keys [fail error]} (run-tests 'kotoba.gitoffice-test)]
    (+ (or fail 0) (or error 0))))

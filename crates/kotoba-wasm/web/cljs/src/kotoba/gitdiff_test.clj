(ns kotoba.gitdiff-test
  "Tests for the GitOffice Phase 1 semantic differ + merge-base/LCA."
  (:require [clojure.test :refer [deftest is testing run-tests]]
            [kotoba.gitoffice :as g]
            [kotoba.gitdiff :as d]))

;; ---------------------------------------------------------------------------
;; docs diff: add / remove / move / modify on real normalized blocks
;; ---------------------------------------------------------------------------

(def base-body
  [{:elementId "a" :kind "heading" :headingLevel 1 :text "概要"}
   {:elementId "b" :kind "paragraph" :text "原材料費が上昇した。"}
   {:elementId "c" :kind "paragraph" :text "結論。"}])

(deftest doc-diff-detects-each-kind
  (let [base (g/body->blocks "doc1" base-body)
        ;; head: edit b's text, drop c, add d, and reorder (move heading a after b)
        head-body [{:elementId "b" :kind "paragraph" :text "原材料費が大きく上昇した。"}
                   {:elementId "a" :kind "heading" :headingLevel 1 :text "概要"}
                   {:elementId "d" :kind "paragraph" :text "新しい段落。"}]
        head (g/body->blocks "doc1" head-body)
        diff (d/diff-doc base head "doc1")]
    (is (= #{"d"} (set (map :id (:added diff)))))
    (is (= #{"c"} (set (map :id (:removed diff)))))
    (is (= #{"a"} (set (map :id (:moved diff)))) "a only moved (order-only change)")
    (is (= #{"b"} (set (map :id (:modified diff)))) "b text changed")
    (testing "modified carries the text delta"
      (let [m (first (:modified diff))]
        (is (= ["原材料費が上昇した。" "原材料費が大きく上昇した。"]
               (get-in m [:deltas :text])))))))

(deftest doc-diff-empty-when-identical
  (let [base (g/body->blocks "doc1" base-body)]
    (is (d/empty-diff? (d/diff-doc base base "doc1")))))

(deftest move-vs-modify-distinguished
  (testing "a block that both moves and edits is :modified (not :moved)"
    (let [base (g/body->blocks "doc1"
                               [{:elementId "x" :kind "paragraph" :text "one"}
                                {:elementId "y" :kind "paragraph" :text "two"}])
          head (g/body->blocks "doc1"
                               [{:elementId "y" :kind "paragraph" :text "two!"}
                                {:elementId "x" :kind "paragraph" :text "one"}])
          diff (d/diff-doc base head "doc1")]
      (is (= #{"x"} (set (map :id (:moved diff)))) "x moved only")
      (is (= #{"y"} (set (map :id (:modified diff)))) "y moved+edited -> modified")
      (is (contains? (:deltas (first (:modified diff))) :order)
          "modified deltas include the order change too"))))

;; ---------------------------------------------------------------------------
;; sheets diff: cell add / remove / modify (no move concept — id is positional)
;; ---------------------------------------------------------------------------

(deftest sheet-diff-cellwise
  (let [base (g/grid->cells "bk" {"S" [["10" "20"] ["30" "40"]]})
        head (g/grid->cells "bk" {"S" [["10" "25"]      ; B1 20->25
                                       ["30" ""]         ; B2 40-> removed (empty)
                                       ["50" "60"]]})    ; A3,B3 added
        diff (d/diff-sheet base head "bk")]
    (is (= #{"S!A3" "S!B3"} (set (map :id (:added diff)))))
    (is (= #{"S!B2"} (set (map :id (:removed diff)))))
    (is (= #{"S!B1"} (set (map :id (:modified diff)))))
    (is (empty? (:moved diff)) "cells never 'move' — position is identity")
    (is (= ["20" "25"] (get-in (first (:modified diff)) [:deltas :value])))))

;; ---------------------------------------------------------------------------
;; merge-base / LCA over a commit DAG
;; ---------------------------------------------------------------------------

;;        c0
;;        |
;;        c1
;;       /  \
;;     c2    c3      (feature branch c3..c5 ; main c2..c4)
;;     |     |
;;     c4    c5
(def dag
  {"c0" {:parents []}
   "c1" {:parents ["c0"]}
   "c2" {:parents ["c1"]}
   "c3" {:parents ["c1"]}
   "c4" {:parents ["c2"]}
   "c5" {:parents ["c3"]}})

(deftest commit-ancestors-walk
  (is (= #{"c4" "c2" "c1" "c0"} (d/commit-ancestors dag "c4")))
  (is (= #{"c0"} (d/commit-ancestors dag "c0"))))

(deftest merge-base-of-two-branches
  (is (= #{"c1"} (d/merge-base dag "c4" "c5")) "LCA of the two branch tips is c1")
  (is (= "c1" (d/merge-base-1 dag "c4" "c5")))
  (testing "linear history: merge-base is the older commit"
    (is (= #{"c1"} (d/merge-base dag "c1" "c4"))))
  (testing "disjoint histories have no base"
    (is (nil? (d/merge-base-1 {"x" {:parents []} "y" {:parents []}} "x" "y")))))

(deftest merge-base-with-merge-commit
  ;; c6 merges c4 and c5 ; merge-base(c6, c4) should be c4 itself
  (let [dag2 (assoc dag "c6" {:parents ["c4" "c5"]})]
    (is (= #{"c4"} (d/merge-base dag2 "c6" "c4")))
    (is (= #{"c1"} (d/merge-base dag2 "c2" "c5")))))

(defn -main []
  (let [{:keys [fail error]} (run-tests 'kotoba.gitdiff-test)]
    (+ (or fail 0) (or error 0))))

(ns kotoba.gitmerge-test
  "Tests for the GitOffice Phase 3 3-way merger."
  (:require [clojure.test :refer [deftest is testing run-tests]]
            [kotoba.gitoffice :as g]
            [kotoba.gitdiff :as d]
            [kotoba.gitmerge :as m]))

;; ---------------------------------------------------------------------------
;; clean cases: one-sided change, agreement, deletion
;; ---------------------------------------------------------------------------

(deftest one-sided-changes-auto-merge
  (let [base {"a" {:kind :block/paragraph :text "x" :order "i"}}
        ours (assoc-in base ["a" :text] "x-ours")          ; ours edits
        theirs base                                         ; theirs unchanged
        r (m/merge3 base ours theirs)]
    (is (m/clean? r))
    (is (= "x-ours" (get-in r [:merged "a" :text])))))

(deftest delete-unchanged-side-is-clean
  (testing "theirs deletes, ours unchanged -> clean delete (no conflict)"
    (let [base {"a" {:text "x" :order "i"} "b" {:text "y" :order "r"}}
          ours base
          theirs (dissoc base "b")
          r (m/merge3 base ours theirs)]
      (is (m/clean? r))
      (is (contains? (:merged r) "a"))
      (is (not (contains? (:merged r) "b")) "b deleted in merge"))))

;; ---------------------------------------------------------------------------
;; the headline: ATTRIBUTE-LEVEL auto-merge (text 3-way would conflict)
;; ---------------------------------------------------------------------------

(deftest attribute-level-auto-merge
  (testing "same element: ours edits heading-level, theirs edits text -> both apply"
    (let [base   {"h" {:kind :block/heading :text "概要" :heading-level 1 :order "i"}}
          ours   (assoc-in base ["h" :heading-level] 2)
          theirs (assoc-in base ["h" :text] "概要(改)")
          r (m/merge3 base ours theirs)]
      (is (m/clean? r) "different attributes on the same element do NOT conflict")
      (is (= 2 (get-in r [:merged "h" :heading-level])))
      (is (= "概要(改)" (get-in r [:merged "h" :text]))))))

;; ---------------------------------------------------------------------------
;; real conflicts: same attr both sides, and delete-vs-modify
;; ---------------------------------------------------------------------------

(deftest same-attr-conflict
  (let [base   {"p" {:kind :block/paragraph :text "orig" :order "i"}}
        ours   (assoc-in base ["p" :text] "ours")
        theirs (assoc-in base ["p" :text] "theirs")
        r (m/merge3 base ours theirs)]
    (is (not (m/clean? r)))
    (is (= :attr (get-in r [:conflicts "p" :kind])))
    (is (= {:base "orig" :ours "ours" :theirs "theirs"}
           (get-in r [:conflicts "p" :attrs :text])))
    (testing "resolve picks a value and clears the conflict"
      (let [r2 (m/resolve-conflict r "p" {:kind :block/paragraph :text "theirs" :order "i"})]
        (is (m/clean? r2))
        (is (= "theirs" (get-in r2 [:merged "p" :text])))))))

(deftest delete-modify-conflict
  (let [base   {"p" {:text "orig" :order "i"}}
        ours   (dissoc base "p")                  ; ours deletes
        theirs (assoc-in base ["p" :text] "edit") ; theirs edits
        r (m/merge3 base ours theirs)]
    (is (= :delete-modify (get-in r [:conflicts "p" :kind])))
    (is (= :ours (get-in r [:conflicts "p" :deleted])))))

;; ---------------------------------------------------------------------------
;; the fractional-index win: concurrent inserts never conflict
;; ---------------------------------------------------------------------------

(deftest concurrent-inserts-do-not-conflict
  (testing "ours and theirs each insert a new block between a and b -> two ADDs, clean"
    (let [base-body [{:elementId "a" :kind "paragraph" :text "A"}
                     {:elementId "b" :kind "paragraph" :text "B"}]
          base (d/doc-nodes (g/body->blocks "doc" base-body) "doc")
          [oa ob] [(get-in base ["a" :order]) (get-in base ["b" :order])]
          x-ord (g/order-between oa ob)
          y-ord (g/order-between x-ord ob)        ; distinct key to keep ids orderable
          ours   (assoc base "x" {:kind :block/paragraph :text "X" :order x-ord})
          theirs (assoc base "y" {:kind :block/paragraph :text "Y" :order y-ord})
          r (m/merge3 base ours theirs)]
      (is (m/clean? r) "concurrent inserts are not a conflict")
      (is (= #{"a" "b" "x" "y"} (set (keys (:merged r)))) "both inserts kept")
      (testing "final order interleaves correctly: A < X < Y < B"
        (let [body (m/merged-doc->body (:merged r))]
          (is (= ["A" "X" "Y" "B"] (mapv :text body))))))))

;; ---------------------------------------------------------------------------
;; end-to-end via datom wrappers
;; ---------------------------------------------------------------------------

(deftest merge-doc-datom-wrapper
  (let [base (g/body->blocks "doc"
                             [{:elementId "a" :kind "heading" :headingLevel 1 :text "T"}
                              {:elementId "b" :kind "paragraph" :text "body"}])
        ours (g/body->blocks "doc"
                             [{:elementId "a" :kind "heading" :headingLevel 1 :text "T (ours)"}
                              {:elementId "b" :kind "paragraph" :text "body"}])
        theirs (g/body->blocks "doc"
                               [{:elementId "a" :kind "heading" :headingLevel 1 :text "T"}
                                {:elementId "b" :kind "paragraph" :text "body (theirs)"}])
        r (m/merge-doc base ours theirs "doc")]
    (is (m/clean? r) "ours edits block a, theirs edits block b -> no conflict")
    (is (= "T (ours)" (get-in r [:merged "a" :text])))
    (is (= "body (theirs)" (get-in r [:merged "b" :text])))))

(deftest merge-sheet-cellwise
  (testing "edits to different cells auto-merge; same cell conflicts"
    (let [base   (g/grid->cells "bk" {"S" [["1" "2"]]})
          ours   (g/grid->cells "bk" {"S" [["1x" "2"]]})  ; A1
          theirs (g/grid->cells "bk" {"S" [["1" "2y"]]})  ; B1
          r (m/merge-sheet base ours theirs "bk")]
      (is (m/clean? r))
      (is (= "1x" (get-in r [:merged "S!A1" :value])))
      (is (= "2y" (get-in r [:merged "S!B1" :value]))))
    (let [base   (g/grid->cells "bk" {"S" [["1"]]})
          ours   (g/grid->cells "bk" {"S" [["1o"]]})
          theirs (g/grid->cells "bk" {"S" [["1t"]]})
          r (m/merge-sheet base ours theirs "bk")]
      (is (= :attr (get-in r [:conflicts "S!A1" :kind]))))))

(defn -main []
  (let [{:keys [fail error]} (run-tests 'kotoba.gitmerge-test)]
    (+ (or fail 0) (or error 0))))

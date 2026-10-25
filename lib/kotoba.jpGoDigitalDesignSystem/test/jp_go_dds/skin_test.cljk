(ns jp-go-dds.skin-test
  "skin と component の併用が壊れないことを守るテスト。

  README は `dds.css` + `skin-css` の併用を勧めており、その構成では同じページに
  素の `<table>` と `.dads-table` component が同居しうる。skin は素の markup を
  助けるためのものなので、component を壊してはならない。"
  (:require [kotoba.lang.text :as str]
            [clojure.test :refer [deftest is testing]]
            [jp-go-dds.skin :as skin]))

(deftest skin-must-not-break-the-dads-table-component
  (testing "上流 `.dads-table__table` は `display` を持たない(border-collapse だけ)ので、
            素の `table` セレクタで display:block を当てると DADS の表が block 化して
            列が崩れる。skin の表規則は必ず component を除外する。"
    ;; 表に触る規則は、すべて component を除外していること。
    (doseq [[selector _] skin/skin-rules
            :when (str/includes? selector "table")]
      (is (str/includes? selector ":not(.dads-table__table)")
          (str "component を除外していない表規則: " selector)))
    ;; セル規則も同じ(skin の罫が DADS 自身の罫と二重になる)。
    (doseq [[selector _] skin/skin-rules
            :when (re-find #"\b(th|td)\b" selector)]
      (is (str/includes? selector ":not(.dads-table__table)")
          (str "component を除外していないセル規則: " selector)))
    (is (str/includes? skin/skin-css ":not(.dads-table__table)"))))

(deftest skin-still-styles-plain-tables
  (testing "component を除外しても、素の表(console / LP が実際に書くもの)は
            引き続き skin の対象であること"
    (is (str/includes? skin/skin-css "table:not(.dads-table__table)"))
    (is (str/includes? skin/skin-css "overflow-x"))))

(deftest skin-writes-no-raw-hex
  (testing "色は DADS token のみ(この ns の既定方針)"
    (is (not (re-find #"#[0-9a-fA-F]{3}" skin/skin-css)) skin/skin-css)))

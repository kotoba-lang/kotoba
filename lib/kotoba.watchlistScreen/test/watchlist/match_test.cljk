(ns watchlist.match-test
  (:require [clojure.test :refer [deftest is]]
            [watchlist.match :as match]))

;; Reference vectors from Winkler's own published Jaro-Winkler examples,
;; reproduced identically across many independent implementations -- if
;; this fails, the algorithm itself has a bug, not a tuning issue.
(deftest jaro-winkler-reference-vectors
  (is (< (Math/abs (- 0.9611 (match/jaro-winkler "MARTHA" "MARHTA"))) 1e-3))
  (is (< (Math/abs (- 0.8400 (match/jaro-winkler "DWAYNE" "DUANE"))) 1e-3))
  (is (< (Math/abs (- 0.8133 (match/jaro-winkler "DIXON" "DICKSONX"))) 1e-3))
  (is (= 1.0 (match/jaro-winkler "SAME" "SAME")))
  (is (= 0.0 (match/jaro-winkler "" "ANYTHING")))
  (is (= 1.0 (match/jaro-winkler "" ""))))

(deftest normalize-strips-punctuation-and-collapses-whitespace
  (is (= "hello world" (match/normalize "  Hello,   WORLD!! ")))
  (is (= "" (match/normalize nil))))

(deftest normalize-does-not-transliterate-diacritics-known-gap
  ;; Documents the real, known limitation this ns's module doc warns about:
  ;; accented characters are stripped as punctuation, not transliterated to
  ;; their plain-ASCII equivalent -- "José" becomes "jos", not "jose". A
  ;; source-list entry only present in accented form would not match a
  ;; plain-ASCII query (or vice versa) under this normalizer.
  (is (= "jos mar a lvarez" (match/normalize "José-María  Álvarez."))))

(deftest tokens-splits-normalized-words
  (is (= ["john" "doe"] (match/tokens "  John   DOE! "))))

(deftest score-name-exact-tier
  (let [s (match/score-name "Ahmed Hassan" "AHMED HASSAN")]
    (is (= :exact (:tier s)))
    (is (= 1.0 (:confidence s)))))

(deftest score-name-fuzzy-high-tier-close-typo
  (let [s (match/score-name "Martha Stewart" "Marhta Stewart")]
    (is (= :fuzzy-high (:tier s)))
    (is (<= 0.75 (:confidence s) 0.92))))

(deftest score-name-fuzzy-high-tier-reordered-tokens
  (let [s (match/score-name "Stewart Martha" "Martha Stewart")]
    (is (= :fuzzy-high (:tier s)) "token-set-subset catches reordering a pure JW comparison would miss")))

(deftest score-name-fuzzy-low-tier-partial-overlap
  (let [s (match/score-name "John Michael Smith" "John Smith")]
    (is (contains? #{:fuzzy-high :fuzzy-low} (:tier s)))))

(deftest score-name-below-threshold-is-nil-tier-not-a-candidate
  (let [s (match/score-name "Alice Wonderland" "Bob Builder")]
    (is (nil? (:tier s)))))

(deftest best-entity-match-picks-highest-scoring-alias
  (let [entity {:entity/primary-name "Unrelated Person"
                :entity/aliases ["Some Other Name" "Ahmed Hassan Al-Zomor"]}
        m (match/best-entity-match "Ahmed Hasan Alzomor" entity)]
    (is (some? m))
    (is (= "Ahmed Hassan Al-Zomor" (:matched-name m)))
    (is (= :alias (:matched-name-kind m)))))

(deftest best-entity-match-nil-when-nothing-clears-the-low-threshold
  (let [entity {:entity/primary-name "Zzyzx Qwerty" :entity/aliases []}]
    (is (nil? (match/best-entity-match "Completely Different Name" entity)))))

;; --- script folding, added with :jp-mof ------------------------------------

(deftest an-unrepresentable-name-matches-nothing-not-everything
  ;; The defect this floor exists for: `jaro-winkler` of two empty strings is
  ;; 1.0, so before the floor, ANY pair of names `normalize` could not
  ;; represent scored :fuzzy-high at 0.92. Two unrelated Cyrillic names would
  ;; have been reported as a sanctions hit.
  ;;
  ;; The two normalize assertions are the control: without them this test
  ;; passes for the wrong reason the moment Cyrillic is added to the kept set
  ;; (the names are simply dissimilar then, and the empty path is no longer
  ;; being exercised at all). They pin that this is still the empty case.
  (is (= "" (match/normalize "Иванов")))
  (is (= "" (match/normalize "Петров")))
  (is (nil? (:tier (match/score-name "Иванов" "Петров"))))
  (is (nil? (:tier (match/score-name "Иванов" "Иванов"))))
  (is (nil? (:tier (match/score-name "" "")))))

(deftest japanese-names-survive-normalization-rather-than-collapsing
  ;; The other half of the same fix. These must NOT be "" -- if they were,
  ;; every MOF entity would fall through to the floor above and the Japanese
  ;; half of the list would be unreachable.
  (is (= "アル カーイダ" (match/normalize "アル・カーイダ")))
  (is (= "山田太郎" (match/normalize "山田太郎")))
  (is (nil? (:tier (match/score-name "山田太郎" "アル・カーイダ")))))

(deftest hiragana-and-katakana-are-one-name
  (is (= "ヤマダタロウ" (match/normalize "やまだたろう")))
  (is (= :exact (:tier (match/score-name "やまだたろう" "ヤマダタロウ")))))

(deftest halfwidth-katakana-folds-with-its-voicing-mark-attached
  ;; ｶﾞ is two codepoints and ガ is one. A per-character map leaves the mark
  ;; stranded, `normalize` strips it, and ガ silently becomes カ -- a
  ;; different name, reported as a clean non-match.
  (is (= "ガ" (match/normalize "ｶﾞ")))
  (is (= "パ" (match/normalize "ﾊﾟ")))
  (is (= "ヴ" (match/normalize "ｳﾞ")))
  (is (= "アル カーイダ" (match/normalize "ｱﾙ･ｶｰｲﾀﾞ")))
  (is (= :exact (:tier (match/score-name "ｱﾙ･ｶｰｲﾀﾞ" "アル・カーイダ")))))

(deftest fullwidth-latin-is-the-same-name-as-ascii
  (is (= "al qaida" (match/normalize "ＡＬ－ＱＡＩＤＡ")))
  (is (= :exact (:tier (match/score-name "ＡＬ－ＱＡＩＤＡ" "AL-QAIDA")))))

(deftest the-nakaguro-separates-rather-than-vanishes
  ;; U+30FB sits inside the katakana block, so keeping the block wholesale
  ;; would fuse アル・カーイダ into one token and lose the reordered-name
  ;; match that `token-set-subset?` provides for every other source.
  (is (= 2 (count (match/tokens "アル・カーイダ"))))
  (is (= 1 (count (match/tokens "カーイダ"))))
  ;; the prolonged sound mark, by contrast, is part of the name
  (is (= "カーイダ" (match/normalize "カーイダ"))))

(deftest latin-matching-is-unchanged-by-the-script-fold
  ;; The fold adds ranges; it must not move any Latin boundary. These are the
  ;; same reference points the Jaro-Winkler tests above use.
  (is (= "milosevic slobodan" (match/normalize "Milosevic Slobodan")))
  (is (= :exact (:tier (match/score-name "MILOSEVIC SLOBODAN" "Milosevic Slobodan"))))
  (is (nil? (:tier (match/score-name "Alice Wonderland" "Bob Builder")))))

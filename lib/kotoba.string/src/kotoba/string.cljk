(ns kotoba.string
  "clojure.string's replacement, assembled from one repo per definition.

  This namespace holds no implementation. It re-exports the definitions
  that each live in their own repo, so a call site can require one name
  and a library can require only the definitions it actually uses."
  (:refer-clojure :exclude [format join re-find re-matches re-seq replace reverse split])
  (:require [kotoba.string.blank-text :as blank-text-ns]
            [kotoba.string.blank :as blank-ns]
            [kotoba.string.capitalize :as capitalize-ns]
            [kotoba.string.codepoints :as codepoints-ns]
            [kotoba.string.ends-with :as ends-with-ns]
            [kotoba.string.escape :as escape-ns]
            [kotoba.string.format :as format-ns]
            [kotoba.string.from-codepoints :as from-codepoints-ns]
            [kotoba.string.includes :as includes-ns]
            [kotoba.string.index-of :as index-of-ns]
            [kotoba.string.index-of-text :as index-of-text-ns]
            [kotoba.string.join :as join-ns]
            [kotoba.string.last-index-of :as last-index-of-ns]
            [kotoba.string.last-index-of-text :as last-index-of-text-ns]
            [kotoba.string.lower :as lower-ns]
            [kotoba.string.pad-center-text :as pad-center-text-ns]
            [kotoba.string.pad-left :as pad-left-ns]
            [kotoba.string.pad-left-text :as pad-left-text-ns]
            [kotoba.string.pad-right :as pad-right-ns]
            [kotoba.string.pad-right-text :as pad-right-text-ns]
            [kotoba.string.re-find :as re-find-ns]
            [kotoba.string.re-matches :as re-matches-ns]
            [kotoba.string.re-seq :as re-seq-ns]
            [kotoba.string.repeat-text :as repeat-text-ns]
            [kotoba.string.replace :as replace-ns]
            [kotoba.string.replace-first :as replace-first-ns]
            [kotoba.string.replace-first-text :as replace-first-text-ns]
            [kotoba.string.reverse :as reverse-ns]
            [kotoba.string.reverse-text :as reverse-text-ns]
            [kotoba.string.segment-count-text :as segment-count-text-ns]
            [kotoba.string.segment-text :as segment-text-ns]
            [kotoba.string.spec-re :as spec-re-ns]
            [kotoba.string.split :as split-ns]
            [kotoba.string.split-lines :as split-lines-ns]
            [kotoba.string.starts-with :as starts-with-ns]
            [kotoba.string.trim :as trim-ns]
            [kotoba.string.trim-newline :as trim-newline-ns]
            [kotoba.string.trim-newline-text :as trim-newline-text-ns]
            [kotoba.string.trim-text :as trim-text-ns]
            [kotoba.string.triml :as triml-ns]
            [kotoba.string.triml-text :as triml-text-ns]
            [kotoba.string.trimr :as trimr-ns]
            [kotoba.string.trimr-text :as trimr-text-ns]
            [kotoba.string.truncate :as truncate-ns]
            [kotoba.string.upper :as upper-ns]))

(def blank-text? "See kotoba.string.blank-text/blank-text?." blank-text-ns/blank-text?)
(def blank? "See kotoba.string.blank/blank?." blank-ns/blank?)
(def capitalize "See kotoba.string.capitalize/capitalize." capitalize-ns/capitalize)
(def codepoints "See kotoba.string.codepoints/codepoints." codepoints-ns/codepoints)
(def ends-with? "See kotoba.string.ends-with/ends-with?." ends-with-ns/ends-with?)
(def escape "See kotoba.string.escape/escape." escape-ns/escape)
(def format "See kotoba.string.format/format." format-ns/format)
(def from-codepoints "See kotoba.string.from-codepoints/from-codepoints." from-codepoints-ns/from-codepoints)
(def includes? "See kotoba.string.includes/includes?." includes-ns/includes?)
(def index-of "See kotoba.string.index-of/index-of." index-of-ns/index-of)
(def index-of-text "See kotoba.string.index-of-text/index-of-text." index-of-text-ns/index-of-text)
(def join "See kotoba.string.join/join." join-ns/join)
(def last-index-of "See kotoba.string.last-index-of/last-index-of." last-index-of-ns/last-index-of)
(def last-index-of-text "See kotoba.string.last-index-of-text/last-index-of-text." last-index-of-text-ns/last-index-of-text)
(def lower "See kotoba.string.lower/lower." lower-ns/lower)
(def pad-center-text "See kotoba.string.pad-center-text/pad-center-text." pad-center-text-ns/pad-center-text)
(def pad-left "See kotoba.string.pad-left/pad-left." pad-left-ns/pad-left)
(def pad-left-text "See kotoba.string.pad-left-text/pad-left-text." pad-left-text-ns/pad-left-text)
(def pad-right "See kotoba.string.pad-right/pad-right." pad-right-ns/pad-right)
(def pad-right-text "See kotoba.string.pad-right-text/pad-right-text." pad-right-text-ns/pad-right-text)
(def re-find "See kotoba.string.re-find/re-find." re-find-ns/re-find)
(def re-matches "See kotoba.string.re-matches/re-matches." re-matches-ns/re-matches)
(def re-seq "See kotoba.string.re-seq/re-seq." re-seq-ns/re-seq)
(def repeat-text "See kotoba.string.repeat-text/repeat-text." repeat-text-ns/repeat-text)
(def replace "See kotoba.string.replace/replace." replace-ns/replace)
(def replace-first "See kotoba.string.replace-first/replace-first." replace-first-ns/replace-first)
(def replace-first-text "See kotoba.string.replace-first-text/replace-first-text." replace-first-text-ns/replace-first-text)
(def reverse "See kotoba.string.reverse/reverse." reverse-ns/reverse)
(def reverse-text "See kotoba.string.reverse-text/reverse-text." reverse-text-ns/reverse-text)
(def segment-count-text "See kotoba.string.segment-count-text/segment-count-text." segment-count-text-ns/segment-count-text)
(def segment-text "See kotoba.string.segment-text/segment-text." segment-text-ns/segment-text)
(def spec-re "See kotoba.string.spec-re/spec-re." spec-re-ns/spec-re)
(def split "See kotoba.string.split/split." split-ns/split)
(def split-lines "See kotoba.string.split-lines/split-lines." split-lines-ns/split-lines)
(def starts-with? "See kotoba.string.starts-with/starts-with?." starts-with-ns/starts-with?)
(def trim "See kotoba.string.trim/trim." trim-ns/trim)
(def trim-newline "See kotoba.string.trim-newline/trim-newline." trim-newline-ns/trim-newline)
(def trim-newline-text "See kotoba.string.trim-newline-text/trim-newline-text." trim-newline-text-ns/trim-newline-text)
(def trim-text "See kotoba.string.trim-text/trim-text." trim-text-ns/trim-text)
(def triml "See kotoba.string.triml/triml." triml-ns/triml)
(def triml-text "See kotoba.string.triml-text/triml-text." triml-text-ns/triml-text)
(def trimr "See kotoba.string.trimr/trimr." trimr-ns/trimr)
(def trimr-text "See kotoba.string.trimr-text/trimr-text." trimr-text-ns/trimr-text)
(def truncate "See kotoba.string.truncate/truncate." truncate-ns/truncate)
(def upper "See kotoba.string.upper/upper." upper-ns/upper)

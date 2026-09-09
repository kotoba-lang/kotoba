(ns kotoba.string
  "Alias of `kotoba.lang.text`. Same functions, one implementation -- every var
  here IS the var there, so there is no second copy to drift.

  Two names exist because two places already pointed at two of them and
  neither pointed at the third. Root ADR-2609040930's replacement-router table
  routes `clojure.string` to `kotoba.text`, a namespace that did not exist;
  the implementation has always been `kotoba.lang.text`; and the owner named
  `kotoba.string` for the guest `.kotoba` plane in `kotoba-lang/kotoba-lang`.
  Rather than retire two of the three names, they are aliases (owner decision,
  2026-09-08). This is the name the guest `.kotoba` plane uses; the guest surface is a SUBSET of this one, and where a guest function deliberately diverges the divergence is named in `kotoba-lang/kotoba-lang`'s `lang/compat.edn`.

  What an alias does NOT carry: docstrings and arglists. `def` copies the
  value, not the metadata, and copying metadata portably would need a macro
  this library does not otherwise have. Read the documentation at
  `kotoba.lang.text`, which is where it lives.

  Drift is not guarded by care. `kotoba.lang.text-alias-test` asserts that the
  public surface here is EXACTLY the public surface there and that each var is
  identical -- a function added to the canonical namespace and forgotten here
  turns that test red rather than quietly leaving the aliases a subset."
  (:refer-clojure :exclude [format split join replace re-find re-matches re-seq reverse])
  (:require [kotoba.lang.text :as text]))

(def split text/split)
(def split-lines text/split-lines)
(def join text/join)
(def trim text/trim)
(def triml text/triml)
(def trimr text/trimr)
(def upper text/upper)
(def lower text/lower)
(def capitalize text/capitalize)
(def starts-with? text/starts-with?)
(def ends-with? text/ends-with?)
(def includes? text/includes?)
(def replace text/replace)
(def replace-first text/replace-first)
(def re-find text/re-find)
(def re-matches text/re-matches)
(def re-seq text/re-seq)
(def format text/format)
(def codepoints text/codepoints)
(def from-codepoints text/from-codepoints)
(def pad-left text/pad-left)
(def pad-right text/pad-right)
(def truncate text/truncate)
(def blank? text/blank?)
(def index-of text/index-of)
(def last-index-of text/last-index-of)
(def reverse text/reverse)
(def trim-newline text/trim-newline)
(def trim-text text/trim-text)
(def triml-text text/triml-text)
(def trimr-text text/trimr-text)
(def blank-text? text/blank-text?)
(def reverse-text text/reverse-text)
(def repeat-text text/repeat-text)
(def index-of-text text/index-of-text)
(def last-index-of-text text/last-index-of-text)
(def pad-left-text text/pad-left-text)
(def pad-right-text text/pad-right-text)
(def replace-first-text text/replace-first-text)
(def trim-newline-text text/trim-newline-text)
(def segment-count-text text/segment-count-text)
(def segment-text text/segment-text)
(def pad-center-text text/pad-center-text)
(def escape text/escape)

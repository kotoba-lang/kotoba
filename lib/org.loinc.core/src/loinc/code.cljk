(ns loinc.code
  "The LOINC code format — `nnnnn-n`: a variable-length digit string, a
  literal hyphen, and a single Mod-10 \"double-add-double\" check digit
  (`loinc.check-digit`). The format itself (a plain, unregistered
  digit-plus-check-digit identifier scheme) is published structure, not
  licensed content — this namespace does not enumerate or ship any real
  LOINC codes, only the shape a code must have and the arithmetic that
  proves a given code is well-formed.

  Two codes are used as fixtures throughout this library's tests, cited
  by number and their commonly-published one/two-word component name,
  as *examples* — never as part of an enumerated table:
  `2951-2` (Sodium) and `718-7` (Hemoglobin)."
  (:require [kotoba.lang.text :as str]
            [loinc.check-digit :as cd]))

(defn parse
  "Split `s` into `{:number \"2951\" :check-digit 2}` — structural
  parsing only (shape, not validity: use `valid?` to confirm the check
  digit actually matches). Returns `[:error reason]` for anything that
  isn't `<digits>-<digit>`:
  `:loinc/no-hyphen`, `:loinc/multiple-hyphens`, `:loinc/empty-number`,
  `:loinc/check-digit-not-single-digit`, or whatever `loinc.check-digit/
  digits` reports for a non-digit `:number` part."
  [s]
  (let [parts (str/split s #"-" -1)]
    (cond
      (= 1 (count parts)) [:error :loinc/no-hyphen]
      (> (count parts) 2) [:error :loinc/multiple-hyphens]
      :else
      (let [[number check] parts]
        (cond
          (empty? number) [:error :loinc/empty-number]
          (not= 1 (count check)) [:error :loinc/check-digit-not-single-digit]
          :else
          (let [digits-result (cd/digits number)
                check-result (cd/digits check)]
            (cond
              (= (first digits-result) :error) digits-result
              (= (first check-result) :error) check-result
              :else [:ok {:number number
                          :check-digit (first (second check-result))}])))))))

(defn valid?
  "True when `s` parses as `<digits>-<digit>` **and** the check digit
  matches `loinc.check-digit/check-digit` of the number part. False for
  any structural or checksum failure — this predicate never throws."
  [s]
  (let [result (parse s)]
    (and (= (first result) :ok)
         (let [{:keys [number check-digit]} (second result)
               expected (cd/check-digit number)]
           (and (= (first expected) :ok)
                (= check-digit (second expected)))))))

(defn format-code
  "`{:number \"2951\"}` -> `\"2951-2\"`, computing and appending the
  correct check digit. Returns `[:error reason]` if `number` isn't a
  non-empty digit string."
  [{:keys [number]}]
  (let [result (cd/check-digit number)]
    (if (= (first result) :error)
      result
      [:ok (str number "-" (second result))])))

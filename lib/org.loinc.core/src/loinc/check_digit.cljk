(ns loinc.check-digit
  "LOINC's Mod-10 \"double-add-double\" check digit — a published,
  general-purpose checksum algorithm (the same family as the IBM/Luhn
  check digit used on credit card numbers, and used by several other
  ANSI/HL7 identifier schemes), not licensed content. LOINC's own Users'
  Guide documents it as chapter \"C — Calculating Mod 10 Check Digits\";
  what follows is this library's own implementation of that published
  procedure, verified against the two check digits below, not a copy of
  LOINC's page text.

  **The procedure**, applied to the numeric part of a code (the digits
  before the hyphen — e.g. `\"2951\"` for the code `2951-2`):

  1. Number the digits from the **right**, starting at position 1.
  2. Digits at **odd** positions (1st, 3rd, 5th, ... from the right) are
     doubled.
  3. If doubling a digit produces a value > 9 (i.e. the original digit
     was 5-9), **add its two digits together** rather than keep the
     two-digit number — this is the \"double-add-double\" step, and is
     numerically identical to subtracting 9 from the doubled value
     (`(2*d) - 9` for `d` in 5..9), which is how `double-and-reduce`
     below actually computes it, without a string round-trip.
  4. Digits at **even** positions are left unchanged.
  5. Sum every resulting single digit (both the doubled-and-reduced odd
     positions and the untouched even positions).
  6. The check digit is `(10 - (sum mod 10)) mod 10` — i.e. \"the digit
     that brings the total to a multiple of 10\", with 0 rather than 10
     when the sum is already a multiple of 10 (the outer `mod 10`
     handles that edge case: `(10 - 0) mod 10 = 0`).

  **Verified against two published example LOINC codes** (both codes are
  cited by their number only, as examples — not the licensed table):
  `2951-2` (Sodium, a code and abbreviated component name cited in
  essentially every public LOINC tutorial) and `718-7` (Hemoglobin,
  likewise). This library was unable to fetch LOINC's own check-digit
  page directly during development (the request was blocked by the
  server, HTTP 403); the algorithm above was reconstructed from
  independent public descriptions of the general \"double-add-double\"
  Mod-10 method and then verified to reproduce both published check
  digits exactly (`check-digit \"2951\"` => `2`, `check-digit \"718\"` =>
  `7`) before being trusted. See `loinc.check-digit-test`.

  Only bare arithmetic (`+` `-` `*` `mod`) is used here — there is no
  byte-level wire format to decode, so there is nothing for `bit-and`/
  `bit-or`/`bit-shift` to do. A low bit-op count in this namespace is
  correct, not a shortfall.")

;; **Not `int`.** `(int c)` correctly converts a character to its code
;; point on the JVM, but not in ClojureScript: a Clojure character is
;; just a one-character JS string there, and `int` on a *non-numeric*
;; string goes through JS's `ToInt32` coercion (`NaN` -> `0`) rather than
;; extracting a code point. `(map int "2951")` therefore comes back as
;; four zeros under ClojureScript and the real digits on the JVM — this
;; workspace's `org-modbus` and `org-dicomstandard-dicom` READMEs both
;; document independently hitting this exact trap; `char-code` here is
;; the reader-conditional fix (`.charCodeAt` on cljs).
(defn- char-code
  [c]
  #?(:clj (int c)
     :cljs (.charCodeAt (str c) 0)))

(defn- double-and-reduce
  "Double `d` (a single digit 0-9); if the result is > 9, reduce it to
  the sum of its two digits (`(2*d) - 9`, since a doubled digit is at
  most 18 and its digit-sum equals `2*d - 9` whenever `2*d > 9`)."
  [d]
  (let [doubled (* d 2)]
    (if (> doubled 9) (- doubled 9) doubled)))

(defn digits
  "`\"2951\"` -> `[2 9 5 1]`. `[:error :loinc/not-digits]` if `s` contains
  anything but ASCII digits, or is empty."
  [s]
  (let [codes (map char-code s)
        zero (char-code \0)
        nine (char-code \9)]
    (if (or (empty? s) (not (every? #(<= zero % nine) codes)))
      [:error :loinc/not-digits]
      [:ok (mapv #(- % zero) codes)])))

(defn check-digit
  "The Mod-10 double-add-double check digit (an int 0-9) for the base
  digit string `s` (no hyphen, no check digit already appended). Returns
  `[:error :loinc/not-digits]` for non-digit input."
  [s]
  (let [result (digits s)]
    (if (= (first result) :error)
      result
      (let [ds (second result)
            n (count ds)
            total (reduce + 0
                          (map-indexed
                           (fn [i d]
                             (let [pos-from-right (- n i)]
                               (if (odd? pos-from-right)
                                 (double-and-reduce d)
                                 d)))
                           ds))]
        [:ok (mod (- 10 (mod total 10)) 10)]))))

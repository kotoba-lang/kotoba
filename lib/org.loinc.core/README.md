# kotoba-lang/org-loinc

**LOINC (Logical Observation Identifiers Names and Codes) — code format,
Mod-10 check digit, six-axis part model, and a release-file CSV parser —
in portable, dependency-free `.cljc`. Ships no LOINC content.**

## The licensing boundary — read this before using or extending this repo

LOINC's code database — the actual table mapping a code like `2951-2`
to "Sodium [Moles/volume] in Blood" and its Component/Property/Time/
System/Scale/Method values — is **licensed content owned by Regenstrief
Institute**. This repository does not vendor, embed, download, cache, or
reproduce that table, or any substantial extract of it, and never will.

**What this library ships (published structure, not licensed content):**

- The LOINC **code format** (`<digits>-<check-digit>`) and its Mod-10
  "double-add-double" check-digit **algorithm** — a general-purpose,
  published arithmetic procedure (the same family as the Luhn/IBM check
  digit used on credit card numbers), not a code list.
- A **parser** for the RFC-4180-shaped CSV layout LOINC's release files
  use, so a licensee who has downloaded their own copy of a release can
  load it into structured data. The parser is header-driven — it reads
  whatever column names are actually present in the file handed to it —
  and hardcodes no LOINC column names, counts, or values.
- The **six-axis part model** (Component, Property, Time, System, Scale,
  Method) as a **data shape**: a map with six keys, a validator that the
  shape is complete, and the colon-delimited Fully-Specified-Name
  join/split convention. No axis *values* for any real code are shipped.
- Validation and formatting **helpers** that operate on codes and
  six-axis maps a caller supplies.

**What this library does NOT ship, and will not accept a PR adding:**

- The LOINC code-to-name table, in whole or in part.
- Any file, fixture, or test vector that reproduces or closely resembles
  a substantial extract of LOINC's Component/Property/System/Scale/
  Method values for real codes.
- A bundled or auto-downloaded copy of a LOINC release.

**Test fixtures use at most a handful of well-known example codes**,
cited by number (and, where useful, their commonly-published one-word
component name) as *examples* — the same way any LOINC tutorial cites
`2951-2` or `718-7` — never as part of an enumerated table. Every
six-axis *value* used in this repo's tests (component/system/etc. text)
is invented placeholder text (e.g. `"Fake-Analyte"`), not drawn from or
resembling real LOINC terminology.

**To use this library against real data, supply your own licensed LOINC
release** (downloaded directly from loinc.org under your own license
agreement) and pass its CSV text to `loinc.release-csv/parse`.

If, after all this, a use case would require this library to embed real
LOINC content to be useful — it doesn't, everything above operates on
data the caller supplies — the right answer is to not build that part,
not to stretch the boundary. Nothing in this repo does.

## Surface

```clojure
(require '[loinc.code :as code]
         '[loinc.check-digit :as cd]
         '[loinc.parts :as parts]
         '[loinc.release-csv :as csv])

(code/valid? "2951-2")                 ;=> true   (a real, published example code)
(code/valid? "2951-9")                 ;=> false  (wrong check digit)
(code/format-code {:number "2951"})    ;=> [:ok "2951-2"]
(cd/check-digit "718")                 ;=> [:ok 7]

(parts/fully-specified-name
  (parts/part {:component "..." :property "..." :time "..." :system "..."
               :scale "..." :method ""}))
;=> [:ok "...:...:...:...:...:"]       -- caller supplies every axis value

;; a licensee's own release file, read however they like (this library
;; does no IO of its own) and handed in as text:
(csv/parse (slurp "/path/to/your/licensed/Loinc.csv"))
;=> [:ok [{:LOINC_NUM "..." :COMPONENT "..." ...} ...]]
```

| namespace | |
|---|---|
| `loinc.check-digit` | Mod-10 double-add-double check digit compute + digit-string validation |
| `loinc.code` | `<digits>-<digit>` code parse / checksum-validate / format |
| `loinc.parts` | six-axis part shape, validator, Fully-Specified-Name join/split |
| `loinc.release-csv` | header-driven RFC 4180 CSV parser for a caller-supplied release file |

## The check digit, precisely

Given the digit string before the hyphen (e.g. `"2951"`):

1. Number the digits from the **right**, starting at position 1.
2. Digits at **odd** positions (1st, 3rd, 5th, ... from the right) are
   doubled; if doubling produces a value > 9, its two digits are added
   together (equivalently, subtract 9 — `2*d - 9` for `d` in 5..9).
3. Digits at **even** positions are left unchanged.
4. Sum every resulting single digit.
5. The check digit is `(10 - (sum mod 10)) mod 10`.

This library was unable to fetch LOINC's own check-digit documentation
page directly during development (`https://loinc.org/kb/faq/check-digit/`
and the Users' Guide chapter both returned HTTP 403 to an automated
fetch). The algorithm above was instead reconstructed from independent
public descriptions of the general "Mod-10 double-add-double" method,
**then verified to reproduce two real, published LOINC check digits
exactly** before being trusted as correct:

```
check-digit "2951" => 2   (2951-2, "Sodium" — cited in essentially every public LOINC tutorial)
check-digit "718"  => 7   (718-7,  "Hemoglobin" — likewise)
```

Both are kept as permanent regression tests
(`check-digit-matches-published-examples`), not one-off manual checks.

## Errors

Returned, never thrown. `:reason` is a keyword: `:loinc/not-digits`,
`:loinc/no-hyphen`, `:loinc/multiple-hyphens`, `:loinc/empty-number`,
`:loinc/check-digit-not-single-digit`, `:loinc/invalid-part`,
`:loinc/wrong-axis-count`, `:loinc/empty-csv`, `:loinc/row-field-count-
mismatch`. **Those keywords are contract.** `code/valid?` is the one
predicate in this library that collapses every failure to `false` rather
than a named reason, by design — it exists specifically so a caller can
ask "is this a well-formed, checksum-correct code" without matching on
every possible way "no" could happen.

### Proof these negative tests discriminate

Two guards were deliberately broken during development, one at a time,
to confirm the corresponding tests fail for the *specific* reason and
not merely "something changed":

1. **`loinc.check-digit/double-and-reduce`** — removed the `> 9`
   reduction step (so a doubled digit of, say, 9 -> 18 was left as 18
   instead of reduced to 9). Result: 7 tests failed, all and only the
   ones that depend on check-digit arithmetic being correct
   (`check-digit-matches-published-examples`, `format-code-round-trip`,
   `valid?-true-for-published-codes`, one case of `valid?-false-for-
   wrong-check-digit`) — showing `check-digit "2951"` now returned `3`
   instead of `2`, and `"718"` returned `9` instead of `7`. Every other
   test (structural parsing, the CSV parser, the part model) stayed
   green, confirming the break was isolated to arithmetic. Restored;
   suite back to 0 failures.
2. **`loinc.code/valid?`** — replaced the checksum comparison with
   `(= (first result) :ok)` (accept any structurally-shaped code
   regardless of whether its check digit is correct). Result: exactly
   the 9 sub-assertions of `valid?-false-for-wrong-check-digit` failed
   — one for each of the 9 possible wrong check digits on `2951-*`
   (`2951-0` through `2951-9` excluding the correct `2951-2`), each
   showing the deliberately-wrong code was accepted (`true`) when it
   should have been rejected. Restored; suite back to 0 failures.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

Both: **22 tests, 66 assertions, 0 failures.**

Digit-to-character-code conversion (`loinc.check-digit`'s `digits`, and
the CSV parser's field scanning) uses a portable `char-code`/index-based
approach rather than `int` — see `loinc.check-digit`'s docstring, and
`org-dicomstandard-dicom`'s and `org-modbus`'s READMEs in this workspace,
for the `(int c)`-on-a-character-returns-0-under-ClojureScript trap this
sidesteps. Caught and fixed here *before* the cljs run first passed
(both runtimes were green on the first `verify-cljs.cljs` execution),
by applying the same lesson this workspace had already paid for twice.

## Not here

- **No IO, no sockets, no threads.** `loinc.release-csv/parse` takes
  already-read text; it does not open a file or fetch a URL.
- **No image/PDF/ZIP handling.** LOINC releases ship as a ZIP containing
  several files; this library parses one CSV's *text*, nothing about
  the archive format.
- **No LOINC linguistic variants, mapping tables, panels/forms
  (LOINC Document Ontology), or the RSNA Radiology Playbook.** Only the
  core code format, check digit, and six-axis structural model.
- **No fuzzy/synonym search over component names.** That would need the
  licensed table to search over, which this library doesn't have.

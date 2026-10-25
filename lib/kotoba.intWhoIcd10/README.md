# kotoba-lang/int-who-icd10

**ICD-10 code grammar/validator, chapter-boundary lookup, dagger/asterisk
dual-classification handling, structural comparison, and a parser for the
ClaML release-distribution XML format — in portable `.cljc`, with one
workspace-local dependency (`kotoba-lang/xml`, for the ClaML parser only).
Targets WHO ICD-10, not ICD-11** (see the ICD-11 note below).

Named per this workspace's origin-domain convention: WHO's domain is
`who.int`, whose registrable-domain-label-reversal is `int-who`. (This
workspace already has an existing, differently-prefixed entry for
`who.int` — `kotoba-lang/com-who` — recorded in
`manifest/origin-domains.edn`; that predates the reverse-DNS derivation
rule this repo's own name follows and is a known, unrelated legacy naming
gap, not a reason to rename this repo. See AGENTS.md's repo-naming
section: existing deviations are not retroactively fixed, but new
registrations follow the rule.)

## ⚠ Read this before assuming anything about scope: the licensing boundary

**The ICD-10 classification content — the code-to-diagnosis-label mapping,
the tabular list, the alphabetical index — is WHO copyright.** This repo
does not vendor, embed, download, or reproduce any of that. It ships
**zero disease/condition labels** and **zero substantial code lists**.

What IS here, and exactly why each piece is legitimate:

| Module | What it does | Why it's not licensed content |
|---|---|---|
| `icd10.code` | Validates/parses the **code SHAPE**: `letter + 2 digits`, optional `.` + 1-2 further characters, dagger (`†`)/asterisk (`*`) suffix | Structural grammar. Knowing that `J18.9` is a *syntactically well-formed* ICD-10 code requires no knowledge of what J18.9 *means* |
| `icd10.chapters` | The 22 published chapter **boundaries** (`A00-B99`, `C00-D48`, ...) and which chapter a category code falls in | These ranges are printed in the plain table of contents of every published edition — navigation structure, not the classification |
| `icd10.compare` | Structural code comparison/sorting | Pure algorithm over the code shape |
| `icd10.claml` | A parser for the **ClaML** XML format WHO (and other bodies) use to *distribute* a release, so a licensee with their own copy can load it | The parser understands the container FORMAT; it carries no actual release content. Ships with zero real WHO `Class`/`Rubric` entries — see Test vectors, below |

## What is consequently NOT here, and never will be added to this repo

- **No code → diagnosis-label table.** Given a code, this library cannot
  tell you what it means. That mapping is the classification itself.
- **No tabular list, no alphabetical index, no inclusion/exclusion note
  text.** Any of these, even partially, would be a substantial extract of
  licensed content.
- **A handful of individual codes appear as test fixtures** (`J18.9`,
  `E11.9`, `A00`, `Z99`, `B20`, ...) per this repo's own instructions:
  individual codes cited as syntax examples are not the classification.
  Where a fixture needed example *label text* (the ClaML round-trip test),
  that text is explicitly fictional/placeholder (`"Example condition A"`),
  never real WHO wording — see `test/icd10/claml_test.cljk`'s own comment.
- **If a useful ICD-10 library could not be built within this boundary,
  the right move would have been to say so and ship less.** It could —
  code-shape validation, chapter navigation, and a release-format parser
  are all real, useful, and clean of licensed content — so that is what
  shipped, no more and no less.

## ICD-11 relationship

**ICD-11 is the current WHO revision and is published under a Creative
Commons licence (CC BY-ND 3.0 IGO)** — a materially different legal
situation from ICD-10, and one that would make embedding actual
classification content at least conceivable. **This repo does not attempt
that.** Its target is ICD-10 specifically, per its brief; ICD-11 also has
a different code shape entirely (e.g. `8A61.2`, a different digit/letter
grammar and an extension-code mechanism ICD-10 has no equivalent of) and
would need its own grammar, not a variant flag bolted onto this one. If
ICD-11 support is wanted, it belongs in a sibling repo built against
ICD-11's own (CC-licensed) foundation content, not folded in here.

## Surface

```clojure
(require '[icd10.code :as code] '[icd10.chapters :as ch]
         '[icd10.compare :as cmp] '[icd10.claml :as claml])

(code/parse "J18.9")
;=> [:ok {:letter "J" :category-role :standard :category-digits "18"
;         :category "J18" :subcategory "9" :dagger-asterisk nil :code "J18.9"}]

(code/parse "J188.9")     ;=> [:error :icd10/invalid-category-digits {...}]
(code/parse "A00.999")    ;=> [:error :icd10/invalid-subcategory-shape {...}]

(:title (ch/chapter-for-code "J18.9"))
;=> "Diseases of the respiratory system"

(cmp/sort-codes ["J18.10" "A00" "J18.2"])
;=> {:sorted ("A00" "J18.2" "J18.10") :invalid ()}   ; numeric, not lexicographic

;; ClaML: bring your own licensed release text
(let [[tag doc] (claml/parse (slurp "my-licensed-icd10-release.xml"))]
  (claml/classes-by-code doc))
```

| namespace | |
|---|---|
| `icd10.code` | code shape parse/validate/serialize, `category-letter-role`, `subcategory-warn` |
| `icd10.chapters` | the 22 chapter boundaries, `chapter-for-category`/`chapter-for-code` |
| `icd10.compare` | `compare-codes`, `sort-codes` (structural, not lexicographic) |
| `icd10.claml` | `parse`/`document-str` for the ClaML release-distribution XML format |

## What this is not

- **Not a clinical decision-support tool and carries no medical
  warranty.** This is a syntax/structure library. It makes no claim about
  the clinical correctness, safety, or fitness for any purpose of any
  code, and must not be used, on its own, to make or support a clinical
  decision.
- **Not a coder's assistant, billing/reimbursement tool, or terminology
  service.** No fuzzy matching, no "did you mean", no cross-mapping to
  SNOMED CT or any other terminology (that content is likewise licensed —
  see `kotoba-lang/com-snomed-ct`'s own README for the same boundary
  drawn there).
- **Not a validator against a specific national ICD-10 clinical
  modification** (ICD-10-CM, ICD-10-AM, etc.). Those add their own
  extension characters and rules on top of WHO's base ICD-10; this repo
  targets WHO's base structure. `icd10.code/subcategory-warn`'s I/O
  advisory is the one place a modification-specific convention is
  acknowledged, and it is explicitly advisory, not enforced.
- **No I/O, no threads, no network, no bundled release file.** Every
  function is pure: string/EDN in, EDN out (or a named
  `[:error kw detail]`), nothing else touched. Reading a `.xml` ClaML
  release from disk is the caller's job, and requires the caller's own
  licensed copy.

## The I-and-O and U conventions, precisely

- **`U` is a real, valid category letter** (WHO's own Chapter XXII,
  "Codes for special purposes", spans `U00-U99` — provisional assignment
  of new diseases `U00-U49`, special-purpose codes such as antimicrobial
  resistance `U50-U99`). `icd10.code/parse` accepts it and tags it
  `:category-role :reserved-provisional` rather than `:standard`, so a
  caller can distinguish "shaped like a standing disease-chapter code"
  from "shaped like a provisional/special-purpose one" without rejecting
  either.
- **`I` and `O` are legitimately used as ordinary category letters**
  (Chapter IX, circulatory diseases, is `I00-I99`; Chapter XV, pregnancy,
  is `O00-O99`) — this library does NOT exclude them from the category
  letter position, because doing so would reject real, valid WHO codes.
  The documented "avoid confusion with 1/0" convention this repo's brief
  named is implemented instead as `icd10.code/subcategory-warn`, an
  advisory (never a parse failure) that flags an `I`/`O` specifically in
  the alphanumeric SUBCATEGORY-extension position some national ICD-10
  modifications use — WHO's own base subcategory position is always
  numeric. See that function's docstring for the reasoning in full.

## Test vectors

`test/icd10/code_test.cljk`, `chapters_test.cljc`, and `compare_test.cljc`
use individual code strings (`J18.9`, `E11.9`, `A00`, `B20`, `G63.2*`,
`U07.1`, ...) as syntax examples — the same kind of citation this repo's
own brief explicitly permits. `test/icd10/claml_test.cljk`'s fixture is
entirely constructed (synthetic rubric text, not real WHO wording), marked
`;; constructed, not a published spec vector` at its definition. The 22
chapter boundaries in `icd10.chapters` are structural facts printed in the
table of contents of every published ICD-10 edition; `chapters_test.cljc`
checks internal consistency of that table against itself, not against any
external source this repo would need to cite as a "spec vector" per se.

## Verify

```sh
kbb -M:test                                              # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

Both runtimes run the identical suite (18 tests / 99 assertions).

# kotoba-lang/org-openehr

**An openEHR Archetype Definition Language (ADL) **1.4** parser and
serializer — cADL constraint grammar, dADL data grammar, and the Reference
Model path syntax — in portable `.cljc`, with no dependencies.**

Named the same way this workspace names spec-origin repos: reverse-DNS of
the specifying body's domain (`openehr.org`), not a language suffix — see
`kotoba-lang/org-modbus` and `kotoba-lang/org-ietf-smtp`, whose structure
this repo's is directly modeled on.

## ADL version: 1.4, not 2.x — and the two are not blurred here

openEHR has published two materially different serializations of an
archetype:

- **ADL 1.4** — the classic plain-text Eiffel-flavoured syntax
  (`archetype (adl_version=1.4)` header, `cADL` constraint blocks using
  `matches {...}`, `dADL` data blocks using `<...>`). Specified at
  <https://specifications.openehr.org/releases/AM/latest/ADL1.4.html>.
- **ADL 2.x** — a redesigned syntax (different header form, `Cluster`/
  primitive-object literal forms, an XML canonical form, formal BNF in the
  AOM2 specification) that is not a superset or a simple version bump of
  1.4; several constructs parse differently or don't exist in the other
  dialect.

**This library implements ADL 1.4 only.** It was written and tested
against two openEHR-org-published ADL 1.4 archetypes (see Test vectors,
below) — real files with `archetype (adl_version=1.4)` headers. It will
reject (with a named `[:error :adl/... ...]`, never a silent
misinterpretation) an ADL 2.x document, because the header/section/literal
grammar is different enough that "supporting both" would mean silently
guessing which dialect a given file is, which is exactly the kind of blur
this repo's brief said not to introduce. If ADL 2.x support is wanted, it
belongs in a second, explicitly-versioned parser (`adl2` namespace or a
sibling repo) built against AOM2's own BNF — not folded into this one.

## What this is

Four namespaces, each usable standalone:

- **`adl.lexer`** — shared character-level scanning: whitespace/comment
  skipping, identifiers, quoted strings, numbers. Every parser here is a
  direct recursive-descent scan over the source string (`[s i] -> [value
  next-index]`), the same style as this workspace's `kotoba-lang/xml` and
  `kotoba-lang/org-dnp3` — not a separate tokenizer pass, because cADL's
  grammar is context-sensitive by nesting DEPTH (see `adl.cadl`'s
  docstring) in a way a flat token stream would make awkward to express.
- **`adl.dadl`** — dADL: the `<key = <value> ...>` / `<["k"] = <value>
  ...>` data syntax used by the `language`, `description`, `ontology`,
  `revision_history` and `annotations` sections, plus the
  `TYPE <key = <value>>` primitive-constraint-object form cADL reuses
  verbatim (e.g. `C_DV_QUANTITY <property = <...> list = <...>>`).
- **`adl.cadl`** — cADL: the constraint grammar of the `definition`
  section. Object node constraints (`OBSERVATION[at0000] matches {...}`),
  attribute constraints with `existence`/`cardinality` bounds, occurrence
  intervals (`{0..1}`, `{1..*; unordered}`), primitive constraint types
  (`C_DV_QUANTITY`, `C_CODE_PHRASE`-shaped `defining_code matches
  {[...]}`, `C_DATE_TIME`-family `DV_DATE_TIME matches {*}`), enumerations
  (booleans, plain literals, and ordinal `N|[code]` lists), archetype
  slots (`allow_archetype TYPE[id] ... {include/exclude archetype_id/value
  matches {/regex/}}`), and `use_node` subtree reuse.
- **`adl.archetype`** — the whole-document grammar: header
  (`archetype (adl_version=1.4)` + archetype id), `concept`, and the
  section sequence, dispatching each section to `adl.dadl` or `adl.cadl`.
  `invariant` (OCL-like assertions) is captured as an opaque
  bracket-depth-balanced block and round-tripped verbatim — a full OCL
  grammar is out of scope for an RM-path-and-constraint parser.
- **`adl.path`** — the openEHR Reference Model path syntax
  (`/content[openEHR-EHR-SECTION.x.v1]/items[at0001]/value`), with
  predicate handling for archetype node ids (`[at0001]`, optionally with a
  `, 'display name'`), name/value predicates
  (`[name/value='Systolic']`, `and`-chainable), and archetype-id
  predicates (`[openEHR-EHR-SECTION.x.v1]`) — including predicates that mix
  more than one of these in a single bracket
  (`[at0001 and name/value='Systolic']`), and a quote-aware bracket scanner
  so a `/` or `]` quoted inside a predicate's value doesn't terminate the
  segment or bracket early.

```clojure
(require '[adl.archetype :as arch] '[adl.dadl :as dadl]
         '[adl.cadl :as cadl] '[adl.path :as path])

(let [[tag archetype] (arch/parse (slurp "openEHR-EHR-OBSERVATION.blood_pressure.v2.adl"))]
  (:archetype-id archetype))
;=> "openEHR-EHR-OBSERVATION.demo.v1"

(arch/serialize archetype)  ;=> re-parses to the same structure

(path/parse "/data[at0001]/events[at0002, 'Any event']/data[at0003]/items[at0004]")
;=> [:ok {:absolute? true :segments [...]}]
```

## Relation to `org-hl7-v2` (already in this workspace)

`org-hl7-v2` implements HL7 v2's ER7 wire encoding and MLLP framing — a
*messaging* transport for clinical data exchanged between systems.
openEHR/ADL is a different layer entirely: it is a *modeling* language for
defining the shape and constraints of clinical data (an archetype), not a
message format. The two are complementary in real deployments (an HL7 v2
OBX segment's value might, in a downstream system, populate a field an
openEHR archetype constrains) but neither implements the other, and this
repo does not duplicate `org-hl7-v2`'s wire-format work.

## What this is not

- **Not an archetype editor, validator against a live Reference Model, or
  Clinical Knowledge Manager.** This parses and serializes ADL 1.4 text;
  it does not check an archetype's constraints against actual openEHR RM
  class definitions, does not resolve archetype specialisation/inheritance
  (an archetype whose id ends `.v2` overriding `.v1` node by node), and
  does not evaluate the `invariant` section's OCL-like assertions (they
  are captured as opaque text, not interpreted).
- **Not a template (OET/OPT) processor.** Templates compose multiple
  archetypes and apply additional constraints on top; that is a separate,
  larger grammar this repo does not attempt.
- **Not the archetype-XML (aXML) canonical serialization.** Only the
  plain-text ADL 1.4 syntax is handled. (If aXML support is added later,
  `kotoba-lang/xml` — already in this workspace, reused rather than
  reimplemented for that purpose if it happens — is the right XML layer to
  build it on; it was not needed for this repo's actual scope, ADL 1.4
  text.)
- **No I/O, no threads, no network.** Every function here is pure:
  string in, EDN out (or a named `[:error kw detail]`), nothing else
  touched. Reading a `.adl` file from disk is the caller's job.
- **Not a clinical decision-support tool and carries no medical
  warranty.** This is a syntax parser for a modeling language. It makes no
  claim about the clinical correctness, safety, or fitness for any
  purpose of any archetype it parses, and must not be used, on its own,
  to make or support a clinical decision. See LICENSE.

## Test vectors

Two real archetypes published by the openEHR organization on GitHub are
embedded verbatim in `test/adl/fixtures.cljk` (cited by source URL there)
and driven through full parse → serialize → re-parse round-trip tests:

- `openEHR-EHR-OBSERVATION.demo.v1` — openEHR/adl-archetypes (every
  primitive datatype: intervals, ordinals, proportions, durations,
  multimedia, coded text with internal and external terminology).
- `openEHR-EHR-OBSERVATION.intravascular_pressure.v1` — openEHR/adl-archetypes
  (a real clinical archetype: archetype slots, `use_node` subtree reuse,
  ordinal and coded-text constraints).

Both files contain one real-world quirk each worth naming explicitly: a
literal `...` ellipsis left by the archetype's original author as an
authoring placeholder in an example list (`other_contributors = <"...",
...>`), which is not part of ADL's own grammar but is accepted and
round-tripped by `adl.dadl` (see its `:ellipsis` handling) rather than
rejected, since refusing to parse real published content over one
non-conformant token would make this library less useful than tolerating
it.

A handful of additional constructed cases (invariant/annotations
sections, generic type parameters, composite path predicates) are used
where the real fixtures don't happen to exercise a grammar rule; every
such case is commented `;; constructed, not a published spec vector` at
its definition.

## Verify

```sh
kbb -M:test                                              # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

Both runtimes run the identical suite (40 tests / 250 assertions) against
the identical embedded fixture text.

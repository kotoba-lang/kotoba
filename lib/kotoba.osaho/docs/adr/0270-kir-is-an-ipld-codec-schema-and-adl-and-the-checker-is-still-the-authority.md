# ADR-0270: KIR is an IPLD codec, schema and ADL -- and the checker is still the authority

- Status: accepted
- Date: 2026-09-07
- Root decision: com-junkawasaki/root ADR `adr-2609076000-kir-is-an-ipld-codec-schema-and-adl`

## Context

This repository already content-addresses KIR. `kotoba.kir.definition-identity`
normalizes a checked definition to a closed, injective, tagged form and encodes
it with a deterministic CBOR encoder, then labels the result a CIDv1 dag-cbor.
Payload v2 exists because v1 hashed `(pr-str canonical-edn)` and called the
result dag-cbor: the block did not decode as dag-cbor, and `pr-str` is not
byte-identical across Clojure and ClojureScript.

So the bytes are DAG-CBOR. What this repository does **not** do is get them
from the layer that owns DAG-CBOR. `deps.edn` requires `io-multiformats`,
`org-ietf-cbor`, `org-nist-sha2`, `kotoba-hir` and `security` -- not
`io-ipld`. `definition-identity` requires `cbor.core` and `multiformats.core`
directly and hand-writes its own `normalize`, `rank` and `cmp`.

`kotoba-lang/io-ipld` owns the other one. `kotoba.value.codec` is the
language-facing facade over the canonical `kotoba.value.v1` codec, and its own
docstring names the consumers: *compiler, provider, actor, and I/O
boundaries should require this namespace instead*. This repository is a
compiler boundary and does not.

Measured 2026-09-07, on the sources at their remote main, through nbb with
both on the classpath. The two normalizations converged on the same
architecture -- a closed injective tagged 2-tuple in canonical CBOR, so a
keyword can never collide with the string of the same name -- and share no
byte:

| value | this repository (payload v2) | `kotoba.value.v1` |
|---|---|---|
| tag | string: `int` `f64` `str` `kw` | integer: `2` `3` `4` `5` `9` |
| `5` | `["int" "5"]` -> `8263696e746135` | `[2 5]` -> `820205` |
| i64 max | `["int" "9223372036854775807"]`, decimal **text** -> `8263696e747339323233333732303336383534373735383037` | `[9 <8 byte BE two's complement>]` -> `8209487fffffffffffffff` |
| `1.5` | `["f64" "3ff8000000000000"]`, 16 hex **text** -> `82636636347033666638303030303030303030303030` | `[3 <8 byte float>]` -> `8203483ff8000000000000` |
| `"a"` | `["str" "a"]` -> `82637374726161` | `[4 "a"]` -> `82046161` |
| `:a` | `["kw" "a"]` -> `82626b776161` | `[5 "a"]` -> `82056161` |

Neither choice is a mistake. Numbers are carried here as exact text because a
64-bit KIR literal exceeds the JavaScript exact-integer range and text keeps
`:clj` and `:cljs` on the same bytes. `kotoba.value.v1` carries exact i64 as
append-only scalar code 9 with an 8-byte big-endian payload so a BigInt never
routes through CBOR's Number integer path. The defect is that nothing forces
them to agree.

The two do not even agree on what an exact i64 *input* is.
`ipld.value/int64` refuses the decimal string with `int64-not-an-exact-integer`
and requires a `js/BigInt`; `i64` here stringifies whatever it is handed. That
is **not a live break**: `normalize` refuses raw out-of-range integers and raw
platform floats outright, and amu's `canonical-value` detects `js/BigInt`
before this namespace sees a literal, which is why the JVM route and the
JDK-free nbb route mint byte-identical CIDs. It is the shape of the risk --
two contracts for one scalar, enforced in two places, kept aligned by a
caller.

This repository has already resolved this exact shape once. The
alpha-normalization walk lived here **and** in `kotoba.codebase.typed-code`:
the same algorithm, over the same KIR, in two places, with neither one the
authority. kotoba-lang `lang/code-identity.edn` recorded it as a residual risk
of `:ci8` and named the fix as a single owner here, not a third place; it
landed 2026-09-02 as `kotoba.kir.alpha-normalization`. The encoder is the same
finding one layer down.

## Decision

**1. The canonical bytes come from `io-ipld`, not from a second value model
in this repository.** `kotoba-kir` takes a dependency on `io-ipld`. This is
acyclic: `io-ipld` depends only on `dev-protobuf`, `io-multiformats` and
`org-ietf-cbor`, and this repository already carries the latter two.

> **Refined 2026-09-07 by the measurement below.** This read *a second
> normalization* and conflated two layers. **The codec is already shared** --
> both encoders are `(cbor/encode <tagged form>)` over the same `cbor.core`
> from `org-ietf-cbor`, and there is no second DAG-CBOR encoder here to unify.
> What differs is the VALUE MODEL above it, and moving it is payload v3, not a
> refactor. The dependency is landed **test-only** for now, which is what
> measuring the gap costs; promoting it to `:deps` is the v3 decision.

**2. The KIR block shape is an explicit IPLD Schema**, written in
`ipld.schema-dsl` and validated as Schema DMT by `ipld.schema/compile-schema`.
Structure, references, representation tables and named-reference closure are
pinned there rather than in prose.

**3. Packed KIR representations are ADLs through the existing boundary** --
`ipld-adl-wasm-v1`, module pinned by raw CID, caller-declared fuel and output
budgets, receipts recording module plus input and output CIDs. No second ADL
mechanism, and no ADL transform that is not itself a Kotoba artifact.

**4. The schema pins shape. It does not pin checkedness, and the two MUST be
distinguishable in the output.** KIR is a *checked* IR: native typed-feature
admission, the closed scalar-variant export boundary (qualified name, 1..32
unique cases, `:i64`/`:bool` payloads), typing, effect rows, the lowering
budget. IPLD Schema validation is structural and representational. It cannot
express "this effect row is the transitive semantic closure of the calls this
definition makes", and it has no cardinality constraints, so it cannot express
the variant bound either.

Therefore a block that validates against the KIR schema and then **fails
admission** must not report what one that passes both reports.
`compile-schema` returning green is not "valid KIR". Admission is carried the
way `ipld.schema` already carries advanced representations: a caller-owned
required capability that fails closed when absent. A missing checker is a
refusal, never a pass -- the same reason `ipld.schema` will not execute an
advanced representation without a validator capability.

**5. The DefCID seals the logical form only.** Schema version and
representation version MUST NOT enter the identity payload. Sealing them would
move every definition's identity on a purely representational change, such as
adding a union representation; not sealing them while letting the encoder vary
would give one meaning two identities. The seam is the one `ipld.schema`
already provides: `representation->logical!` and `logical->representation!`.
The six sealed inputs named by `lang/code-identity.edn` -- typed KIR, profile
version, desugar contract version, effect row, interface, direct definition
dependencies -- are unchanged.

**6. If any canonical byte moves, that is payload v3, announced as such.**
Payload v2 says v2 CIDs are deliberately not v1 CIDs; v3 says the same about
v2. Every frozen vector in kotoba-lang `lang/code-identity-vectors.edn`, every
module lock and every compile cache key moves with it. A change presented as
"unifying the encoders" that silently moves DefCIDs is refused.

**7. Kototama's program form is not KIR.** The Kototama reduction plane is a
closed S-expression whose canonical wire form is tagged DAG-CBOR vectors
(`kototama` `spec/kototama-vm-v1.edn`, `:planes :reduction`). Giving KIR a
schema does not make KIR the VM's instruction form. Two schemas, two layers,
and they stay two; unifying them is a separate decision with its own evidence.

## What is not claimed

- No incorrect CID was measured. The two encoders are reachable from one
  codebase and disagree; the compiler keeps its side exact by hand.
- The KIR IPLD Schema is not written. This ADR decides the form and the owner.
- There is no gate for encoder agreement yet, and this ADR does not invent
  one. See below.

## Measured 2026-09-07 -- the next step, executed

`kotoba.kir-value-codec-differential-test`, over this repository's own copy of
the frozen vectors (verified byte-identical to the kotoba-lang authority), with
`io-ipld` pinned in the `:test` alias only.

**All ten vectors reproduce byte-for-byte through `canonical-bytes`, and all
ten disagree with `kotoba.value.v1`.** Payload v3 IS needed. The value codec
does not *refuse* the payload -- it accepts all ten and returns different bytes
-- which is asserted separately, so a refusal can never be miscounted as a
disagreement.

Three independent dimensions, not a tag rename:

| | `normalize` (here) | `value->form` |
|---|---|---|
| tag alphabet | strings `map` `kw` `set` `int` `str` | integers `19` `5` `18` `2` `4` |
| scalar payload | integers as exact decimal **text** | native integers, scalar code 9 for exact i64 |
| map key order | its own `rank`/`cmp` | DAG-CBOR canonical **length-first** |

Neither key order is wrong: `normalize` never emits a CBOR map, it emits
`["map" [pairs]]`, so the codec's ordering rule does not bind it. A migration
that changed only the tag alphabet would still move every CID through the
other two.

Both directions were shown before calling it landed. Perturbing one frozen hex
fails the golden half naming that vector; simulating a closed gap fails the
debt marker with the payload-v3 message and the list of newly-agreeing
vectors. Restored, it is green again, and the full suite passes with the new
test dependency.

**Incidental finding.** This repository's top-level `io-multiformats` pin is 37
commits behind that repository's main and predates `multiformats.base32`, which
`ipld.link` needs. The test alias overrides it rather than moving the runtime
pin, because moving a runtime pin is a separate change with its own risk -- and
the frozen-CID assertions passing under the override are evidence those 37
commits do not move CID assembly.

## Still to decide

Whether to pay payload v3. The cost is measured; the benefit -- one value model
instead of two -- is unchanged. **This ADR does not decide it.** Decision 1
says where the bytes should come from; the price turned out to be a version
bump touching every locked identity in the workspace. That is an owner
decision, and the differential test is what stops it happening by accident.

# 0009 — Stack topology position, browser-parity gate, and canonical capability schema

Current architecture direction (2026-10-10): Wasm is one AMU target, target ABI
profiles are separate from neutral contracts, and distribution/consensus
profiles are independent of execution targets. Tier numbers are ownership
labels, not dependency ranks. The coordinated owner guide is
[stack architecture](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/stack-architecture-target-neutral.ja.md);
[current dependency measurements](https://github.com/kotoba-lang/kotoba-lang/blob/main/lang/stack-dependency-observation.edn)
remain distinct from intended migration. Existing runtime schemas and historical
qualification evidence are not changed by this documentation.

Status: accepted
Date: 2026-07-24
Amended: 2026-08-30 by `docs/kototama-virtual-machine.md`. The host/runtime
responsibilities below remain valid, but they are now explicitly one
implementation surface of the wider Kototama VM contract.
Root authority: `com-junkawasaki/root` ADR-2607241100 (kotoba stack topology
and design cleanup). This ADR is the kototama-repo mirror; the canonical
topology and the full cross-repo cleanup list live there.

## Position in the stack topology

Updated 2026-10-10 against fetched main manifests. The
[stack architecture](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/stack-architecture.md) and
[composition contract](https://github.com/kotoba-lang/kotoba-lang/blob/main/lang/stack-architecture.edn) distinguish responsibility, library,
artifact and runtime/service graphs.

```text
kotoba-lang = language contracts (T1)
kotoba      = CLI, libraries and Codebase
amu         = compiler and project linker (T2)
abi         = shared execution contract (T0)
kototama    = Lisp VM contract; engines implement it (T3)
grant       = pure permission decisions (T4); authority owns scope/delegation
aiueos      = operating system (T5); enforces grant's answer
sahai       = reusable placement (T6); murakumo operates its own inference fleet
kotobase    = database and persistent data plane
```

AiueOS is the OS for a modern Kotoba Lisp machine in development; Kototama is
its Lisp VM contract, also implemented by hosted engines. These are
architectural roles, not completion/qualification claims.

Library arrows mean consumer → dependency: Kotoba imports Amu and Kototama;
Kototama imports grant and abi; AiueOS imports grant; grant imports authority
and abi and does not import the OS. Amu imports contracts and multiple
backends. Alias-only dependencies must be labelled separately.
The booted kernel consumes verified compiler artifacts rather than linking
the compiler. Host build/conformance aliases may import compiler libraries.
The database/language boundary describes ownership, not a claim that every
database runtime directly imports the Kotoba CLI.

The July 2026 topology snapshot was corrected on 2026-10-10 after the grant
split and VM-contract separation; its old dependency counts and “AiueOS
decides” wording are not current invariants.

## Decision 1 — new `actor:host` imports require 2-runtime parity in the same wave

The application-profile completion gate (#6, `kotoba-lang/kotoba`
`docs/lang/application-profile.md`) already requires parity evidence across
at least two runtimes before a capability family is "implemented" — yet the
ADR-2607230943 second wave (`http-fetch`/`cbor-encode`/`json-encode`/
`json-extract-field`) and the third wave (`http-post-headers`) landed
JVM-tender-only, moving browser parity from 9/9 to 9/14. `docs/maturity.md`
records this honestly, but honesty in a doc is not enforcement.

**Decision:** a PR adding a new `actor:host` import to `kototama.contract`
must either (a) land the `wasm-webcomponent` browser wiring in the same wave
(cross-repo PR pair), or (b) carry an explicit waiver note in the PR body AND
a same-PR `docs/maturity.md` parity-table update marking the gap. The parity
score in `kbb -M:cli parity` is the machine check; CI should fail a
contract change that does not update the parity matrix.

The former 5-import backlog (`http-fetch`/`cbor-encode`/`json-encode`/
`json-extract-field`/`http-post-headers`) was closed by the codec port and
`wasm-webcomponent` PR #15; 14/14 is now the enforced baseline. Any future debt must be burned
down under this rule, not grandfathered forever.

## Decision 2 — `HostCaps` and grant vocabulary derive from one canonical schema

Today the capability vocabulary exists in four hand-maintained forms: the
compiler's closed host-import table, `kototama.contract`'s `HostCaps`,
grant's decision vocabulary, aiueos's kernel handles, and their adapter translation.
`kototama.aiueos_adapter` covers only the 3 imports that have aiueos-kernel
counterparts (`log-write`/`clock-monotonic`/`random-bytes`); the rest take
caller-supplied `HostCaps`. This is the historical coverage finding; current
coverage must be measured against grant decisions and the selected host profile.

**Decision:** adopt the canonical typed capability-descriptor schema
(application-profile completion-gate item 1) as the single source; generate
`HostCaps` field-by-field from it, and extend the grant decision vocabulary so
every `actor:host` import has a decidable counterpart. Hand-written adapter
coverage gaps become schema-coverage gaps, which are mechanically listable.

## Decision 3 — the two Chicory compat paths share fixtures, not code

`kototama.tender` and `kotoba-lang/kotoba`'s `kotoba.wasm-exec` are two
deliberately separate JVM/Chicory bootstraps (com-junkawasaki/root
ADR-2607182200: no cross-repo test dependency). Keep the two implementations,
but move the checked-in `.wasm` conformance fixtures
(`test/kototama/fixtures/kotoba-compiled-*.wasm`) toward a shared
fixture set that both repos consume, so the justification completes: two
implementations, one oracle.

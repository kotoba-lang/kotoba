# Canonical Linux-static planning and layout source port

Update: [complete vector arena composition](linux-static-vectors-port.md)
extends the source to sixteen implemented slots and real vector table/item
regions. The initial counts and eight-slot evidence below are provenance.

Tracking: [JUN-201](https://linear.app/kotobalabs/issue/JUN-201),
[JUN-200](https://linear.app/kotobalabs/issue/JUN-200).

`src/kotoba/native/linux_static_plan.kotoba` ports the complete public
planning and image-layout boundary from `linux_static.cljk` at owning main
`535ca0a3e7ec1c4b4496c8ea12b18436838cbb47` (reference blob
`0ab7132ae38f4fd6fb75b107909c1854559160cf`). It uses canonical document
operations and the owning artifact seal verifier. It imports no hosted
encoder, numeric conversion, C loader, process wrapper or external assembler.

This is a source candidate. No compiler build, native admission, runtime
operation or test was run. It does not yet replace the hosted packager or
produce a qualified ELF/compiler generation.

Candidate source SHA-256:
`40dde90afbb66e30c821b2cf0cef96f61b9ee0bcad9adf5ab7c0781840953d4e`.
Static inventory found balanced delimiters, matching own-function arities,
no unresolved source call heads, both target profiles, the eight implemented
slots and all 13 scratch-region names. This does not measure executed behavior.

## Public contract

| Export | Boundary |
| --- | --- |
| `targets []` | Return both existing target profiles, ISA/machine names and hidden context registers |
| `implemented-slots []` | Return the actual eight slots of the reference static prelude; do not claim unimplemented vector/byte slots |
| `slot-names [context]` | Enumerate callable `-offset` entries, exclude the same eight context data words, and order by slot name |
| `plan [artifact profile overrides]` | Read the complete native profile and derive budgets, grants, handlers, slot admission, trap/exit names and context |
| `image-layout [text-size plan]` | Compute text/data, alternate stack, pair/validation/string arenas and all 13 optional capability scratch regions |

The two former exported table values become zero-argument accessors, and
`plan` takes an explicit overrides document (an empty map for the old default
arity). Each fallible operation returns `:linux.static.plan/result`, with
`value`, `error` and `data`. Only `error=:ok` authorizes using `value`.
Failures replace host exceptions; callers must propagate them. API and
Definition CID integration remain open.

As in the reference, `plan` operates on artifact metadata already admitted
by its caller. The final `package` entry must verify the main artifact seal,
target and zero-arity exported entry before using the plan. Handler artifacts
are separately seal-checked inside this module; no caller-supplied verifier
callback or pre-approved flag can bypass that check.

## Preserved decisions

- Budgets may vary only within the profile's cell/byte maxima. Fuel,
  metering, trap names and required exit codes are read from their declared
  owners; no replacement success status or hardcoded policy is substituted.
- Pure `:state` / `:abort` abilities do not create external authority. Capability
  effects are explicit wire calls. Handlers must exist for every effect, and
  an override grant can only narrow those effects. An empty explicit grant
  stays empty. A pure program leaves typed-cap-call unadmitted.
- Filesystem scope is absent or a canonical absolute path. Spawn remains
  inert unless wire 20 is granted, with at most 16 distinct canonical program
  paths, unambiguous basenames when lookup is enabled, and at most 16 bounded
  environment names without NUL or `=`. No ambient PATH or environment is added.
- Capability programs require both sealed, ISA-matched decision artifacts
  and their named exports. Normalized code bytes and export offsets accompany
  the plan; a missing handler is a refusal.
- An admitted slot absent from the implemented-slot set is refused. Every
  other context slot retains its unimplemented-trap disposition. Context ABI
  version 11 is the reference prelude's implemented format; this is not a
  requirement to pin or run a C loader. Other required native ABI versions
  still need implementation and qualification.
- Layout retains the original 4096-byte page, image base, alternate stack,
  pair/validation/string arenas, alignment, and every capability scratch
  region, including spawn, resolved scope root and browse name/index arenas.
  Intermediate addresses, products, alignment and region sums now reject
  signed i64 overflow explicitly.

Canonical numeric inputs are i64 documents, without JavaScript Number
coercion. Additional malformed-input refusals cover document shapes, wire
ids outside the 256-bit grant mask, invalid handler bytes/export offsets,
missing actual trap exit codes and layout overflow. Refusal precedence when
several inputs are malformed is not claimed byte/diagnostic-identical to the
old exception path. Slot ordering explicitly compares UTF-16 code units to
preserve the reference keyword-name order even for supplementary Unicode
characters. Native whole-component behavior and ordering still need
qualification; static source coverage is not runtime parity.

## Verified source dependency and remaining integration

Artifact [#68](https://github.com/kotoba-lang/artifact/pull/68) is merged at
`5ec6362ca5fbc4b0ce07f5ee7e0dcfdeab1fd3ea`. Its canonical `core.kotoba` blob
`ff7f780734f55b730505023522a3c76b11cb46d9` matches the current remote main
readback and exports `valid-seal?`. The local artifact checkout is older and
has staged WIP; it was preserved. A staged file was not used as proof of main.

The existing owning `deps.edn` artifact pin `af43fc8f...` predates this source
and requires a reviewed canonical pin/closure update for a standalone build.
Amu's current root lock instead selects `ce6f82d398467ba5504c8d377b47a8ca2dc185c3`,
whose tree already contains the exact canonical blob above. Do not invent a
missing-core blocker for that root-lock route. Do not bulk-replace the old pin
with an unreviewed history range, or retain a C-loader identity as a native
acceptance condition. The canonical artifact printer/seal behavior and
declared `hash/sha256` capability also require native qualification.

The current remote `lang/limits.edn` blob
`9549aaf1fd92f975d8f58b1b7c80e8df95cfd153` lists static capability handlers
for wires 7, 20, 23, 33, 34, 35, 37, 38, 39 and 41. It does not include wire
3 (`hash/sha256`), which the canonical seal verifier calls. Thus the current
static profile cannot qualify running this planner's seal verification.
Implement the native hash provider and its owning profile/admission binding;
retaining the real seal check is required. Source presence in the root lock
does not establish provider availability.

The companion [SHA-256 computation source](linux-static-sha256-port.md) now
emits a private register-IR routine for the missing computation. Layout now
appends a 16-byte-aligned `:hash-workspace`, sized by that source's
`workspace-bytes` accessor (816), only when wire 3 is in the narrowed grant.
It follows the existing 13 scratch regions; plans without wire 3 retain their
original layout. Malformed grants and a hash grant without handlers are refused,
and the extra region uses the same checked size/address arithmetic.

The [C1/C3 gate source](linux-static-capability-port.md) adds request/result
handle validation and hash-result interning. Owning decision routing, handler
body/text placement, full profile/admission integration and native qualification
are still required. None of these candidates has been generated, assembled or
executed, so wire 3 remains unavailable in the current profile. Do not enable a
handler merely because this source exists.

The [prelude/context candidate](linux-static-prelude-port.md) now supplies
complete startup/signal/trap/slot composition and initialized data binding.
The [complete image source candidate](linux-static-image-port.md) now supplies
handler/guest text placement, both assembly passes, context and owning ELF
framing. Native admission/behavior/verification and exact reviewed source/lock
pins remain open. The compiler's required
vector/string/byte/I/O helper coverage and self-rebuild generations remain
open under JUN-200 / JUN-202. This module grants no production cutover or
service-stop authority.

The [pair/string runtime source](linux-static-strings-port.md) now covers all
seven corresponding slots in the reference and supplies inline request/result
and pool-interning fragments to the new gate. It does not implement vector/byte
helpers. The separate prelude candidate composes these bodies; the planner's
implemented/admitted sets and native qualification remain separate decisions.

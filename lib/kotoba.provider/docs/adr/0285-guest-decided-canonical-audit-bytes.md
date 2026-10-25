# ADR 0285: the guest decides the canonical audit bytes (secret kit)

- Status: Accepted
- Date: 2026-08-12
- Depends: provider ADR 0256 host EDN codec wire; ADR 0284 bounded canonical
  value wire; kotoba-lang canonical value codec (`kotoba.value.v1`)

## Context

ADR 0284 put bounded canonical `kotoba.value.v1` bytes on every ops-audit
event, and named its own residual in decision 4: EDN stays "**while the guest
W4 packages still export text**". That is the shape this closes for one kit.

Until now the byte sequence was decided on the host. A W4 guest package emitted
EDN text, and `provider.value-codec/legacy-edn->audit-bytes` parsed that text
and re-encoded it canonically. The audit event therefore recorded bytes the
guest never produced and could not have produced — the host's encoder was doing
the part of the work that the canonical codec exists to pin down: type tagging,
key ordering, and the exact CBOR spelling.

## Decision

1. Ship `:secret-value-wire` (`src/secret_value_wire.kotoba`), a pure guest
   package that emits the canonical bytes of a `:provider.ops-audit/v1`
   envelope for all three secret arms — request, reply-value, reply-error.
2. The bytes leave the guest as **lowercase hex over the typed string export
   ABI**, which carries strings and i64 only. Hex is transport, not a second
   encoding: the host un-hexes byte-for-byte and makes no semantic choice.
3. Add `provider.value-codec/hex->bytes` and `guest-hex->audit-bytes`. The
   latter **admits** rather than repairs: the bytes must decode as this
   envelope, in canonical form, naming the expected kit and direction.
   Non-canonical map order is rejected, not sorted.
4. `wrap-secret-fetch` prefers guest bytes and falls back to the ADR 0284
   legacy bridge, and now emits `:request-value-source` / `:reply-value-source`
   (`:guest` or `:host-legacy`). The two are not the same claim and the event
   says which one it is.
5. Declare `:guest-value-wire :implemented` **on the secret kit only**, and
   surface it through `kit-package`. The other five ops kits are unchanged and
   still on the legacy bridge.
6. `:wasm-aot` stays `:partial`. Host fetch authority is untouched.

## Evidence

- Guest bytes equal `provider.value-codec/encode-audit-value` byte-for-byte for
  all three arms (`provider.value-wire-test`, 7 tests / 54 assertions).
- Full provider suite green with the change: **254 tests / 2582 assertions**,
  0 failures, 0 errors.
- Package `main` → `-2407`; registry digest
  `b99d3436918cafc4e17897c5500a0a90034444227371d3bd5caab434f2ac276c`,
  reproduced byte-identically from source with compiler `806f5cef`.
- The folded hex literals are asserted equal to what the module's own exported
  `kw_form` produces **and** to what the host codec produces, so no constant in
  the module is an unreviewable magic number.
- Reject paths measured fail-closed: empty name, `"`, `\`, non-ASCII, >128.

## Consequences and costs, measured

- **The guest arena is a bump allocator with no reclamation.** One instance
  serves 18 `secret_request_audit_hex` calls and 10 `secret_reply_error_audit_hex`
  calls before it traps `unreachable`. This is safe on the provider path only
  because `invoke-export` spawns a fresh Node process per call. A host that
  reuses one instance will hit this. The first draft, deriving every keyword
  form per call with two-nibble hex, managed five.
- **Four guest invocations per audited secret fetch, up from two** (request and
  reply × EDN and value). This is audit machinery, not the authority path.
- ASCII-only. A code point ≥ 128 fails closed, because the CBOR text header
  carries a **byte** length and this slice does not encode multi-byte UTF-8.
- Admission is held identical to `kotoba.secret.record-kv-edn` (ADR 0251),
  including its `"` / `\` rejection, which the canonical wire does not need.
  Deliberate: the two evidence fields on one event must not disagree about what
  was admitted. Widening is a separate decision.

## Residual — what this does NOT close

- **Five of six ops kits.** http, process, git, entropy, scoped-fs still emit
  EDN text and are still re-encoded by the host.
- **Ordering for runtime-shaped maps.** Every shape here is closed at author
  time, so canonical key order is a compile-time constant in the guest. A guest
  that must order keys it does not know at author time needs the encoded-bytes
  comparison itself, which is not written.
- **Multi-byte UTF-8**, and text ≥ 64 KiB (the 2-byte CBOR length is
  implemented; anything longer fails closed).
- `:request-edn` / `:reply-edn` remain on the secret event as compatibility
  evidence. This ADR does not retire them.

## Incidental finding (not fixed here)

`lang/guest-grammar.edn` — the source-surface authority — admits `rem` in
`:admitted-builtins` and `string=` in `:predicates`, but the compiler rejects
both with `:kotoba.error/subset-reject` "operation has no admitted lowering".
Measured 2026-08-12 against compiler `806f5cef`. That is authority-to-frontend
drift of the kind ADR-2607279200 Delivery #1 exists to catch; it belongs to the
compiler/kotoba-lang side, not here. This module works around it with
`bit-and` and `string-contains?`.

## Related

- ADR 0256 (host EDN codec wire, the residual this starts closing)
- ADR 0284 (bounded canonical value wire; its decision 4 named this)
- ADR 0251 (secret W4 record-kv EDN, whose admission rules are mirrored)

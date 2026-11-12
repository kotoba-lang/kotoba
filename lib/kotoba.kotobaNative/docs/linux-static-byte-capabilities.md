# Raw-byte filesystem capability source candidate

This extends the complete canonical Linux-static provider candidate. It is
not an activated GMIR contract, admitted artifact, runtime receipt or CI gate.
No compiler/generator/assembler/provider was executed and no tests were added
or run.

## Closed request/result contracts

The compiler-port draft proposed these discriminators. Both ABI metadata
words carry the same whole-contract discriminator; they are not independent
primitive type numbers.

| Kind | Contract | Wire / provider / handler | FS2 forms |
| --- | --- | --- | --- |
| 1 | string / string | existing routes | all original forms |
| 8, `bytes-v1` | bytes / bytes | 35 / 5 / 7 only | write (1), append (2) |
| 9, `string-bytes-v1` | string / bytes | 35 / 5 / 7 only | read (0), range (4) |

The grant bitmap and equal-contract check still run first. Canonical C1 now
routes kinds 8/9 only to fs/app-data wire 35. The C3 mechanism additionally
requires handler 7. Owning handler op 49 constrains the form before path
resolution or target access. Unknown contracts/forms refuse. No new wire,
grant, provider identity, broad generic bytes route or hash/sha256 ABI is added.

The raw branch is emitted only with positive admitted vector/item budgets
and byte-value limits. A profile without that closure keeps the string-only
gate and has no references to unavailable byte-value trap labels. Profile
activation is still pending the complete paired runtime and language drafts.

## Native request and result path

For kind 8, the request fragment validates the vector handle, entire used
descriptor/item window, length bounds and every byte word (0–255). It asks
the existing sealed op-6 charge policy before allocating a pool span, checks
remaining space by subtraction, copies all bytes and advances real pool use.
Descriptor facts are explicitly saved across the decision call. No byte is
decoded/replaced or stored through a UTF8 string conversion.

Kind 9 requests retain the full string validation path. Both raw contracts
require NUL-F-S-2-NUL framing; neither can enter legacy token parsing. Kind 8
validates the framed path alone as canonical UTF8 without marking the whole
payload as a validated string. Full-span NUL/path/scope rules remain owned by
the existing path mechanism. The write/append tail remains arbitrary bytes,
including NUL, malformed UTF8 and former separator tokens.

Existing read/range/write/append bodies operate on raw bounded buffers.
Their intermediate internal pool pair is resolved as a span for raw results,
without consulting or setting a UTF8 cache flag. The FS2 answer path retains
its five-byte acknowledgement even for absent/empty data. The final fragment
copies the entire response into a fresh bytes/vector descriptor and item
span, respecting separate byte-value, per-vector, vector-table and item-pool
limits. Publication follows all checks and stores. No truncating success,
ASCII-only payload or byte-to-string round trip is substituted.

Kind 1 keeps full string validation, including the validation cache. The
existing UTF8 scan expressions are factored into an uncached span walker;
source AST comparison preserves every scan expression after removing only
the cache prefix/suffix. The raw span helper is internal glue and grants no
pointer authority; its caller must prove a stable bounded source window.

The extra pool copy and descriptor/item allocation consume actual resources.
FS2 acknowledgement bytes count toward the per-value response limit. Default
arena/pool sizes, actual allocation lifetimes and real workload limits remain
unqualified; this source does not claim arbitrary unbounded file reads.

## Complete component / decision preservation

- All existing native public names and parameter lists remain; four fragment
  exports are added to the full string/vector components.
- All prior vector and bytes primitive bodies remain unchanged.
- All sixteen filesystem forms remain; typed op 49 narrows only the meaning
  of the new raw contracts. Existing kind-1 forms retain their surface.
- C1 retains all 26 functions/public decision ABI/operation IDs; only the
  provider selector body changes. C3 retains all prior 53 function signatures
  and operations 0–48, adding one function and op 49.
- Native source reads 17 modules/35 schemas/591 imported calls/489 record
  uses/643 type positions. Source arity/type/record/lexical/Git comparison has
  no findings. This is not compilation or native execution evidence.

## Remaining order and qualification

1. Complete owning canonical GMIR validation and admit the byte kind/signature
   contract. Current owning main still stops at kind 7; the compatibility
   projection has an empty i64-value? body and is not complete GMIR.
2. Complete canonical KIR/value/type lowering and both ISA encoding for the
   byte contracts. The hosted compiler-port draft is port input, not a final
   dual-runtime dependency or source/type admission receipt.
3. Integrate the complete Amu raw FS2 codec and all file/hash/cache/resolver/
   materializer callers, preserving Result/Option/refusal semantics. The
   existing string codec does not become raw bytes merely through this patch.
4. Build/admit exact ISA-matched Amu-produced C1 and handler artifacts for
   the changed provider selector and new op 49. An old seal or embedded cache
   is not a qualifying replacement; no C-loader/header equality is required.
5. Obtain full native positive/refusal/authority/resource/path/no-leak and
   corpus evidence, exact component artifacts/Definition CIDs, reviewed
   owning mains and immutable locks, then the actual whole self-rebuild and
   two Amu/Kotoba-native CDCI gates with a native controller.

Pure byte-vector digest source is separately prepared in org-nist-sha2 #5.
It is not yet admitted, and this provider change does not qualify raw-file
hashing, artifact identity, all callers or the complete compiler.

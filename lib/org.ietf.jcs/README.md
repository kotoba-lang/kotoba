# kotoba-lang/org-ietf-jcs

**[RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html) JSON Canonicalization
Scheme, portable `.cljc`.** Turns a Clojure value into the one byte sequence
RFC 8785 defines for it, so two parties holding the same logical document produce
the same bytes — and therefore the same signature.

This is the transformation step of the `eddsa-jcs-2022` cryptosuite
([W3C vc-di-eddsa](https://www.w3.org/TR/vc-di-eddsa/)). Nothing here signs;
see `kotoba-lang/org-w3-vc-data-integrity` for that.

```clojure
(require '[jcs.core :as jcs])

(jcs/canonicalize {:b 1 :a 2})              ;=> "{\"a\":2,\"b\":1}"
(jcs/canonicalize {"n" 1e21})               ;=> "{\"n\":1e+21}"
(jcs/canonicalize-bytes {"k" "é"})          ;=> UTF-8 bytes, ready to hash
```

## The four rules

1. **Object members sort by property name, compared as UTF-16 code units**
   treated as unsigned integers (§3.2.3). Both hosts' native string compare is
   exactly this, so `sort-by` on the name is the rule rather than an
   approximation of it.
2. **No whitespace** (§3.2.1).
3. **Strings escape only `"` and `\`, plus C0 controls** — U+0008/09/0A/0C/0D as
   `\b \t \n \f \r`, every other control as *lowercase* `\uhhhh` (§3.2.2.2).
   Everything else is literal UTF-8, including `/`, U+007F, and all non-ASCII.
4. **Numbers serialize as ECMAScript `Number::toString`** (§3.2.2.3 → ECMA-262
   7.1.12.1). NaN and Infinity terminate with an error.

## Why the JVM branch does not use `Double/toString`

`Double/toString` is specified to produce *a* representation that round-trips,
not the *shortest* one. For `Double/MIN_VALUE` it yields `4.9E-324` where
ECMAScript — and RFC 8785's own Appendix B sample — require `5e-324`. Relying on
it would make the canonical form host-dependent, which defeats the point.

So `:clj` derives the digits directly: `BigDecimal.` of a double is its *exact*
binary value, and rounding that to `p` significant digits and checking the result
still parses back to the same double finds the true shortest `p`. `HALF_UP` on a
positive magnitude implements ECMA-262's tie rule ("choose the larger `s`").

`:cljs` delegates to `Number.prototype.toString`, because in JavaScript that
**is** the algorithm the RFC cites.

Both hosts are pinned to the same vectors (`test/jcs/core_test.cljk` and
`test/nbb_smoke.cljk`) and produce byte-identical output for all of them.

## Fail-closed inputs

A canonicalizer that silently coerces is worse than one that refuses, because
the caller is about to sign the result. Each of these throws `ex-info` carrying a
`:jcs/error` key:

| `:jcs/error` | Input |
|---|---|
| `:jcs/non-finite` | NaN, +∞, −∞ (§3.2.2.3 requires termination) |
| `:jcs/integer-out-of-range` | exact integer beyond ±(2^53−1) — App. D says carry it as a JSON string |
| `:jcs/unsupported-number` | `BigDecimal`, `Ratio` — no IEEE-754 double identity |
| `:jcs/invalid-key` | property name that is neither string nor keyword |
| `:jcs/duplicate-key` | distinct map keys collapsing to one JSON name (`:a` and `"a"`) |
| `:jcs/unsupported-type` | sets (no JSON form, no defined order) and anything else |

### One deliberate host asymmetry

`:clj` refuses exact integers beyond ±(2^53−1); `:cljs` does not, because there
is nothing to refuse — JavaScript has a single `number` type, so such a value is
*already* a double by the time it arrives and the precision has been lost
upstream. `Number.isInteger` is not the analogue of Clojure's `integer?`: it asks
"is this double integral", which `1e20` and `1e300` both are, and both are
exactly representable and must serialize.

So a `:clj` caller holding the exact integer 10^20 gets an error while a `:cljs`
caller holding `1e20` gets `100000000000000000000`. `:clj` is the stricter host,
which is the correct direction — App. D says such a value does not belong in a
JSON number at all, and a host able to detect that should say so rather than sign
a silently-rounded value.

## Reading in a static image (`kotoba/jcs/reader.kotoba`)

`jcs.reader` is the verifying direction, in the Amu selfhost seed subset. A
loaderless static image can check that the bytes it received are strict JSON,
read their fields, and confirm they are already canonical, with no host
parser (Linear JUN-349; kotoba-lang/amu#1469). It works on bytes
(`:vector-i64`).

| function | answer |
| --- | --- |
| `json-valid?` | the whole input is exactly one JSON value |
| `json-end` | where the value at `i` ends, or why not: `-1` syntax, `-2` deeper than 64, `-3` bad string, `-4` bad number, `-5` duplicate key, `-6` escaped key |
| `json-kind` | 1 object, 2 array, 3 string, 4 number, 5 true, 6 false, 7 null |
| `json-member`, `json-element`, `json-count` | navigation |
| `json-string-bytes`, `json-string` | a string decoded: escapes and `\u` surrogate pairs resolved, as bytes or as a `:string` |
| `json-int-ok?`, `json-int` | an integer with no fraction or exponent, within ±(2^53−1) |
| `json-canonical?` | the bytes are canonical under both RFC 8785 and `JSON.stringify` of sorted-key data (murakumo's signed form) |
| `json-canonical-bytes` | the value written in that form: members sorted, whitespace dropped, strings re-escaped, integers re-printed; no bytes outside the domain |

**Strict profile.** These are I-JSON's rules (RFC 7493) plus two more, so
that two readers cannot see two different documents in the same bytes:
- duplicate keys are refused;
- keys may not contain escapes, so `"a"` and `"\u0061"` cannot both appear;
- a `\u` surrogate must be a pair;
- UTF-8 must be well formed;
- nesting is at most 64 deep;
- a byte order mark is not whitespace;
- `NaN` and `Infinity` are refused.

**Canonical form.** It requires no whitespace, ASCII keys in strictly
increasing byte order (for ASCII, the same as §3.2.3's UTF-16 order), and
only the escapes §3.2.2.2 writes. It also accepts only documents whose
canonical form is the same in both schemes:
- **no all-digit keys.** JavaScript objects enumerate those first; JCS does
  not.
- **only integers within ±(2^53−1),** which both print as plain digits.
  Other numbers are refused rather than guessed.

The seed has no forward references, so validation is one loop with an
explicit stack.

**Native gate.** `kotoba/jcs/reader_gate.kotoba` is generated by
`docs/evidence/reader-corpus-20261023.py emit`. Each of its 105 cases is held
as hex, so a case can carry bytes a Kotoba string literal cannot. The gate
composes org-nist-sha2's `sha2.core` (for `hex`), the reader and the driver:

```sh
AMU=/Users/junkawasaki/github/kotoba-lang/amu
SHA=/Users/junkawasaki/github/kotoba-lang/org-nist-sha2
G=/Users/junkawasaki/github/workspaces/<agent>/<task>
mkdir -p "$G"
git -C "$AMU" show 457042ab741520980bceb5bf12970937d1bc8dba:seed/bootstrap/aarch64-linux-static-root.elf > "$G/root.elf"
chmod +x "$G/root.elf"   # SHA-256 1739f52f02fc90c28a1fa4a6c3a3f780caeff481893e3a1cd35badd8c227682e
{ echo '(ns jcs-reader-gate (:export [main]))'
  git -C "$SHA" show ea83e70a6a8efb8fb12dd5f0031fcda35a9ec77b:kotoba/sha2/core.kotoba | sed '1,/\]))$/d'
  sed '1,/\]))$/d' kotoba/jcs/reader.kotoba
  sed '1,/\]))$/d' kotoba/jcs/reader_gate.kotoba; } > "$G/gate.kotoba"
podman run --rm --pull never --platform linux/arm64 --network none \
  -e KEXE_CAP_RESOURCES_35=/gate -v "$G:/gate" -w /gate docker.io/library/python:3.12-alpine sh -c '
    ./root.elf compile /gate/gate.kotoba --target aarch64-linux --output /gate/gate.elf --format static &&
    chmod +x /gate/gate.elf && KEXE_STRUCTURED_REPORT=1 /gate/gate.elf > /gate/gate.out'
python3 -I docs/evidence/reader-corpus-20261023.py check "$G/gate.out"
```

Inside the image, the reported result is a bitmask:
- `1`: navigation and decoding on a nested document;
- `2`: the six reason codes.

For each case the image also prints validity, the end code, canonicality,
the canonical bytes, and the decoded string or integer. `check` compares every line with Python's
`json` module:
- an `object_pairs_hook` refuses duplicates;
- `parse_constant` refuses `NaN` and `Infinity`;
- the other strict and canonical rules are applied by name.

Measured on 2026-10-23 (arm64 Linux 6.15 under podman, amu `457042ab` root):

| source | result | disagreements with the oracle (of 105) |
| --- | --- | --- |
| reader | 3 | 0 (56 valid, 22 canonical, 46 with canonical bytes) |
| duplicate check removed | 1 | 2: `duplicate`, `duplicate-nested` |
| overlong 2-byte UTF-8 accepted (`0xC0`) | 3 | 1: `overlong-2` |
| key order not checked in the canonical form | 3 | 4: `canon-order`, `canon-prefix-wrong`, `canon-nested-order`, `recanon-deep` |
| members not sorted when writing canonical bytes | 3 | 5: the three ordering cases, `recanon-mixed`, `recanon-deep` |
| `/` escaped when writing canonical bytes | 3 | 3: `escapes`, `canon-slash`, `recanon-mixed` |

The canonical bytes are compared with Python's
`json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
The image is 311,808 bytes and runs in about 0.01 s with a 1,192 KiB maximum
resident set. The receipts are `docs/evidence/reader-gate-20261023.edn` (the
first version, 94 cases) and `docs/evidence/reader-canonical-bytes-20261023.edn`.

The gate does not cover floating-point numbers in the canonical form, x86_64
execution, or project-linker linkage. The `.cljk` canonicalizer below is
unchanged and is not called by the reader.

## Test

The `.cljk` canonicalizer's suite is retained corpus. CI no longer runs it,
because the JVM workflow was removed (see `AGENTS.md`). These commands are
historical:

```bash
kbb -M:test                              # JVM
kbb -M:lint
kbb --backend sci --classpath src test/nbb_smoke.cljk      # :cljs branch
```

## License

MIT. See `LICENSE`.

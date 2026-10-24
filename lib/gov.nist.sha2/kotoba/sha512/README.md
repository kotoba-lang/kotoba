# SHA-512 in Kotoba

`core.kotoba` is FIPS 180-4 SHA-512 written in the Kotoba guest subset — not
`.cljc` with a `java.security` branch and a `node:crypto` branch, and not a
`.cljc` file renamed to `.kotoba`. It compiles with `amu` and runs as
WebAssembly with no JVM and no `node:crypto`.

## Running it

```sh
amu compile core.kotoba --target wasm32 --jvm-free \
  --policy fuel.edn --output sha512.wasm
node run.mjs sha512.wasm
# main() = 0n
```

`main` returns the **number** of mismatched 64-bit words across two FIPS 180-4
vectors — `"abc"` and the empty string — so `0` is a pass and any other number
says how much is wrong. A boolean could not tell one wrong word from a hash
returning garbage. Measured: perturbing one expected word of the `"abc"`
digest makes it answer `1`.

## What the guest subset made this look like

Three constraints shaped the code, and each is visible in it:

- **Shift counts must be integer literals in [0,63].** A parameterised
  `(rotr x n)` is refused, so every rotation is written out. That is a good
  rule — a rotation whose distance is a runtime value is how constant-time
  code stops being constant-time — and it is also how FIPS 180-4 states them.
- **`vector-assoc!` takes a linear handle.** Any earlier use of the vector,
  including a `vector-at` read, disqualifies it, so read-modify-write is not
  expressible with the bang form. The persistent `vector-assoc` is used
  throughout.
- **At most five parameters.** A `loop` desugars to a helper whose parameters
  are its bindings, so the eight working variables live in a vector and the
  schedule and compression are self-recursive over `(vector, index)`.

Constants are the spec's unsigned values written as their signed i64 bit
patterns, because a literal above 2^63−1 is not an i64. Addition wraps mod
2^64 on this backend (measured: `(+ 9223372036854775807 1)` evaluates to
`-9223372036854775808`), which is what SHA-512's mod-2^64 addition needs, and
`u64-shift-right` is used wherever the spec says SHR or ROTR — `i64-shift-right`
appears nowhere in the file.

## What this is not

- **One block.** Messages up to 111 bytes, padded into the single 128-byte
  block the self-check supplies. Multi-block streaming is not implemented.
- **Not native.** `amu compile --target aarch64-macos` refuses it: *"typed
  values currently require the kotoba-script web target, typed Wasm target, or
  qualified native string/scalar-record/option-i64/result-i64 features"*. The
  native backend admits one-word values, and this uses `:vector-i64`. That is
  a named backend gap, not a language one.
- **Not Ed25519.** SHA-512 is the hash Ed25519 needs. The curve arithmetic —
  field operations mod 2^255−19 built from i64 limbs, point arithmetic, scalar
  multiplication — is not here.
- **Not constant-time-audited.** The rotations are literal, which is the
  precondition, but nothing here has been measured for timing behaviour.

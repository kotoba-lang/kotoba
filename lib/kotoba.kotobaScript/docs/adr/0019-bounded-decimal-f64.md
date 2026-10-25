# ADR 0019: Bounded decimal to binary64 parsing

Status: implemented in Kotoba Script; compiler qualification pending

`decimal-f64-parse` has type `string -> [:option :f64]`. It accepts at most 64
ASCII bytes matching a signed decimal significand with an optional decimal
point and an optional signed exponent containing one to three digits. Parsing
uses IEEE-754 binary64 round-to-nearest, ties-to-even. Finite results, including
underflow to signed zero and subnormal values, are `some`; malformed syntax and
non-finite overflow are `none`.

The operation rejects whitespace, NaN and infinity spellings, hexadecimal
forms, digit separators, locale syntax, and longer or wider exponent forms. It
does not throw for data-invalid input, consult locale state, perform I/O, or
grant authority. The enclosing string ABI still rejects invalid UTF-16.

Qualification requires identical reference, restricted JavaScript, and typed
Wasm values and bits across normal, signed-zero, subnormal, boundary, overflow,
and halfway-adjacent corpora, followed by real URDF numeric attribute evidence.

Kotoba Script evidence is `kbb -M:test`: 40 tests and 136 assertions pass.

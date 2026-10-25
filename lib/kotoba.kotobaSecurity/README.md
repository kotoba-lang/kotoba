# kotoba-security

Pure Kotoba byte helpers for security code. One module,
[`src/kotoba/security.kotoba`](src/kotoba/security.kotoba) (`kotoba.security`),
with no host imports and no dependencies.

## Exports

| function | returns |
|---|---|
| `const-eq a b` | `1` if the two i64 words are equal, else `0`. The whole 64-bit XOR is compared; values differing only in the upper 32 bits are unequal. |
| `xor-byte a b` | `(a XOR b) & 0xFF` |
| `hex-nibble v` | ASCII code of the uppercase hex digit for `v` in 0–15 (`10` → `65`, `A`) |
| `main` | the self-check: the number of failed checks, so `0` means pass |
| `test-self-check`, `test-const-eq-upper-word` | `kotoba -M test` exports: `1` means pass |

## Self-check

With amu's `kotoba` driver ([`kotoba-lang/amu`](https://github.com/kotoba-lang/amu) `bin/kotoba`):

```sh
kotoba -M test src/kotoba/security.kotoba
# kotoba test: 6/6 passed tests=[test-self-check test-const-eq-upper-word] targets=[:jvm-kir :js :wasm]
```

## Not here

Hashing and signing live in their own repositories:

- SHA-2: [`kotoba-lang/org-nist-sha2`](https://github.com/kotoba-lang/org-nist-sha2)
- Ed25519: [`kotoba-lang/org-ietf-ed25519`](https://github.com/kotoba-lang/org-ietf-ed25519)
- CACAO: [`kotoba-lang/org-chainagnostic-cacao`](https://github.com/kotoba-lang/org-chainagnostic-cacao)

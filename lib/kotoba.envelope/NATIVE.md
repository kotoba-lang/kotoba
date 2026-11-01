# Native envelope v1 chunk boundary

Tracked by [JUN-23](https://linear.app/kotobalabs/issue/JUN-23). The library's
current source owner is `kotoba-lang/kotoba/lib/kotoba.envelope`; the imported
individual repository is provenance, not the current implementation target.

`kotoba/envelope/chunk.kotoba` handles the existing AES-256-GCM chunk format.
It reuses `lib/gov.nist.aes/kotoba/aes` without implementing a cipher or KDF.
Its ciphertext matches the fixed vector already asserted by the browser and
JCA tests. The imported CLJK/JVM/NBB runners are not a build, runtime, gate or
fallback for this native module. The native gate invokes Amu directly.

The context vector is `[version, this chunk's epoch, chunk index, total chunks]`.
The caller resolves the stored per-chunk epoch before calling either operation.
`seal(key, object-id, context, plaintext)` returns ciphertext plus a 16-byte tag;
an empty vector means refusal. `open(key, object-id, context, ciphertext)` returns
authenticated plaintext, including an empty vector for an authenticated empty
file; `[-1]` means refusal. Inputs and outputs are unsigned-octet `:vector-i64`.
Only version 1, 32-byte keys, valid chunk positions, nonempty object IDs and
chunks up to 4 MiB are admitted. Epochs outside unsigned 32 bits are refused
rather than wrapping a nonce. The nonce and UTF-8 AAD match `envelope.model`.

The caller must generate a fresh CSPRNG content key for each object, wrap it
only to the independently verified owner's encryption key, never reuse an
epoch/index under that key for different plaintext, and keep sensitive metadata
inside an encrypted manifest. This module does not enforce that assembly or
retain nonce history. It neither receives a passkey nor grants network access.

## Verification

Fetch the compiler recorded in the repository's native input manifest:

```sh
scripts/fetch-native-amu.sh /absolute/github/workspaces/codex/jun23-test/amu
```

Then run `scripts/check-chunk-native.py` from this library with explicit
`--compiler`, `--compiler-sha256`, `--packager`, `--packager-sha256` and a fresh
`--output` directory on macOS arm64. On Linux x86_64 supply `--runner` for the
native KX64 runner instead of the Mac packager. No implicit compiler selection
or host-language fallback is provided. The shared native workflow runs the
macOS gate using its pinned Amu input manifest.

Four executed groups cover nonce endian/overflow, UTF-8 AAD, the existing
interoperability vector, empty-file authentication, wrong keys and context,
modified ciphertext/tags, malformed context and non-byte inputs. Four mutants
must compile and execute to the exact failing bitmasks: wrong nonce endian,
unbound object, unbound chunk count and bypassed AEAD authentication. A compiler
error or process crash is not counted as detecting a mutant. The report records
the actual source locks, compiler and packager digests, and executed verdicts.

## Qualification still open

This is a bounded native compatibility slice. It does not qualify key generation,
owner-key binding, hybrid key wrapping, Passkey PRF, locked-device custody,
recovery, browser consent, durable storage, Kura repair or independent failure
domains. The existing native AES implementation uses a data-dependent S-box
and is **not constant time**. Its production suitability for a client holding
private keys remains open; this gate must not enable customer-data mode or
label the distributed storage ready. The legacy provider's qualifications do
not transfer automatically to this native backend.

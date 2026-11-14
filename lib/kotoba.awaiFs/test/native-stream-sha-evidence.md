# Native streaming SHA-256 reference, 2026-11-14

`multiformats.sha256` now exposes a bounded mutable stream using the existing SHA-256 block compression and 146 `i64` slots per stream. It checks all input bytes before modifying the stream, limits total input length to 1,152,921,504,606,846,975 bytes, and finalization does not mutate it. State is caller-owned: it is not concurrency-safe or an authenticated serialized state; do not alias it as input.

On Darwin arm64 a pinned Amu compiler (`ce982703375bedc0039b61b1a821407d228ea98a`, SHA-256 `369fc624cf5236b3f4a9dba2021bb057223bd1179736c882123506dee4fda082`) compiled `native_stream_sha.kotoba` against the modified SHA source. The Native binary exited 0 for the empty and `abc` known SHA-256 values, lengths 55/56/64/65, invalid byte refusal without state mutation, the known million-`a` digest in one update and in 1,000 updates, and 1,000 updates whose input buffers live in separate `arena-scope`s. Source lock SHA-256 `11c4d91c2e26bde7f89f98a3f1e3289f490dc5c6a672f1fb9e610e40a3795adc`; signed local executable SHA-256 `8a9e755369d9851d2fdc6ad327cc8ec7952795a3fff2d0cb1b71adb5686b0f30`.

An independently compiled negative control with a changed SHA initial constant exited 1. It used the preceding implementation and test fixture without the additional arena checks. The runs invoked the pinned Native compiler, extractor and packager directly with an explicit KSL1 source lock; no Python runtime, host hash implementation, or fallback supplied the verdict. The retained local build directory has the locks, generated binaries and mutations. No Linux or exact-head CI result is implied. This unit establishes the hash primitive on the listed fixtures, not whole-file Forest restoration, GiB physical I/O, OS cache loss or device durability.

## Native-only shell gate subset

`native_stream_sha_gate.sh` stages the source under KSL1 locks, checks the compiler and packager against `native-inputs.json`, validates their signatures, and runs the Native fixture and a separately compiled changed-constant control. On 2026-11-14 Darwin arm64, it exited 0 with positive exit 0 and negative exit 1; a symlinked compiler was refused before compilation. The positive and negative lock SHA-256s were `11c4d91c2e26bde7f89f98a3f1e3289f490dc5c6a672f1fb9e610e40a3795adc` and `0d26a9c4cbe8ec353fda411e4d23743dc2acc343c85f98987e442efce05cc268`. Invocation from the repository root, with an independently staged and pinned Amu checkout and a new private destination:

```sh
lib/kotoba.awaiFs/test/native_stream_sha_gate.sh <amu-checkout> <new-output-dir>
```

The script is a macOS arm64 subset only. It is not yet wired into CI and does not replace the prior workflow's larger frozen corpus, Native Forest tests or Linux targets. The existing workflow's Python gate conflict remains open. GitHub CI, Native production integration and OS-cache-loss results remain unverified.

# Source-locked ARM64 runnable-layout producer candidate

`test/fune/build-runnable-arm64.sh` builds the diagnostic runnable-layout
producer from its 14 Kotoba source files. It writes a KSL1 lock with the source
hashes, invokes the supplied native Amu compiler to compile the locked project
to AArch64 KSEED, and packs that payload with the supplied runner source into a
Linux ARM64 static ELF. The core compiler calls its KSEED target
`aarch64-macos`; the final packed image is Linux ARM64. The script records the
compiler, runner, lock, KSEED and ELF hashes in `sha256sums.txt`.

On Linux ARM64, provide an Amu selfhost compiler, the matching
`seed/x86_64-kx64-runner.kotoba` from its Amu source tree, and a new output
directory. The compiler must be granted access to the actual Kotoba source
roots, runner and output directory under its existing filesystem capability
rules. The script does not grant those capabilities, verify the caller's
compiler identity, or authenticate the resulting artifact.

```sh
lib/kotoba.fune/test/fune/build-runnable-arm64.sh \
  /path/to/amu-arm64-linux /path/to/x86_64-kx64-runner.kotoba /path/to/new-output
```

On 2026-11-03, the pinned ARM64 bootstrap root with SHA-256
`76fa9b5e654822ba41cd3f621cb6c110e1893c3fa61a97d5ff068feb3fb3214f`
built the current candidate twice on native ARM64 Linux. Both KSEED outputs
were `2535f5a10cf022842278741904a6512ef370b36541dee9230bd1594f565ddf04`;
both ELFs were `175f19a6186b4773de88e0be950c062e3e884f800201857f8ab7b3033fb2cd72`.
These identities depend on the actual compiler, runner and sources; the
recorded values are not release pins. A wrong lock digest, changed source and
missing source-lock entry were refused without output artifacts. A valid local
OCI fixture and five supervisor refusal fixtures were exercised separately.

The producer is a test candidate, not a container runtime or general OCI
implementation. It can emit partial worker frames before later rejection;
the supervisor must discard the worker and its effects on failure. This ELF
is not the producer currently pinned by the fixed-fixture driver. Integrating
it requires a new driver identity and fresh end-to-end controls; registry
access, arbitrary workloads and general isolation remain unqualified.

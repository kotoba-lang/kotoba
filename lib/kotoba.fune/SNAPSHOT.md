# OCI layer snapshot digest candidate

`fune.snapshot/verify-layer-and-hold` reads a layer descriptor only after the
manifest bytes match the caller's expected digest and pass the bounded manifest
profile. It opens the layer using the Linux FS2 V operation, hashes W reads in
1 MiB windows, and compares SHA-256 to the descriptor. On success the snapshot
remains open in the same process; the caller must consume that same snapshot,
then call `close-snapshot`. On digest mismatch the function closes it. It does
not verify the tar structure, build a rootfs or grant permission to run it.
It must not be used as a detached admission token or as proof that reopening
the original path is safe.

The native snapshot provider in [Amu PR #1785](https://github.com/kotoba-lang/amu/pull/1785)
is a draft dependency. Old runtimes refuse V rather than silently falling back.
The source path must be granted through `:fs/app-data`. Provider refusals can
terminate the process. The maximum layer is 256 MiB in a sealed memfd; SHA
working state stays outside a temporary arena and individual read replies are
released after each update. The persistent caller-owned vectors are mutable:
their contents, the byte count and the update order are trusted inputs to the
streaming SHA API. Finalization consumes the state.

## Local native observations, 2026-11-02

Using an ARM64 compiler rebuilt from Amu PR #1785, the test-only
`test/fune/snapshot_gate.kotoba` passed these conditions:

* SHA-256 of `abc` and every length 0–130, updated in chunks of 1, 13 and 64,
  matched the existing non-streaming SHA-256 result.
* A valid fixture was checked, then its source file was rewritten; reads from
  the held snapshot retained the original bytes. A same-size corrupted fixture
  was rejected and the snapshot was closed so another can be opened.
* An independently exported 8,939,008-byte Alpine ARM64 layer matched its OCI
  descriptor across multiple windows. This is only digest verification; that
  image still contains a symlink outside the current tar inspection profile.
* A separately compiled mutant with digest comparison disabled returned the
  test failure code 4 on the corrupt fixture. The old pinned runtime refused
  FS2 V with stage 8 and exit 126.

The fixture runner intentionally rewrites its input in the positive case;
use a disposable copy. These are local ARM64 checks, not source-locked project
linkage, native x86 qualification, CI, a release, or Docker compatibility.
For the test-only runner set `KEXE_COMMAND=1` and leave
`KEXE_STRUCTURED_REPORT` unset so nonzero guest results become process errors.
The existing read-only layout checker still uses whole-file FS2 reads and does
not call this snapshot function. Layer application, safe transactional rootfs,
compression, whiteouts, links and actual container lifecycle remain open.

To repeat the native fixture, prepare the layer fixtures as described in the
README and make a disposable copy of `good.tar`. With `G` set to a task-owned
workspace, place the candidate Amu compiler from PR #1785 at
`$G/snapshot-compiler.elf`. The local run used compiler SHA-256
`0da6af45521d7ffc4cfcebee2ea56cb5655e3bc15763069a9d21a9d2f8adafd0`.
The following composes the namespace bodies for the measured seed compiler;
this is not source-locked project linking:

```sh
{
  printf '(ns fune-snapshot-test (:export [main]))\n'
  sed '1,/\]))$/d' lib/gov.nist.sha2/kotoba/sha2/core.kotoba
  sed '1,/\]))$/d' lib/org.ietf.jcs/kotoba/jcs/reader.kotoba
  sed '1,/\]))$/d;s@json/@@g;s@sha/@@g' lib/kotoba.fune/kotoba/fune/image_manifest.kotoba
  sed '1,/\]))$/d;s@manifest/@@g;s@sha/@@g' lib/kotoba.fune/kotoba/fune/snapshot.kotoba
  sed '1d;s@snapshot/@@g;s@sha/@@g' lib/kotoba.fune/test/fune/snapshot_gate.kotoba
} > "$G/snapshot-candidate.kotoba"
podman run --rm --pull never --platform linux/arm64 --network none \
  -e KEXE_CAP_RESOURCES_35=/gate -v "$G:/gate" -w /gate docker.io/library/alpine:3 \
  sh -c './snapshot-compiler.elf compile /gate/snapshot-candidate.kotoba --target aarch64-linux --output /gate/snapshot-candidate.elf --format static && chmod +x /gate/snapshot-candidate.elf'
podman run --rm --pull never --platform linux/arm64 --network none \
  -e KEXE_CAP_RESOURCES_35=/gate -e KEXE_COMMAND=1 -e KEXE_FUEL=100000000000 \
  -v "$G:/gate" -w /gate docker.io/library/alpine:3 /gate/snapshot-candidate.elf \
  good /gate/disposable-good.tar /gate/fixtures/good.manifest \
  sha256:65d85cbf52167eeb2bacc60972d64614b2f1a1fbbe7b4af5ac833c227b67d679
```

For `bad`, change one byte of a separate same-size fixture and run the same
command with mode `bad`. For `invalid-manifest`, pass an all-zero expected
digest. Both must exit zero because the fixture observes the intended refusal.
For the digest control replace the snapshot comparison `(if (= (str
"sha256:" actual) digest) "ok"` with `(if true "ok"` in a temporary composed
source, rebuild, and run `bad`; it must exit 4. Do not use the mutant for any
other purpose.

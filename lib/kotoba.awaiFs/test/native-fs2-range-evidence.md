# Native macOS FS2 range refusal (2026-11-14)

The pinned macOS arm64 FS2 provider was exercised with three separate native processes. The source pin is Amu `ce982703375bedc0039b61b1a821407d228ea98a`; the gate verifies the compiler and provider artifact digests and signatures. The one-byte file contained `A`.

| Direct FS2 E request | Observed process status |
| --- | --- |
| Existing file, offset 0, length 1 | 0 |
| Missing file, offset 0, length 1 | 133 (SIGTRAP) |
| Existing one-byte file, offset 0, length 2 | 133 (SIGTRAP) |

Run `lib/kotoba.awaiFs/test/native_fs2_range_probe.sh .agent-output/pinned-amu .agent-output/fs2-short-final` with the pinned artifacts present. The two trap diagnostics are expected negative controls. This is a local macOS result, not CI or another platform's result.

The [Amu FS2 evidence](https://github.com/kotoba-lang/amu/blob/ce982703375bedc0039b61b1a821407d228ea98a/docs/evidence/mac-fs2-ef-20261026/README.md) describes invalid E requests as trapping. The Forest reader performs a separate F metadata check before E; this experiment does not reproduce a concurrent truncate between those operations. If the file shrinks after that check, the direct E refusal can terminate the process instead of returning a recoverable reader error. A versioned provider contract or another explicit safe execution boundary needs independent design and validation; this result does not change the existing E contract.

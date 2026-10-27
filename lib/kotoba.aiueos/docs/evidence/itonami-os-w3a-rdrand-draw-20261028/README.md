# Itonami OS W3a: the guest draws hardware entropy (2026-10-28)

This supersedes the "no entropy is drawn" limit of `itonami-os-w3a-entropy-probe-20261028`.
The desktop checks CPUID (word 90) and, only when RDRAND is reported, executes the new
`kernel-rdrand` intrinsic twice (kotoba-lang/amu#1637, merged `bfe0b3acc`) and stores the low
32 bits of each draw in browser-context words 91 and 92. The intrinsic retries ten times and
returns 0 on failure, so 0 means "no entropy" and is never used as a value.

Evidence: `native-consent-qemu.json` (QEMU TCG, Apple Silicon, `--profile consent`), built with
**no explicit compiler**: the builder now takes the Mac root pinned by the Amu checkout
(`seed/bootstrap/aarch64-macos/root.json`, signed compiler `9d023d99...`, which knows kernel-v3
and the new intrinsics). Event `entropy-probe`: flags 7, `drawn` true, `distinctNonZeroDraws` true;
the gate asserts both draws are non-zero and different. Manual control on the same image:
`-cpu qemu64` (no RDRAND) gives flags 4 and draws 0, 0 (fail closed, no #UD, no crash);
`-cpu max` gives flags 7 and two different words. Desktop GPT+ISO, local-draft (12 events) and
idle (4 events) pass from the same repository root.

The builder's "repository bootstrap only knows kernel-v1" guard was stale after amu#1624; it now
applies only to roots that do not pin a kernel-v2 reference compiler.

Limits: QEMU draws RDRAND from the host, so this shows the instruction path and the fail-closed
check, not the quality of a physical CPU's source. No stuck-source test (QEMU cannot return a constant
here), no health test beyond non-zero and non-repeat, RDSEED not executed, and the 32-bit words are
diagnostic: no key is generated, stored or used. W3 stays open (SHA-512/Ed25519, persistence, consent-bound
signing). Source change and built candidate with QEMU results; not deployed.

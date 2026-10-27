# Itonami OS W3a: the guest reports its CPU entropy instructions (2026-10-28)

ADR-0277 puts the device key under local entropy. This slice answers only
"does the CPU the desktop runs on report a hardware entropy instruction?".
`desktop.kotoba` reads CPUID and stores the answer in browser-context word 90:
bit 0 = RDRAND (CPUID.1:ECX bit 30), bit 1 = RDSEED (CPUID.7:EBX bit 18),
bit 2 = CPUID leaf 7 exists.

Evidence: `native-consent-qemu.json` (QEMU TCG, Apple Silicon, `--profile
consent`, signed kernel-v3 compiler 4350f3ba), event `entropy-probe`: flags 7
under `-cpu max` (the gate asserts 7). Negative control, run by hand on the
same image: `-cpu qemu64` gives word 90 = 4 (leaf 7 present, neither RDRAND
nor RDSEED), so the probe distinguishes the two. Desktop GPT+ISO, local-draft
(12 events) and idle (4 events) also pass.

What this is not: no entropy is drawn. The Amu compiler has no intrinsic that
executes RDRAND or RDSEED (it has `kernel-cpuid-*`, `kernel-rdtsc`,
`kernel-read-msr` only), so drawing bytes, the health test and any key
generation need an Amu change first. The negative control was not added to the
gate; it is a manual run recorded here. Source change and built candidate with
QEMU results; not deployed.

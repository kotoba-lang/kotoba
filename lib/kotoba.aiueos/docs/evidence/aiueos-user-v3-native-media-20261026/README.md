# Mac native user-v3 media and Itonami QEMU boot (2026-10-26)

The AIUEOS user-v3 kernel/EFI from the [current-main integration](../aiueos-user-v3-main-integration-20261026/README.md)
was packaged into an 8 MiB GPT/FAT16 image by the signed Mac Amu compiler
(`fd72151174e57fb3f035cb6dd0e0c9e82fddcafaa2b158c0a8de67e802f91cfa`)
and Kotoba packager (`2ee308409db572c08733a4b0a28fc1908c8b15c44b045cf78e671ff798439ad0`).
The [native media receipt](media.json) records reproduced, independently
verified image SHA-256
`1d06c333d90b34bc9da0dc44b54e4e678df766486b693ac41831e12a81b35f39`
and ten format/refusal cases. Python staged and independently read the image;
native Kotoba emitted and verified its bytes.

The [headless controller receipt](debug-run.json) and [guest receipt](debug-summary.json)
record PASS on that exact image. The [first](boot-1-command.json) and
[second](boot-2-command.json) QEMU boots used the GPT image as a snapshot IDE
drive, a separate marked 64 KiB Goal draft disk, private QMP standard I/O,
`-nic none`, and no VNC listener or password. Itonami saved Goal `awai a`,
cold-restored it visibly in the [screenshot](restored-goal.png), displayed the
[local model choice](approval.png), left user pages untouched on denial,
then reached a CPL3 result of 105 after the synthetic approval branch.
The one-byte-modified user slot was refused in a separate direct-EFI boot;
that negative case was **not** a boot from the unmodified GPT image.

The [corrupt GPT run](corrupt-gpt-run.json) exited nonzero before any guest
boot; its [error log](corrupt-gpt-stderr.log) names the header CRC check.
The boot media digest was unchanged after both positive QEMU runs. These are
diagnostic VM results, not release admission, physical hardware, trusted
human consent, canonical `:llm/generate`, a general Itonami agent loop, or
D2 workspace recovery.

# AIUEOS local-draft VM from the refreshed Mac Amu root

Draft Amu [#1586](https://github.com/kotoba-lang/amu/pull/1586) commit
`242745ff7e716d9106b8281614f598c24e8631fb` adds checked Mac runtime
callbacks for `bytes-concat` and `bytes-slice`, then pins a new signed compiler
and packager. The same Amu checkout passed its 47-module Mac F1=F2 gate and
the FS2 product fixture's raw-byte write/readback. This AIUEOS run used that
repository-local root through the ordinary Mac desktop entry without setting
external compiler or packager image overrides.

The [integrated receipt](integrated.json) records native font, 31-module
workspace kernel, EFI, and 8 MiB GPT/FAT16 media generation. The media SHA-256
is `c7d4088475ac68944e5c28d94c206a74abf4063d08252545bfbfe89ffbc7671b`,
matching the prior local-draft candidate. The [private-QMP VM receipt](qemu.json)
returned `PASS_NATIVE_LOCAL_DRAFT_COLD_RESTORE` for 11 commit, cold restart,
uncommitted edit loss, generation selection and malformed-medium refusals.
The [restored guest screenshot](restored-ab.png) visibly shows `Goal local:`
and `ab` after a fresh QEMU process read the output-owned draft disk.
The build and VM observation did not launch a Linux, JVM, Node or C compiler
process or require VNC authentication or manual guest keys.

To rerun from these source checkouts, set `OUTPUT` to a new directory under
`github/workspaces/` and use the ordinary entry:

```sh
AIUEOS_NATIVE_DESKTOP_OUT="$OUTPUT" \
AIUEOS_NATIVE_DESKTOP_PROFILE=local-draft \
AIUEOS_OWNER_REPO_ROOT=/Users/junkawasaki/github/kotoba-lang \
  os/aiueos/scripts/build-kotoba-native-desktop.sh "$AMU_CHECKOUT"
```

This is diagnostic VM evidence. A registered Itonami agent turn, D2 signed
workspace state, release image, hardware boot and full OS acceptance remain
open.

# AIUEOS default Mac entry with repository-local Amu root

The ordinary `build-kotoba-native-desktop.sh` entry now reads the candidate
Mac bootstrap descriptor from the Amu checkout when no explicit compiler
and packager variables are supplied. The descriptor is in draft Amu PR
[#1586](https://github.com/kotoba-lang/amu/pull/1586), head `dd43782ce`.
The AIUEOS builder requires the exact compiler and packager paths, sizes,
SHA-256 digests, signed arm64 Mach-O format and no declared dylib loads.
It also checks the 47 ordered Amu source modules and packager source
against that descriptor before creating an output directory, then checks
the source and inputs again after the QEMU observation.

On Apple Silicon, the default shell entry was run with all four legacy
compiler/packager environment variables unset. It built the native font,
31-module workspace kernel, EFI, and GPT/FAT16 media, then booted that
exact media under private-QMP QEMU. The media SHA-256 was
`c7d4088475ac68944e5c28d94c206a74abf4063d08252545bfbfe89ffbc7671b`.
The local-draft gate passed 11 commit, cold restore, uncommitted crash and
refusal observations. Its screenshots show committed `ab`, restored `ab`
and `abd` after an orphan was refused, with visible glyph pixel checks.
`integrated.json`, `qemu.json`, and `queue.json` bind the root descriptor,
source graph, tools, media and guest observations. A partial explicit
override (only the compiler path) failed with exit 1 and no output
directory; the old fully pinned override remains supported.

To repeat with a new output directory under `github/workspaces/`:

```sh
AIUEOS_NATIVE_DESKTOP_OUT="$OUTPUT" \
AIUEOS_NATIVE_DESKTOP_PROFILE=local-draft \
AIUEOS_OWNER_REPO_ROOT="$OWNER_REPO_ROOT" \
  os/aiueos/scripts/build-kotoba-native-desktop.sh "$AMU_CHECKOUT"
```

Here `AMU_CHECKOUT` is the Amu #1586 candidate checkout and
`OWNER_REPO_ROOT` contains the five pinned Kotoba source-owner repositories.
The wrapper resolves installed QEMU and OVMF and binds their digests in
the receipt. The build entry is still a diagnostic VM route. It does not
qualify initial bootstrap provenance, complete Mac runtime, registered
Itonami agent execution, D2 workspace, release, or physical hardware.

# Mac native selfhost build progress (2026-10-26)

This is a local Apple Silicon build and QEMU desktop candidate for JUN-417
and JUN-89. Linux static-ELF builder qualification, release signing and
physical hardware admission are separate. The font/kernel/EFI result is in
[the first receipt](../docs/evidence/aiueos-mac-native-build-20261026/receipt.json);
Mac media and desktop receipts follow below.

## Native product route measured

- Signed arm64 Mac Amu full compiler SHA-256:
  e56548a0717e819c411f56393fa8657c06d28e3028213f4de231eaca87fd3d63.
  Signed Kotoba Mac packager SHA-256:
  4a656761e34e47cdcb640d68a1f4e99425253cdc1d69bea41c8c6e4eded69be0.
  Both passed strict code-signature verification; otool listed no dylibs.
- The Mac native font builder assembled the same 41,640-byte Kotoba source
  unity as the Linux comparator (SHA-256
  eb7179906ab035f6668a210e0ad8777ff6d5678c2548d516e5612ef939e4dba9).
  Amu compiled it to a Mac container, extracted main, and the Kotoba packager
  emitted a signed Mach-O. The native program padded 7,422 licensed glyphs
  to 524,288 bytes, SHA-256
  2dec7f39b3e2daea96d595805adaa9ed45b96eca912c955b515067e30a435b5f.
- The Mac native kernel builder staged the current AIUEOS Kotoba tree and
  manifest-pinned owner files as virtual absolute paths beneath FD3. The
  native modules command discovered 31 modules. The KSL1 lock was 3,937
  bytes, SHA-256
  37495e49f1133c747f2f4da84b4606db7f671ffce65277aa33f93e2b7de0444a.
  The Mac compiler reproduced the desktop-entry kernel ELF at fuel
  9007199254740991: 3,350,808 bytes, SHA-256
  0234d8a727e4f7803f0e89b7b0a52dc0d63e5a0061cb658f67e9f6685850ae19.
  Native package-aiueos-boot reproduced the EFI with the Mac-generated font:
  3,903,488 bytes, SHA-256
  6d1c32811ff076e3d060469893702c69c64bceab14659107fe67b93f6135bf7f.
- The comparator build in this exact AIUEOS checkout used the same 31 source
  hashes, source unity/font bytes and kernel fuel on a Linux arm64 static Amu
  image. Direct SHA-256 and size comparisons show the Mac font, kernel ELF
  and EFI are byte-identical to those comparator outputs. This comparison
  did not execute Linux during the Mac build. A wrong Mac compiler pin was
  refused before creating an output directory.

Python staged and observed bytes; it did not compile or package them. Mac
code signing and Mach-O inspection used macOS OS tools. The actual font,
kernel and EFI were produced by Kotoba/Amu native programs.

## Mac media and QEMU desktop candidate

The Mac Kotoba packager now supplies scoped FS2 F metadata and E range reads.
The unmodified media-builder source compiled to a signed Mac program and
generated the 8 MiB disk with SHA-256
`dcbb5274789f345d20519aa61137166085fe511d5ad6ec7b42f02bca5ef6b60a`.
It is byte-identical to the exact-source Linux comparator. The native program
also verified and reproduced the disk; the independent GPT/FAT16 reader and
10 named refusals passed. [The media receipt](../docs/evidence/aiueos-mac-native-build-20261026/media.json)
pins the compiler, packager, four source parts, media program, EFI and output.
The [Mac media builder](../os/aiueos/scripts/build-native-media-macos.py)
rejects wrong image pins and runs without a Linux/JVM/Node compiler process.
Format emission and verification execute in the Kotoba program.

The exact Mac-produced disk booted under QEMU TCG. The
[desktop gate](../docs/evidence/aiueos-mac-native-build-20261026/desktop-qemu.json)
used private QMP stdio and passed 12 input, redraw and device observations:
Itonami opened, Goal `ab` appeared, F5 stayed disabled in the normal profile,
and keyboard/mouse events and the [guest screenshot](../docs/evidence/aiueos-mac-native-build-20261026/itonami-goal-ab.png)
matched. No VNC password, Screen Sharing or manual guest key was used.
The Amu [FS2 F/E gate](https://github.com/kotoba-lang/amu/pull/1580) checks
FD3 scope, size/count bounds, missing files and traversal separately.
This is a local diagnostic VM candidate, not a release or physical boot.

Pinned full-compiler F1–F5 fixed-point evidence predates this expanded
FS2 F/E runtime. Requalification on the expanded runtime, integration into
the AIUEOS release builder, signed release and physical qualification remain open.

## Integrated Mac default entry

The default `build-kotoba-native-desktop.sh` entry now selects an
Apple Silicon path with pinned Amu and Kotoba packager images. One invocation
built the font, locked 31-module kernel, EFI and media, then booted that exact
disk with the private QMP desktop gate. Its [integrated receipt and stage evidence](../docs/evidence/aiueos-mac-integrated-20261026/README.md)
show the same Mac compiler at all three native build stages, the
`dcbb5274…f6b60a` disk, 12 guest observations and no Linux/JVM/Node
compiler process in the run. A wrong compiler digest refused before creating
the output directory.

The desktop gate now waits for a complete guest frame and checks dark glyph
pixels at the native draw positions of `a` and `b`. The previous gate
could capture the guest text state before QEMU's screen scanout had drawn
those glyphs. The new captured image visibly shows `Goal (RAM):` and `ab`.
This closes a local Mac build-to-VM-input diagnostic path. It does not close
the agent loop, default release build, independent initial bootstrap or
physical hardware gates.

## Opt-in local-draft and unattended debugging

The same Mac entry accepts `AIUEOS_NATIVE_DESKTOP_PROFILE=local-draft`.
It builds the `workspace-entry.kotoba` kernel, EFI and media with the pinned
Mac Amu compiler and Kotoba packager, then runs the save/restart gate against
that exact image. The [source-bound Mac local-draft evidence](../docs/evidence/aiueos-mac-local-draft-20261026/README.md)
records 11 passing QEMU observations, including F5 commit, cold restore,
uncommitted-edit loss and malformed-media refusal. Its committed and restored
screenshots also pass native glyph pixel checks. The resulting media is
byte-identical to the exact-source Linux arm64 comparator. The Mac run uses
no Linux/JVM/Node compiler process.

Routine Itonami inspection now uses `debug-native-desktop-qmp.py --build-dir`
with `--expect-visible-goal`; it boots a fresh headless VM and checks memory,
completed frames and QEMU scanout without Screen Sharing, a VNC password or
manual guest keys. The local-draft test disk is an output-owned 64 KiB
fixture. D2 workspace restore, signed Cell state, a registered Itonami app,
release and physical qualification remain open.

## Repository-local Mac bootstrap candidate

Draft [Amu #1586](https://github.com/kotoba-lang/amu/pull/1586) pins a
signed Mac compiler and Kotoba packager under
`seed/bootstrap/aarch64-macos/`. With that Amu checkout, the ordinary
`build-kotoba-native-desktop.sh` entry can read `root.json` instead of
requiring four compiler/packager environment variables. It checks the
ordered 47-module source graph, packager source, image digests and Mac
signature before producing output. Partial explicit overrides refuse.

The [default-entry receipt and screenshots](../docs/evidence/aiueos-repository-mac-root-20261026/README.md)
show a Mac native local-draft build and 11-case private-QMP QEMU gate from
that repository-local root. The media digest matches the earlier pinned
Mac build. This removes scratch executable inputs from the repeatable Mac
diagnostic path. The historical initial bootstrap bridge, full native
runtime corpus, signed release and physical-machine acceptance remain open.

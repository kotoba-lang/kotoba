# One Mac native desktop build and visible Itonami gate (2026-10-26)

The ordinary `build-kotoba-native-desktop.sh` entry now selects a Mac
native path on Apple Silicon. One pinned Mac Amu compiler
(`e56548a0717e819c411f56393fa8657c06d28e3028213f4de231eaca87fd3d63`)
and one Kotoba packager
(`45febd669218fd74c032a0a86a8dd03504311e2d2bf55b02c206ca60822e751c`)
built the font, 31-module desktop kernel, EFI and GPT/FAT16 disk in order.
The exact disk booted under QEMU TCG in the same invocation. The shared
native build queue recorded a 17.71-second run with one slot and exit 0.

The [integrated receipt](integrated-desktop.json) binds the host tools,
source manifest, stage scripts, font, kernel, EFI and media. Stage receipts
are [font](font.json), [kernel](kernel.json), [media](media.json) and
[QEMU](qemu.json); [queue admission](admission.json) is separate.
The media is 8 MiB, SHA-256
`dcbb5274789f345d20519aa61137166085fe511d5ad6ec7b42f02bca5ef6b60a`,
matching the exact-source Linux arm64 comparator. The Mac invocation
launched no Linux, JVM, Node or C compiler process. Python staged and
observed the native builders. The historical initial Mac Amu bootstrap
bridge has separate provenance.

QEMU used a private QMP stdio pipe, no VNC listener or NIC, and placed its
temporary disk overlay inside the private task output. The 12 guest
observations include Itonami Goal `ab`. The revised gate waits for a
completed frame and checks the **actual QEMU screenshot pixels** at the
guest's `a` and `b` glyph draw positions: 23 and 25 dark pixels.
The [screenshot](itonami-goal-ab.png) visibly shows both characters. An
[independent scanout readback](scanout-readback.json) found zero matching
pixels in the earlier gate's premature screenshot, despite its already
updated guest text state. That explains why the previous framebuffer
evidence was too weak to claim visible Goal text.

To repeat, set `AMU_SOURCE` to the Amu source checkout;
`AIUEOS_AMU_SELFHOST_BIN` and
`AIUEOS_AMU_SELFHOST_SHA256` to a signed, pinned Mac compiler;
`AIUEOS_KOTOBA_PACKAGER_BIN` and
`AIUEOS_KOTOBA_PACKAGER_SHA256` to the signed packager;
`AIUEOS_OWNER_REPO_ROOT` to the parent of the five canonical owner
repositories when building from a worktree; and
`AIUEOS_NATIVE_DESKTOP_OUT` to a **new** directory under
`github/workspaces/`. QEMU and its OVMF image are discovered from
the installed QEMU path, or may be selected with `AIUEOS_QEMU_BIN` and
`AIUEOS_QEMU_FIRMWARE`. Then run:

```sh
python3 "$AMU_SOURCE/scripts/seed/native_build_queue.py" \
  --phase aiueos-mac-desktop --output "$AIUEOS_NATIVE_DESKTOP_OUT.admission.json" \
  -- sh os/aiueos/scripts/build-kotoba-native-desktop.sh "$AMU_SOURCE"
```

The compiler and packager pins are checked before creating output. A
[wrong-compiler-pin control](negative-pin.json) exited nonzero and left
its output absent. The
result is a local diagnostic VM candidate. It does not qualify the full
Itonami agent loop, durable D2 workspace, shared Browser/CSSOM, signed
release or physical hardware.

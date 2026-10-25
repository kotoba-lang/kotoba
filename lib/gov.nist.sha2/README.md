# kotoba-lang/org-nist-sha2

SHA-224 / SHA-256 and HMAC-SHA-256, with a separate SHA-384 / SHA-512
namespace and hash subpath dispatch.

## Current migration contract

The canonical target is `.kotoba` compiled and run through Amu selfhost /
Kotoba native. CLJK, CLJC, Clojure, JVM/Java, NBB, Node and KBB are historical
port inputs, not final runtime dependencies or required CI gates.

The former workflow ran JDK 17/21 tests/lint and Node/NBB tests. It has been
retired, and no native CI gate is registered.

`kotoba/sha2/core.kotoba` is the `.kotoba` reading of `sha2.core`. It has all
eight exports, written in the Amu selfhost seed subset. The native gate below
builds it into a loaderless aarch64-linux static image and runs the retained
corpus (2026-10-23). Still open:

- x86_64 execution;
- a native CI gate and controller;
- artifact admission;
- caller integration.

## Complete `sha2.core` surface

| Export | Inputs | Result |
| --- | --- | --- |
| `sha256` | unsigned byte vector | 32 unsigned bytes |
| `sha224` | unsigned byte vector | 28 unsigned bytes |
| `sha256-hex`, `sha224-hex` | unsigned byte vector | lowercase hexadecimal |
| `hmac-sha256` | key byte vector, message byte vector | 32 unsigned bytes |
| `hmac-sha256-hex` | key byte vector, message byte vector | lowercase hexadecimal |
| `hex` | unsigned byte vector | two lowercase hexadecimal digits per byte |
| `u32` | signed 32-bit word | historical unsigned-word conversion |

The port must preserve the full message, distinct SHA-224 initial state,
64 rounds, all padding boundaries, 64-bit bit length, and HMAC with empty,
short, 64-byte and longer keys. A single-block fixture is insufficient.
No host digest or UTF-8 conversion of arbitrary bytes is an implementation
of this API. Native resource budgets must be recorded when qualified.

## Native gate

The gate composes two bodies, `kotoba/sha2/core.kotoba` and the corpus driver
`kotoba/sha2/native_gate.kotoba`, into one source. The pinned Amu root
compiles it to a static image, and the image runs with no network. Podman must
already have `alpine:3`, because `--pull never` refuses a download. Choose a
new task-owned directory for `G`.

```sh
AMU=/Users/junkawasaki/github/kotoba-lang/amu
G=/Users/junkawasaki/github/workspaces/<agent>/<task>
mkdir -p "$G"
git -C "$AMU" show 457042ab741520980bceb5bf12970937d1bc8dba:seed/bootstrap/aarch64-linux-static-root.elf > "$G/root.elf"
chmod +x "$G/root.elf"
# Expected compiler SHA-256: 1739f52f02fc90c28a1fa4a6c3a3f780caeff481893e3a1cd35badd8c227682e
shasum -a 256 "$G/root.elf"
{ echo '(ns sha2-gate (:export [main]))'
  sed '/^(ns /,/))$/d' kotoba/sha2/core.kotoba
  sed '/^(ns /,/))$/d' kotoba/sha2/native_gate.kotoba; } > "$G/gate.kotoba"
sed 's/\[1116352408 1899447441/[1116352409 1899447441/' "$G/gate.kotoba" > "$G/ctl-constant.kotoba"
sed 's/(if (> (vector-count key) 64) (sha256 key) key)/key/' "$G/gate.kotoba" > "$G/ctl-hmac-truncate.kotoba"
podman run --rm --pull never --platform linux/arm64 --network none \
  -e KEXE_CAP_RESOURCES_35=/gate -v "$G:/gate" -w /gate docker.io/library/alpine:3 sh -c '
    for c in gate ctl-constant ctl-hmac-truncate; do
      ./root.elf compile /gate/$c.kotoba --target aarch64-linux --output /gate/$c.elf --format static || exit 1
      chmod +x /gate/$c.elf
      KEXE_STRUCTURED_REPORT=1 /gate/$c.elf > /gate/$c.out
    done'
```

`--output` must name a new file, so remove old `.elf` files before you run it
again. Read the **reported result** on the last line of each `.out`. It is a
bitmask of the portable suite (`test/sha2/sha2_test.cljk`), checked inside the
image:

| bit | check |
| --- | --- |
| 1 | the published SHA-256 vectors |
| 2 | the published SHA-224 vectors and digest size |
| 4 | RFC 4231 test case 2 and the fox HMAC vector |
| 8 | HMAC key handling: long keys hashed, not truncated; short keys zero-padded; the empty-key vectors; a 64-byte key |
| 16 | `hex`, the hex lengths and `u32` |
| 32 | lengths 0–199, the six boundary digests are distinct, and a one-character change shares fewer than 8 bytes |

The image also prints one line per oracle case, from
`test/sha2/sha2_oracle_test.cljk`:
- SHA-256 and SHA-224 of the 19 shapes, including the one-megabyte message;
- SHA-256 of the length 0–199 sweep, and of the padding sweep;
- HMAC-SHA-256 under the five keys over every shape below 10,000 bytes.

Python's `hashlib` and `hmac`, an independent implementation, recompute the
same inputs and compare each line:

```sh
python3 -I - "$G/gate.out" <<'PY'
import hashlib, hmac, sys
lines = open(sys.argv[1]).read().splitlines()
report = lines.pop()
assert lines[-1] == f"lines {len(lines) - 1}", lines[-1]
lengths = [54, 55, 56, 57, 63, 64, 65, 118, 119, 120, 121]
shapes = {"empty": b"", "one": b"\0", "abc": b"abc", "all-bytes": bytes(range(256)),
          "high-bytes": b"\xff" * 300, "text": b"the quick brown fox. " * 40,
          "pseudo-random": bytes(1103515245 * (i + 1) % 256 for i in range(5000)),
          "one-megabyte": b"a" * 1000000}
shapes.update({f"length-{n}": bytes([n]) * n for n in lengths})
keys = {"k": b"k", "Jefe": b"Jefe", "0b-x64": b"\x0b" * 64, "aa-x100": b"\xaa" * 100, "55-x200": b"\x55" * 200}
want = []
for name, data in shapes.items():
    want += [f"sha256 {name} {hashlib.sha256(data).hexdigest()}", f"sha224 {name} {hashlib.sha224(data).hexdigest()}"]
for n in range(200):
    want += [f"sha256 sweep-{n} {hashlib.sha256(bytes(31 * (n + i) % 256 for i in range(n))).hexdigest()}",
             f"sha256 pad-{n} {hashlib.sha256(bytes([7 * n % 256]) * n).hexdigest()}"]
for k, key in keys.items():
    for name, data in shapes.items():
        if len(data) < 10000:
            want.append(f"hmac {k} {name} {hmac.new(key, data, hashlib.sha256).hexdigest()}")
got = lines[:-1]
bad = [w for w, g in zip(want, got) if w != g]
print(report.split(" :fuel")[0], "|", len(want), "expected", len(got), "printed", len(bad), "mismatched")
PY
```

Run the same comparison on each control's `.out`.

Measured on 2026-10-23 (arm64 Linux 6.15 under podman on macOS arm64; receipt:
[`docs/evidence/sha2-core-native-gate-20261023.edn`](docs/evidence/sha2-core-native-gate-20261023.edn)):

| source | reported result | oracle lines mismatched |
| --- | --- | --- |
| `gate` | 63 | 0 of 528 |
| `ctl-constant` (one round constant off by one) | 48 | 528 of 528 |
| `ctl-hmac-truncate` (a long key is truncated, not hashed) | 55 | 36 of 528, exactly the 100- and 200-byte keys |

The controls have to produce exactly these lower values.

Resource budget, measured with busybox `time -v`:
- 3.40 s of wall-clock time and 12,976 KiB maximum resident set, within the
  image's own 64 MiB address-space limit;
- a 250,368-byte image.

No Node, NBB, JVM, hosted compiler, C compiler or C loader runs in this gate.
Python only computes the oracle. This is a source-unity gate. It does not show:
- linkage through the project linker;
- x86_64 execution;
- byte-preserving callers such as file hashing or `org-tukaani-xz`.

## Retained source and corpus

`src/sha2/core.cljk` is the historical implementation input. The existing
`test/sha2/sha2_test.cljk` contains published SHA-224/256 vectors and RFC 4231
HMAC cases. `test/sha2/sha2_oracle_test.cljk` retains length 0–199 sweeps,
multiple input shapes including all byte values and larger messages, and
historical MessageDigest / shasum comparisons. These files are preserved;
old hosted comparison results do not establish native execution parity.

The SHA-384/512 implementation and corpus remain under `src/sha2/sha512.cljk`
and `test/sha2/sha512*`. Their full migration, including the 128-byte HMAC
block, distinct SHA-384 initial state and 128-bit length field, is separate
from `sha2.core`. The existing `kotoba/sha512` fixture does not establish
whole-namespace completion.

Hash subpath dispatch (`src/hash/subpath_dispatch.cljk`,
`kotoba/hash/subpath_dispatch.kotoba`) has its own public surface and corpus.
It remains a separate dependency until its full native closure is admitted.

Historical hosted runners and dependency descriptors remain porting records;
they do not define an accepted fallback or a future gate.

## Downstream integration

The original consumer was SHA-256 block checking for `org-tukaani-xz`.
Compiler caches and file hashing also need byte-preserving callers. Source
migration here does not implement raw file capability kinds, their provider
and result lowering, caller conversion, or artifact publication.

## Specifications

- [NIST FIPS 180-4](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf)
- [NIST FIPS 198-1](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.198-1.pdf)
- [RFC 4231](https://www.rfc-editor.org/rfc/rfc4231)

These references define the algorithms; this repository does not claim a
validated implementation or completed native qualification.

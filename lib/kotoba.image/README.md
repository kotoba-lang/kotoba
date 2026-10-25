# kotoba-lang/image — `kotoba.image`

A portable raster with `java.awt.image.BufferedImage` getRGB / setRGB
semantics (TYPE_INT_RGB and TYPE_INT_ARGB only), plus PNG read / write with
`javax.imageio.ImageIO` semantics, over
[org-w3-png](https://github.com/kotoba-lang/org-w3-png) and
[org-ietf-deflate](https://github.com/kotoba-lang/org-ietf-deflate).
Source is `.cljk`: the JVM branch (`#?(:clj)`) and the kbb branch
(`#?(:cljs)`, ClojureScript on Node) run the same code — neither calls
`java.awt` or `javax.imageio`.

It exists so that `java.awt.image.BufferedImage` + `ImageIO` raster use can be
rewritten onto a `kotoba.*` namespace (clojure.\*/java.\* → kotoba.\*
migration, 2026-09-25).

## Boundary to neighbours

| repo | owns |
|---|---|
| `org-w3-png` | the PNG codec: bytes ↔ unfiltered samples (`png.core/parse`, `png.encode/encode`, `png.grammar/grammar`) |
| `org-ietf-deflate` | zlib / deflate under it |
| `org-iso-jpeg` | JPEG decode — **not wired here**: a JPEG refuses by name |
| **`kotoba.image`** | the raster model (packed ARGB ints), format dispatch (what ImageIO's reader SPIs would claim), and the colour model ImageIO applies when it turns PNG samples into `getRGB` |

**Not covered:** `java.awt` drawing — `Graphics2D`, fonts, `AlphaComposite`,
scaling, any `BufferedImage` type other than INT_RGB / INT_ARGB, `Raster` /
`ColorModel` access. A consumer that draws still needs something else.

## API (namespace `kotoba.image`)

| fn | semantics |
|---|---|
| `(create w h type)` | `new BufferedImage(w, h, TYPE_INT_RGB \| TYPE_INT_ARGB)`; `type` ∈ `#{:rgb :argb}`; pixels 0. `w`, `h` integers > 0 with `w*h` ≤ 2³¹−1, else `{:kotoba.image/error :invalid-dimensions}`; unknown type → `:invalid-type` |
| `(width img)` `(height img)` `(image-type img)` `(image? x)` | accessors; a non-raster → `:invalid-image` |
| `(get-rgb img x y)` | `getRGB(x, y)`: signed 32-bit int; `:rgb` reads alpha 0xFF. Outside → `:out-of-bounds` (JDK: `ArrayIndexOutOfBoundsException`) |
| `(set-rgb! img x y argb)` | `setRGB`: any integer, low 32 bits taken (`0xff0080ff` as a long, `-1`, `0x1ffffffff`); `:rgb` keeps the low 24 bits; returns nil. Bounds as above; a non-integer argb → `:invalid-argb` |
| `(read-image bytes)` | `ImageIO.read(ByteArrayInputStream)` for PNG — see below |
| `(write-png img)` | PNG bytes: `byte[]` on the JVM, **`Int8Array` under kbb** (the host byte type `kotoba.lang.io.file/read-all-bytes` and `kotoba.bytes/->host-bytes` use there). `:rgb` → colour type 2, `:argb` → colour type 6, 8-bit, filter 0, not interlaced |
| `(read-file f)` | `ImageIO.read(File)`: `f` a path string, or on the JVM a `java.io.File` / `java.nio.file.Path`. Not a readable regular file → `{:kotoba.image/error :cannot-read :path p}` (JDK: `IIOException "Can't read input file!"`); `nil` / another type → `:invalid-path` |
| `(write-png-file! img f)` | `ImageIO.write(img, "png", File)`: writes `write-png`'s bytes (create / truncate); returns `true`. Unwritable → `:cannot-write` |
| `(pixels img)` | extra: every `get-rgb`, row-major, as a fresh vector |

`read-image` accepts `byte[]`, `Int8Array`, `Uint8Array`, a Node `Buffer`, or
any sequence of byte values; `nil` → `:invalid-input` (JDK:
`IllegalArgumentException "input == null!"`).

### `read-image` / `read-file` outcomes

* **a raster** whose `get-rgb` equals `ImageIO.read(...).getRGB(x, y)` for
  every pixel. Type `:argb` when the PNG carries alpha — colour type 4 / 6,
  or a tRNS chunk ImageIO honours — else `:rgb`.
* **`nil`** when no ImageIO reader would claim the bytes (ImageIO returns
  `null`). The sniff reproduces each JDK reader SPI's `canDecodeInput`,
  including WBMP's (for a stream: width < 1024 and height < 768; for a File:
  the exact data length).
* **`{:kotoba.image/error :unsupported-format :format f}`**, f ∈ `:jpeg :gif
  :bmp :tiff :wbmp` — ImageIO WOULD decode these, so nil would lie.
* **`{:kotoba.image/error :unsupported-png :reason r}`** for a PNG this does
  not decode:
  * `:interlaced` — Adam7. ImageIO decodes it; png.core does not
    de-interlace. The one PNG kind that refuses where ImageIO succeeds.
  * `:malformed` — ImageIO throws on these too (measured, see below):
    truncated / undecodable data, bad IHDR, unknown filter / compression /
    interlace method, a tRNS in a colour-type 4/6 image, and for palette
    images every chunk ImageIO's full metadata pass cannot consume (second
    PLTE, tRNS before PLTE, fixed-size chunks of the wrong length, hIST
    before PLTE / odd length, unterminated tEXt / iCCP / sPLT keywords, sPLT
    depth ≠ 8/16, no IEND).
  * `:missing-plte`, `:invalid-bit-depth`, `:invalid-color-type`, `:too-large`.

### What ImageIO does to PNG samples (and so what this does)

Found by reading `PNGImageReader` / `ComponentColorModel` (OpenJDK 21) and
then measured, not assumed:

* **Gray 8 / 16-bit and gray+alpha are converted to sRGB.** ImageIO builds a
  `CS_GRAY` (linear gray) colour model, and `getRGB` runs the IEC 61966-2-1
  curve: gray 128 reads `0xFFBCBCBC`, not `0xFF808080`. The tables
  (`kotoba.image.gray`) are the JDK's own values, measured entry by entry.
* **Gray 1 / 2 / 4-bit without tRNS is not converted** (an `IndexColorModel`
  ramp `i*255/(2^b−1)`). With tRNS it becomes 8-bit gray+alpha: the sample is
  scaled `(s*255 + max/2)/max`, the SCALED value is compared with the tRNS
  value, and the gray then goes through the sRGB curve.
* **16-bit → 8-bit** is `(int)((float)c / 65535f * 255f + 0.5f)` in IEEE
  single precision (alpha too).
* **Palette:** PLTE rounded up to 2 / 4 / 16 / 256 entries with black, then
  padded to 2^bits with the last of those; tRNS entries beyond that length
  dropped, missing ones 255.
* **tRNS for gray / RGB** counts only before the first IDAT and only with the
  right length (ImageIO.read sets `ignoreMetadata`); the last valid one wins.
  For palette images it counts anywhere after the PLTE up to IEND.
* **gAMA, iCCP, sRGB, cHRM are not applied** by ImageIO.read (they are not
  even parsed for non-palette images), so they are ignored here — measured.

## Tests

```sh
kbb -M:test                                   # portable suite on kbb
kbb --backend sci scripts/jvm_test.cljk kotoba.image-test kotoba.image.jvm-oracle-test
```

* `kotoba.image-test` — **portable**, runs on kbb and on the JVM: create /
  get / set incl. `:rgb` alpha forcing, low-32-bit wrap (`0xff0080ff`, `-1`,
  `0x1ffffffff`, `2^32`), bounds at `w` / `h` / `-1` and `w-1` / `h-1`,
  refusals by literal keyword, write→read round trips for both types, files,
  not-an-image → nil, every other format → `:unsupported-format`, literal
  getRGB values measured from ImageIO for gray / sub-byte gray / palette+tRNS
  / RGB16 / gray+tRNS, PNG refusals.
* `kotoba.image.jvm-oracle-test` — **JVM oracle only** (body is
  `#?(:clj)`; kbb loads it and runs nothing): compares against the live JDK.
* `scripts/jvm_test.cljk` mirrors `.cljk` → `.cljc` and runs clojure.test on
  a JDK (exit 2 = zero tests ran). Local change vs. the shared runner: it
  also quotes `{:kotoba/export [..]}` ns attr-maps in pre-existing `.cljc`
  files on the classpath (a stray `edn.cljc` in `~/.gitlibs` hid the fix).

Measured 2026-09-25, OpenJDK 21.0.1 (Temurin), seed per deftest:

| oracle case | cases | pixels | mismatches |
|---|---|---|---|
| ImageIO-written PNGs of 10 BufferedImage types (INT_RGB, INT_ARGB, INT_ARGB_PRE, BYTE_GRAY, USHORT_GRAY, BYTE_INDEXED, BYTE_BINARY, 4BYTE_ABGR, 3BYTE_BGR, USHORT_565_RGB) | 120 | 51,664 | 0 |
| hand-built: every colour type × bit depth (15 kinds) × {plain, tRNS, raw tRNS} | 370 | 58,862 | 0 |
| palette rounding: bits 1/2/4/8 × PLTE 1…257 × tRNS lengths | 308 | 21,406 | 0 |
| exhaustive: every 16-bit sample in gray / gray+alpha / RGB / RGBA | 4 | 262,144 | 0 |
| gray LUTs vs BufferedImage, every entry (8-bit, 16-bit) | 65,792 | 65,792 | 0 |
| gAMA / iCCP / sRGB / cHRM present | 24 | 1,512 | 0 |
| tRNS / chunk placement cases | 9 | — | 0 |
| cases where ImageIO throws → we refuse `:malformed` | 11 | — | 0 |
| sniff agreement with `ImageIO.getImageReaders` (crafted + 2,000 random) | 2,029 | — | 0 |
| (b) `write-png` → `ImageIO.read` | 50 | 29,343 | 0 |
| (c) setRGB/getRGB vs set-rgb!/get-rgb, random writes (INT_RGB, INT_ARGB) | 30,723 writes | 10,241 | 0 (+640 bounds probes, 0 disagreements) |

JVM: 24 tests / 2,250 assertions, 0 failures. kbb: 12 tests / 82 assertions, 0 failures.
The oracle goes red when broken: rounding `+0.5f` → `+0.4f` and padding the
palette with a non-black entry gave 236 failures (8,415 mismatching pixels in
the hand-built set alone).

Speed (one run, not a constant): a 256×256 `:argb` image under kbb wrote in
2.3 s and read back in 0.34 s — the encoder's vector-based zlib dominates.

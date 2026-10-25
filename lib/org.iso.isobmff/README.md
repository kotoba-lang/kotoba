# kotoba-lang/org-iso-isobmff

The open CLJC implementation remains the semantic oracle for recursive box
trees, AVIF/HEIC metadata, demux, mux, and remux. The capability-free bounded
Kotoba profile in `src/isobmff/bounded_box.kotoba` validates top-level ISO-BMFF
box framing for inputs up to 16,384 bytes, including normal, EOF-sized, and
64-bit large-size headers. It rejects truncated and invalid-byte headers,
undersized or out-of-range boxes, unsupported sizes above the bounded input
domain, more than 32 top-level boxes, and missing `ftyp`/`moov`/`mdat` boxes.

The committed 12,171-byte H.264 MP4 fixture runs through generated Web and
sealed typed Wasm artifacts. The cross-repository Kotoba graph in
`src/isobmff/avc_sps.kotoba` follows the bounded first `trak` path
`moov/trak/mdia/minf/stbl/stsd/avc1/avcC`, extracts one SPS (at most 128
bytes), then calls `h264.sps/parse-ebsp-baseline` directly from the pinned
`org-iso-h264` dependency. The real fixture proves baseline profile 66 at
64x48 on both targets. It rejects malformed nested sizes, invalid bytes,
unsupported AVC configuration versions/counts, truncated or oversized SPS,
and inputs above 16,384 bytes without host capabilities. General multi-track
selection, sample tables, media decode, and mutation remain explicitly in
CLJC.

`src/isobmff/image_meta.kotoba` adds a bounded still-image metadata profile
over `ftyp + meta/iprp/ipco/ispe`. It returns the exact four-byte major brand
as an unsigned-u32 value held in Kotoba i64, plus the full positive-u32 width
and height domain. This avoids narrowing arbitrary brands to a hard-coded
AVIF/HEIC enum and avoids delegating dynamic string construction to JavaScript.
The parser rejects missing or malformed paths, non-byte payloads, nonzero
`ispe` version/flags, zero dimensions, nested range errors, and inputs above
16,384 bytes. The general recursive box listing and optional-field result
shape remain in the CLJC oracle.

Zero-dep portable `.cljc` ISO Base Media File Format reader/writer
(ISO/IEC 14496-12) — the box-tree container behind MP4/MOV video and
AVIF/HEIC still images. Named `org-iso-isobmff` (ISO/IEC-numbered spec,
consistent with `org-iso-jpeg`/`org-iso-pdf`/`org-iso-opentype`/`org-iso-h264`
in the same batch).

**This repo unifies two previously independent, duplicate box-tree
implementations**: `kasane.isobmff` (a flat walker used to read AVIF/HEIC
`ftyp`/`ispe` metadata, from `kotoba-lang/kasane`, ADR-2606280010) and
`utsushi.container`/`demux`/`mux`/`remux` (a nested-tree walker + full MP4
demux/mux/remux pipeline, from `kotoba-lang/utsushi`, ADR-2606272200). Both
were parsing the *same spec*; merging them into one `isobmff.box` walker
also fixed a real gap — the MP4-side walker didn't know `meta` is a
FullBox (4-byte version+flags before its children), which the AVIF-side
walker handled correctly. The merge carries that fix into the shared
engine, and both consumers (`isobmff.meta` for AVIF/HEIC, `isobmff.demux`/
`mux`/`remux` for MP4) now sit on one correct implementation.

## Namespaces

| ns | role | source |
|---|---|---|
| `isobmff.bytes` | big-endian read/write primitives | utsushi.bytes |
| `isobmff.box` | generic recursive box-tree walker (shared engine) | merged kasane.isobmff + utsushi.container |
| `isobmff.meta` | AVIF/HEIC brand + dimensions (ftyp/ispe) | kasane.isobmff |
| `isobmff.blob` | content-id placeholder for sample/packet references | utsushi.blob |
| `isobmff.demux` | MP4 → per-track samples via the stbl sample table | utsushi.demux |
| `isobmff.mux` | per-track samples → MP4 (re-encode-free) | utsushi.mux |
| `isobmff.remux` | trim / concat (re-encode-free edits) | utsushi.remux |

Pixel/frame decode (AV1/HEVC/H.264/...) is out of scope — this repo only
reads/writes the container structure; coded media stays an opaque blob for
the caller (or a capability-gated native codec, per `kotoba-lang/utsushi`'s
own design).

**Two exceptions, deliberately made:** `isobmff.mux/aac-stsd` and
`avc-stsd` BUILD an `mp4a` + `esds` / `avc1` + `avcC` sample entry rather
than passing one through. Opaque codec config is the right default for
re-encode-free work, but it leaves no way to author a track from scratch —
an MP4 has to declare its codec, and without those boxes
`kotoba-lang/org-iso-aac` and `org-iso-h264` could encode streams ffmpeg
decodes with still nowhere in an MP4 to say so (`com-junkawasaki/root`
ADR-2800002800). `aac-track`/`avc-track` turn those encoders' access units
into `mux`-shaped tracks.

Both are cross-validated against the boxes real ffmpeg wrote in this repo's
own `av_sample.mp4` — for `avcC`, given ffmpeg's own parameter sets this
writer produces ffmpeg's exact BYTES — and both resulting files are verified
end to end: `ffprobe` reads `aac_mono.mp4` as `aac (LC) (mp4a)` and
`avc_video.mp4` as `h264 (Baseline) (avc1), 128x96, 30 fps`, and in each case
ffmpeg's decode is byte-identical to decoding the same access units outside
the container, so the container contributes no error.

For video the fiddly part is not the boxes: **MP4 carries length-prefixed
NAL units, not Annex B start codes, and the parameter sets belong to `avcC`
rather than to the samples.** A muxer that copied Annex B into `mdat`
produces a file that parses, reports the right codec and resolution, and
decodes to nothing. `annexb->sample` does that conversion and is tested on
its own. Codec config for every OTHER format stays opaque.

## Usage

```clojure
(require '[isobmff.meta :as meta] '[isobmff.demux :as demux]
         '[isobmff.mux :as mux] '[isobmff.remux :as remux])

(meta/parse avif-bytes)                     ; => {:brand :width :height :boxes}
(def d (demux/demux mp4-bytes))             ; => {:timescale :tracks [...]}
(remux/remux (remux/trim d 0 5000))         ; re-encode-free trim → MP4 bytes

;; author an AAC audio track from scratch (aac.encode's output, no ADTS headers)
(def t (mux/aac-track {:access-units (:access-units enc)
                       :sample-rate 44100 :channel-count 1
                       :audio-specific-config (:audio-specific-config enc)}))
(mux/mux {:timescale 44100 :tracks [t]})    ; => a playable MP4

;; author an H.264 video track (Annex B NALs per access unit; SPS/PPS go in avcC)
(def v (mux/avc-track {:access-units [[idr-nal] [p-nal] ...]
                       :sps sps-nal :pps pps-nal
                       :width 1280 :height 720
                       :timescale 30000 :sample-duration 1000}))
(mux/mux {:timescale 30000 :tracks [v]})
```

## Test

```sh
kbb -M:test
```

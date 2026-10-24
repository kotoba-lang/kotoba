# kotoba-lang/org-iso-aac

Zero-dep portable `.cljc` AAC-LC (Low Complexity) **codec** — ADTS (Audio
Data Transport Stream) frame framing, real spectral-to-PCM sample decode,
and PCM-to-ADTS **encode** — ISO/IEC 13818-7 (MPEG-2 AAC) / ISO/IEC
14496-3 (MPEG-4 AAC). Named
`org-iso-aac` (ISO/IEC-numbered spec, consistent with `org-iso-h264`/
`org-iso-isobmff`/`org-iso-jpeg`/`org-iso-pdf`/`org-iso-opentype` in the
same batch). This is the kotoba-lang ecosystem's **first audio codec
sample-decode implementation** (previously only ADTS framing existed).

**New implementation, not an extraction** — `kotoba-lang/utsushi`'s
`utsushi.bitstream/parse-adts` was an unimplemented `(throw (ex-info
"TODO..."))` stub (discovered while decomposing `utsushi` into
per-format-spec repos; see `com-junkawasaki/root` ADR precedent
2607072500).

## Scope

- **Framing** (`aac.adts`): ADTS's self-contained 7-byte (9-byte with CRC)
  header (sample rate, channel config, frame length) + frame splitting.
- **Decode** (`aac.decode` + `aac.ics`/`aac.huffman`/`aac.dequant`/
  `aac.stereo`/`aac.imdct`): **mono (SCE) OR stereo (CPE, incl. mid/side
  stereo), all four `window_sequence` values** AAC-LC —
  `ics_info()`/`section_data()`/`scale_factor_data()`/`spectral_data()`
  noiseless coding (all 11 spectral Huffman codebooks + the scalefactor
  codebook, Annex 4.A), inverse quantization, mid/side (M/S) stereo
  reconstruction (`aac.stereo`, per-scalefactor-band `ms_used`, §4.6.8.1),
  and the §4.6.11 filterbank: IMDCT + sine/KBD windowing + 50% overlap-add,
  run independently per channel for CPE (see
  `aac.decode/decode-adts-frame-stereo`'s docstring for why overlap-add
  history is never shared across channels).
- **Block switching** (§4.6.11.3, `aac.imdct`/`aac.ics`/`aac.tables`):
  `ONLY_LONG_SEQUENCE`, `LONG_START_SEQUENCE`, `EIGHT_SHORT_SEQUENCE` and
  `LONG_STOP_SEQUENCE` — the eight 128-line IMDCTs with their own short
  sine/KBD windows (alpha 6.0, not the long window's 4.0) overlap-added at a
  128-sample hop, plus LONG_START/LONG_STOP's flat-and-short-half transition
  shapes. On the side-info side that means the 4-bit `max_sfb` +
  `scale_factor_grouping` form of `ics_info()`, window groups
  (`aac.ics/window-group-lengths`), per-group `section_data()` with its
  narrower 3-bit `sect_len_incr`, per-(group, band) scalefactors and
  `ms_used`, the short scalefactor-band table, and de-interleaving the
  grouped coefficient order back into transform order. **This is what makes
  real encoder output decodable**: encoders switch to short blocks at every
  transient, so before this a file with any attack in it was undecodable
  from its first frame.
- Explicitly **out of scope** for decode (all throw rather than
  mis-decode): intensity stereo (a per-band pseudo-codebook, separate from
  mid/side and NOT implemented — see `test/aac/decode_test.cljk`'s stereo
  fixture comment for why this one bites in practice even with PNS
  disabled), LFE/coupling channels, SBR/PS (this is plain AAC-LC, not
  HE-AAC/v2), LTP, predictor/pulse/TNS/gain-control tools, and PNS
  (perceptual noise substitution — see `aac.ics`'s namespace docstring for
  why this one matters a lot in practice, and why it could not be
  golden-vector-tested even if implemented). Only 44100/48000 Hz sample
  rates.
- **Encode** (`aac.encode` + `aac.mdct`/`aac.quant` + the write direction of
  `aac.huffman`/`aac.adts`): PCM -> ADTS AAC-LC, mono (SCE) or stereo (CPE
  with per-band mid/side), 44100/48000 Hz, with a bit-budget rate-control
  loop. The encoder emits `ONLY_LONG_SEQUENCE` only — **the decoder reads
  block switching, the encoder does not write it**, so transients are not
  given short windows and percussive material gets pre-echo a real encoder
  would avoid. (Deciding WHEN to switch is a psychoacoustic question, not a
  filterbank one, which is why the two directions moved separately; the
  short/transition windows and grouping the encoder would need now exist in
  `aac.imdct`/`aac.ics`.) There is also **no psychoacoustic model** — bits follow the power law's
  own mild noise shaping plus the rate loop, not masking thresholds, so at
  equal bitrate ffmpeg will usually sound better while scoring *worse* on
  plain SNR. No TNS, PNS, intensity stereo, LTP, pulse coding or SBR/PS.
  `aac.encode`'s namespace docstring states each limitation and why.
  Also emits the 2-byte MPEG-4 `AudioSpecificConfig` an MP4/ISOBMFF `esds`
  needs, since MP4 carries these access units without ADTS headers.

## Usage

```clojure
(require '[aac.adts :as adts] '[aac.decode :as decode] '[aac.imdct :as imdct])

(adts/parse-header adts-bytes 0)
;; => {:mpeg-version :protection-absent? :profile :sampling-frequency-index
;;     :sample-rate :channel-configuration :frame-length :header-length
;;     :start :end}

(def frames (adts/frames adts-bytes))   ; vector of the above + :payload (raw AAC bytes)

;; decode a run of consecutive frames to PCM (mono, SCE) — any mix of window
;; sequences, so a whole file from frame 0 is fine:
(decode/decode-frames frames)
;; => concatenated float PCM samples (1024 per frame); (mapv decode/pcm->int16 ...)
;;    for 16-bit signed PCM matching a real decoder's output convention.

;; same, for STEREO (CPE, incl. mid/side) — two independent PCM channels:
(decode/decode-frames-stereo frames)
;; => {:left [...] :right [...]} (each concatenated float PCM, 1024/frame)
```

Encoding, the other direction. PCM is on the same full-scale convention as
`aac.decode`'s output — roughly ±32768, **not** ±1.0:

```clojure
(require '[aac.encode :as encode])

(encode/encode-mono samples {:sample-rate 44100 :bitrate 128000})
;; => {:adts [...]                    ; a complete ADTS byte stream
;;     :access-units [[...] ...]       ; the same frames WITHOUT ADTS headers, for MP4
;;     :audio-specific-config [0x12 0x08]   ; the 2 bytes an MP4 esds needs
;;     :encoder-delay 1024             ; samples a decoder must discard up front
;;     :frames 9 :bits 32810 :clipped-lines 0 :sample-rate 44100 :channels 1}

(encode/encode-stereo left right {:sample-rate 44100 :bitrate 192000})
```

Options: `:bitrate` (the rate loop's target, never exceeded), or `:base-sf`
to fix the quantizer and ignore it (constant quality instead of constant
rate); `:window-shape` 0 sine / 1 KBD; `:noise-shaping-alpha` and
`:rounding` (see `aac.quant` — both defaults are the ones this repo can
defend, and `:rounding`'s was chosen by measurement, not convention).

## Validation

**Framing** (`aac.adts`): validated against a real ffmpeg/libavcodec-encoded
ADTS stream (`ffmpeg -f lavfi -i sine=frequency=440 -c:a aac -f adts`) —
decoded header matches `ffprobe`'s reported sample rate/channel count, and
`frames` is checked for self-consistency (every computed frame boundary
lands on a real sync word).

**Decode** (`aac.decode`): validated against real
`ffmpeg -c:a aac -aac_pns 0`-encoded fixtures, comparing this decoder's PCM
output against `ffmpeg` decoding its OWN encode (the same golden-vector
methodology `org-iso-h264`'s `decode_test.clj` and `kotoba-lang/utsushi`'s
`mp4_h264_test.clj` use). Every fixture is decoded **from frame 0 to the end
of the file**, transients included. Max observed diff across every frame of
every fixture: **1 LSB** of a 16-bit sample (most samples bit-exact) — see
`test/aac/decode_test.cljk`'s docstring for the full methodology, tolerance
rationale (floating-point IMDCT rounding, not a decode bug), and why the
fixtures needed `-aac_pns 0`/`-aac_tns 0`.

**Block switching** (`aac.imdct`/`aac.ics`): two dedicated fixtures
(`blockswitch-{mono,stereo}-nopns.aac`) put a click in the MIDDLE of a tone,
so the encoder block-switches somewhere other than the stream onset and the
short-block run is entered and left with real, non-zero overlap-add history
on both sides. The tests **assert the fixture actually contains all four
window sequences and a non-trivial window grouping** before comparing any
PCM — otherwise a fixture that had drifted to long blocks only would pass
while exercising nothing. Both fixtures match ffmpeg's own decode to the
same **1 LSB** across all 23 frames.

That the 2 LSB bound is not merely permissive was checked by breaking the
implementation on purpose and confirming `kbb -M:test -n aac.decode-test`
goes red:

| deliberate break | result | worst diff |
|---|---|---|
| (none) | 0 failures | 1 LSB |
| LONG_START's transition shaping removed (its right half windowed as a full long falling window) | 12 failures in 4 tests | 6087 LSB |
| EIGHT_SHORT de-interleave skipped (short blocks transformed in the bitstream's grouped order) | 24 failures in 4 tests | 35468 LSB |

Both breaks leave `silence-golden-vector` and the side-info unit tests
passing, which is the right selectivity: a silent stream has no transient to
block-switch on. The folded IMDCT is separately pinned against a literal
transcription of §4.6.11.3.1's formula (`aac.imdct/imdct-reference`), which
they match to ~1e-13 absolute.

**Stereo/mid-side** (`aac.stereo`): validated the same way against a real
`ffmpeg -c:a aac -aac_pns 0 -aac_is 0`-encoded STEREO fixture with
channel-distinguishable content (left 440 Hz / right 880 Hz tones), whose
real `common_window=1`/`ms_mask_present=1` side info has a genuine per-band
MIX of `ms_used` bits (not uniformly on/off) — exercising both the
M/S-reconstructed and plain-L/R-passed-through code paths in the same
frame. Both channels independently match `ffmpeg`'s own PCM decode to the
same **1 LSB** max-diff as the mono case — see
`test/aac/decode_test.cljk`'s `stereo-golden-vector` fixture comment for why
`-aac_is 0` (disabling INTENSITY STEREO specifically, a separate
out-of-scope tool) was additionally required beyond `-aac_pns 0`.

**Encode** (`aac.encode`): the same golden-vector methodology, run in the
other direction — this repo encodes and **real ffmpeg decodes**. There is no
reference encoder to diff against (two conformant AAC encoders produce
entirely different bitstreams and neither is wrong), so the claim being
checked is the only one worth making: an independent decoder reads this
encoder's output and recovers the audio. `ffmpeg`'s decode of the committed
`encode-tone-{mono,stereo}.aac` fixtures agrees with this repo's own decode
of the same bitstream to **2 LSB**, and recovers the source at **38.2 dB**
SNR (mono, 125.6 kbit/s) / **37.9 dB** per channel (stereo, 182.5 kbit/s).
Those fixtures deliberately mix tones with broadband dither, which is what
holds the number down — a tones-only source reaches ~62 dB at the same rate.
The fixtures include ffmpeg's answer so CI needs no
ffmpeg; regenerate them with `kbb -M:fixtures` (see `aac.dev.fixtures`).
Byte-exactness against the fixture is deliberately not asserted —
`Math/pow`/`Math/cos` are not required to be identical across platforms, so
that would be a portability trap rather than a correctness check; see
`test/aac/encode_test.cljk`'s docstring.

The forward filterbank (`aac.mdct`) is pinned by perfect reconstruction
rather than by a reference: `analyze-frame` -> `aac.imdct/decode-frame`
returns the input signal to ~1e-6 absolute for both window shapes, and the
test also asserts that it FAILS at a perturbed forward scale, so a
self-consistent-but-wrongly-scaled transform pair could not pass. All ~1240
Annex 4.A spectral table entries round-trip through the encode direction and
back, with the bit cost predicted exactly.

The Kaiser-Bessel Derived (KBD) window construction (`aac.imdct/kbd-window`)
and the ~1360-row Annex 4.A Huffman codebook tables
(`aac.huffman-tables`) were independently cross-verified against real
reference decoders' own data during development — see those namespaces'
docstrings for the methodology (this matters because the ISO spec PDF's
own KBD formula didn't extract cleanly from OCR, and the Huffman tables
are large enough that a transcription error would be very hard to catch
by eye).

## Test

```sh
kbb -M:test
kbb -M:lint
kbb -M:fixtures   # regenerate the encode-side fixtures (needs ffmpeg)
```

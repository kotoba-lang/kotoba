(ns aac.tables
  "Scalefactor-band (SWB) boundary tables, ISO/IEC 14496-3:2005 Table 4.110
   (`num_swb_long_window`/`swb_offset_long_window` and
   `num_swb_short_window`/`swb_offset_short_window`, §4.5.2.3.2/4.5.2.3.3
   `window_grouping_info`). `swb_offset[sfb]` is the index of the lowest
   spectral coefficient of scalefactor band `sfb`; `swb_offset[num_swb]` is
   always the transform length (1024 long / 128 short) as a sentinel upper
   bound.

   Which of the two tables applies is decided by `window_sequence`, not by
   the frame length: ONLY_LONG_SEQUENCE, LONG_START_SEQUENCE and
   LONG_STOP_SEQUENCE all use the LONG table (they are all 2048-point
   transforms — only their window SHAPES differ, see `aac.imdct`), and
   EIGHT_SHORT_SEQUENCE uses the SHORT one, once per 128-line window.
   `swb-offsets-for` below encodes that choice so callers do not have to.

   Scope: only the 44.1 kHz / 48 kHz tables are transcribed (Table 4.110
   states these two sample rates share one row, for both window lengths) —
   this repo's fixtures are all 44100 Hz (see `aac.decode`'s namespace
   docstring for the sample-rate scope statement). Other
   `sampling_frequency_index` values throw rather than silently
   mis-decode; add their Table 4.11x rows here if a future fixture needs
   them."
  )

(def ^:private swb-offset-long-44100-48000
  "Table 4.110 (44.1/48 kHz, LONG_WINDOW / LONG_START / LONG_STOP), 49 bands
   + the transform-length sentinel (1024)."
  [0 4 8 12 16 20 24 28 32 36 40 48 56 64 72
   80 88 96 108 120 132 144 160 176 196 216 240 264 292
   320 352 384 416 448 480 512 544 576 608 640 672 704 736
   768 800 832 864 896 928 1024])

(def ^:private num-swb-long-44100-48000 49)

(def ^:private swb-offset-short-44100-48000
  "Table 4.110 (44.1/48 kHz, SHORT_WINDOW), 14 bands + the short-transform-
   length sentinel (128). Cross-verified against BOTH of the independent
   reference decoders this repo checks its transcribed tables against
   (FAAD2's `swb_offset_128_48` and FFmpeg's `ff_swb_offset_128` row for
   sampling_frequency_index 3/4/5) — same methodology as `aac.imdct`'s KBD
   window and `aac.huffman-tables`' Annex 4.A tables, and worth doing here
   because a wrong band boundary does not throw: it silently shifts every
   scalefactor onto the wrong coefficients."
  [0 4 8 12 16 20 28 36 44 56 68 80 96 112 128])

(def ^:private num-swb-short-44100-48000 14)

(def sampling-frequency-index->swb-offset-long
  "sampling_frequency_index -> swb_offset_long_window vector (49+1 entries,
   last = 1024). Only 4 (44100 Hz) and 3 (48000 Hz) populated (Table 4.110);
   see namespace docstring."
  {3 swb-offset-long-44100-48000
   4 swb-offset-long-44100-48000})

(def sampling-frequency-index->num-swb-long
  {3 num-swb-long-44100-48000
   4 num-swb-long-44100-48000})

(def sampling-frequency-index->swb-offset-short
  "sampling_frequency_index -> swb_offset_short_window vector (14+1 entries,
   last = 128). Same populated set as the long table."
  {3 swb-offset-short-44100-48000
   4 swb-offset-short-44100-48000})

(def sampling-frequency-index->num-swb-short
  {3 num-swb-short-44100-48000
   4 num-swb-short-44100-48000})

(defn swb-offsets
  "swb_offset_long_window for `sfi` (sampling_frequency_index), or throws if
   this sample rate isn't in scope (see namespace docstring)."
  [sfi]
  (or (get sampling-frequency-index->swb-offset-long sfi)
      (throw (ex-info "aac.tables: unsupported sampling_frequency_index (only 44100/48000 Hz long-window SWB table is in scope)"
                       {:sampling-frequency-index sfi}))))

(defn num-swb [sfi]
  (or (get sampling-frequency-index->num-swb-long sfi)
      (throw (ex-info "aac.tables: unsupported sampling_frequency_index"
                       {:sampling-frequency-index sfi}))))

(defn swb-offsets-short
  "swb_offset_short_window for `sfi` — the band boundaries WITHIN one
   128-line short window (EIGHT_SHORT_SEQUENCE)."
  [sfi]
  (or (get sampling-frequency-index->swb-offset-short sfi)
      (throw (ex-info "aac.tables: unsupported sampling_frequency_index (only 44100/48000 Hz short-window SWB table is in scope)"
                       {:sampling-frequency-index sfi}))))

(defn num-swb-short [sfi]
  (or (get sampling-frequency-index->num-swb-short sfi)
      (throw (ex-info "aac.tables: unsupported sampling_frequency_index"
                       {:sampling-frequency-index sfi}))))

(defn swb-offsets-for
  "The swb_offset table `window-sequence` selects: the SHORT one for
   EIGHT_SHORT_SEQUENCE (2), the LONG one for the other three (see namespace
   docstring)."
  [sfi window-sequence]
  (if (= window-sequence 2)
    (swb-offsets-short sfi)
    (swb-offsets sfi)))

(defn num-swb-for
  "`num_swb` for `window-sequence` — the largest legal `max_sfb`."
  [sfi window-sequence]
  (if (= window-sequence 2)
    (num-swb-short sfi)
    (num-swb sfi)))

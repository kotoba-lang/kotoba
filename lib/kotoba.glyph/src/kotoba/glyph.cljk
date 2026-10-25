(ns kotoba.glyph
  "KAMI glyph — CPU-side SDF text-layout CONTRACT, ported from kami-text
  (Rust, deleted-not-migrated per ADR-2607010930 Phase 4). Pure `.cljc`:
  glyph/font-slot classification, grapheme + script/direction/font-slot run
  segmentation, uniform-grid atlas rect packing (mono/SDF + color/emoji),
  instanced-quad layout math (glyph placement, advance accumulation), and
  capacity-bounded LRU key-set management for dynamic atlases.

  What is NOT here (see README `Unported` for the full rationale): real
  SDF rasterization from font outlines, OpenType/HarfBuzz shaping (GPOS
  kerning), UAX#9 bidi visual reordering, native emoji color rasterization,
  and the bundled font binaries — those stay host/platform-adapter
  concerns, not layout math.

  This namespace is a thin facade over the implementation namespaces; call
  them directly for anything not re-exported here."
  (:require [kotoba.glyph.atlas :as atlas]
            [kotoba.glyph.dynamic :as dynamic]
            [kotoba.glyph.layout :as layout]
            [kotoba.glyph.segment :as segment]
            [kotoba.glyph.slot :as slot]))

;; slot / classification
(def glyph-key slot/glyph-key)
(def font-slot-for-char slot/font-slot-for-char)
(def font-slot-for-cluster slot/font-slot-for-cluster)

;; segmentation
(def graphemes segment/graphemes)
(def segment-text-runs segment/segment-text-runs)

;; atlas packing
(def pack-mono-atlas atlas/pack-mono-atlas)
(def pack-color-atlas atlas/pack-color-atlas)
(def ascii-procedural-atlas atlas/ascii-procedural-atlas)

;; layout / instanced quads
(def layout-text layout/layout-text)
(def layout-color-glyphs layout/layout-color-glyphs)

;; dynamic capacity/LRU
(def make-dynamic-state dynamic/make-state)
(def ensure-keys dynamic/ensure-keys)

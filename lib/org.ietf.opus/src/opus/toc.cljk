(ns opus.toc
  "Opus (IETF RFC 6716) packet TOC (table-of-contents) byte parsing — RFC
   6716 §3.1. The TOC byte selects mode/bandwidth/frame-size (`config`,
   Table 2), whether the packet is stereo, and the frame-count code (which
   `opus.packet` uses to split the packet into individual Opus frames).
   Pure cljc, zero dependencies. Framing/parameter metadata only — the
   actual SILK/CELT audio decode is out of scope, matching this repo
   family's 'coded payload stays opaque, only framing/metadata is decoded'
   boundary (see org-iso-h264/org-iso-aac siblings).

   New implementation (not an extraction — utsushi.bitstream had no Opus
   support at all, not even a TODO stub) as part of the kotoba-lang
   reverse-domain media/graphics standards-substrate split
   (com-junkawasaki/root)."
  )

(defn- entry [mode bandwidth ms] {:mode mode :bandwidth bandwidth :frame-size-ms ms})

;; RFC 6716 §3.1 Table 2, config 0..31.
(def configs
  (vec (concat
        (for [bw [:narrowband :mediumband :wideband] ms [10 20 40 60]]
          (entry :silk bw ms))
        (for [ms [10 20]] (entry :hybrid :super-wideband ms))
        (for [ms [10 20]] (entry :hybrid :fullband ms))
        (for [bw [:narrowband :wideband :super-wideband :fullband] ms [2.5 5 10 20]]
          (entry :celt bw ms)))))

(defn parse
  "Parse the TOC byte (first byte of an Opus packet) →
   {:config :mode :bandwidth :frame-size-ms :stereo? :frame-count-code}."
  [toc-byte]
  (let [config (bit-and (bit-shift-right toc-byte 3) 0x1F)
        stereo? (= 1 (bit-and (bit-shift-right toc-byte 2) 1))
        code    (bit-and toc-byte 3)]
    (merge (nth configs config) {:config config :stereo? stereo? :frame-count-code code})))

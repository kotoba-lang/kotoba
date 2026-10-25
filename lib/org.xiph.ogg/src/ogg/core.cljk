(ns ogg.core
  "The Ogg container (RFC 3533) in portable `.cljc`, both directions.

   ```clojure
   (require '[ogg.core :as ogg])

   (ogg/ogg? bytes)                            ; signature sniff
   (ogg/logical-streams bytes)                 ; every stream, packets reassembled
   (ogg/packets bytes)                         ; the first stream's packets
   (ogg/identify (first (ogg/logical-streams bytes)))  ; :opus / :vorbis / :flac
   (ogg/build {:serial 1 :packets [...] :granules [...] :flush-after #{0 1}})
   ```

   Ogg carries *packets*, not samples: it is the framing layer that Vorbis, Opus,
   FLAC, Speex and Theora ride in, and it knows nothing about any of them. That
   separation is why this repo exists — `org-ietf-opus` decodes Opus packets but
   had no way to get them out of a `.opus` file, because a `.opus` file is Ogg.

   Bytes in and out are vectors of unsigned 0-255 integers. Zero dependencies:
   beyond framing, Ogg's only primitive is its own CRC-32 variant."
  (:require [ogg.page :as page]
            [ogg.stream :as stream]))

(defn- ascii [s] (mapv #(#?(:clj int :cljs (fn [c] (.charCodeAt c 0))) %) (seq s)))

(def ^:private signatures
  ;; the first packet of a logical stream names its codec
  [[:opus (ascii "OpusHead")]
   [:vorbis (into [0x01] (ascii "vorbis"))]
   ;; the FLAC-in-Ogg mapping prefixes its own header with 0x7F, so the bare
   ;; "fLaC" magic of a native .flac file does not appear first
   [:flac (into [0x7f] (ascii "FLAC"))]
   [:speex (ascii "Speex   ")]
   [:theora (into [0x80] (ascii "theora"))]
   [:skeleton (ascii "fishead")]])

(defn ogg?
  "True when `data` starts with the OggS capture pattern."
  [data]
  (= [0x4f 0x67 0x67 0x53] (vec (take 4 data))))

(defn identify
  "Name the codec of a logical stream (or of a bare first packet) → `:opus`,
   `:vorbis`, `:flac`, `:speex`, `:theora`, `:skeleton`, or `:unknown`.

   A sniff of the first packet, not a parse: this repo decodes none of these
   formats, it only says which one it is carrying."
  [stream-or-packet]
  (let [pkt (vec (if (map? stream-or-packet)
                   (first (:packets stream-or-packet))
                   stream-or-packet))]
    (or (some (fn [[codec pattern]]
                (when (and (>= (count pkt) (count pattern))
                           (= pattern (subvec pkt 0 (count pattern))))
                  codec))
              signatures)
        :unknown)))

(def pages
  "Every page in a physical stream. See `ogg.page/pages`."
  page/pages)

(def logical-streams
  "Every logical stream, packets reassembled. See `ogg.stream/logical-streams`."
  stream/logical-streams)

(def packets
  "The packets of one logical stream. See `ogg.stream/packets`."
  stream/packets)

(def build
  "Serialise packets into pages. See `ogg.stream/build`."
  stream/build)

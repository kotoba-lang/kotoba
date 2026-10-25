(ns opus.packet
  "Opus (IETF RFC 6716) packet → frame splitting, per the TOC byte's
   frame-count code (RFC 6716 §3.2 'Frame Packing'). Frames stay opaque
   byte ranges — SILK/CELT decode is out of scope (see opus.toc). Pure
   cljc, zero dependencies.

   New implementation as part of the kotoba-lang reverse-domain
   media/graphics standards-substrate split (com-junkawasaki/root)."
  (:require [opus.toc :as toc]))

(defn- u8 [b i] (bit-and (int (nth b i)) 0xff))

(defn- read-length
  "RFC 6716 §3.2.1 frame length coding: 1 byte if < 252, else a 2-byte
   encoding (L2*4 + L1). Returns [length bytes-consumed]."
  [b i]
  (let [l1 (u8 b i)]
    (if (< l1 252)
      [l1 1]
      (let [l2 (u8 b (inc i))]
        [(+ l1 (* l2 4)) 2]))))

(defn frames
  "Split an Opus packet `b` (vector of unsigned bytes, TOC byte at index 0)
   into {:toc <opus.toc/parse result> :frames [[start end) ...]}."
  [b]
  (let [n     (count b)
        t     (toc/parse (u8 b 0))
        code  (:frame-count-code t)]
    {:toc t
     :frames
     (case code
       ;; code 0: 1 frame, whole remaining packet.
       0 [{:start 1 :end n}]

       ;; code 1: 2 equal-size frames, no length byte (remainder/2 each).
       1 (let [half (quot (- n 1) 2)]
           [{:start 1 :end (+ 1 half)} {:start (+ 1 half) :end n}])

       ;; code 2: 2 frames, first frame's length is explicitly coded.
       2 (let [[len1 consumed] (read-length b 1)
               f1-start (+ 1 consumed)
               f1-end   (+ f1-start len1)]
           [{:start f1-start :end f1-end} {:start f1-end :end n}])

       ;; code 3: arbitrary frame count M (RFC 6716 §3.2.5). Frame-count
       ;; byte: bit7=VBR flag, bit6=padding flag, bits0-5=M. Padding length
       ;; (if present) is itself length-coded and skipped. VBR: M-1 explicit
       ;; frame lengths, last frame = remainder. CBR: all M frames equal
       ;; size = remainder/M.
       3 (let [fc-byte (u8 b 1)
               vbr?    (= 1 (bit-and (bit-shift-right fc-byte 7) 1))
               pad?    (= 1 (bit-and (bit-shift-right fc-byte 6) 1))
               m       (bit-and fc-byte 0x3F)
               pos0    2
               [pad-len pad-consumed]
               (if pad?
                 (loop [pos pos0 total 0]
                   (let [v (u8 b pos)]
                     (if (= v 255)
                       (recur (inc pos) (+ total 254))
                       [(+ total v) (- (inc pos) pos0)])))
                 [0 0])
               pos1 (+ pos0 pad-consumed)]
           (if vbr?
             (let [[lens pos2]
                   (loop [i 0 pos pos1 acc []]
                     (if (= i (dec m))
                       [acc pos]
                       (let [[len consumed] (read-length b pos)]
                         (recur (inc i) (+ pos consumed) (conj acc len)))))
                   frame-end   (- n pad-len)
                   starts-ends (loop [ls lens pos pos2 acc []]
                                 (if (empty? ls)
                                   (conj acc {:start pos :end frame-end})
                                   (recur (rest ls) (+ pos (first ls))
                                          (conj acc {:start pos :end (+ pos (first ls))}))))]
               starts-ends)
             (let [avail    (- n pos1 pad-len)
                   per-frame (quot avail m)]
               (mapv (fn [i] {:start (+ pos1 (* i per-frame)) :end (+ pos1 (* (inc i) per-frame))})
                     (range m)))))

       (throw (ex-info "opus: bad frame-count-code" {:code code})))}))

(ns w3.webcodecs.codec-string
  "Portable (no JS interop) parsing/construction of WebCodecs codec strings —
   the string identifiers passed to VideoDecoderConfig/VideoEncoderConfig's
   `codec` field (e.g. \"avc1.42001f\"), per the WebCodecs Codec Registration
   spec (https://www.w3.org/TR/webcodecs-avc-codec-registration/) which in
   turn borrows the AVC string syntax from RFC 6381 / ISO/IEC 14496-15.

   This is the one piece of WebCodecs binding logic that has no browser
   dependency (unlike VideoDecoder/VideoEncoder construction, which needs a
   real UA — see w3.webcodecs), so unlike org-w3-webgpu (zero portable logic,
   no test suite) this namespace is `.cljc` and carries real tests."
  (:require [kotoba.lang.text :as str]))

;; --- AVC (H.264) `avc1.PPCCLL` ---------------------------------------------
;;
;; PP = profile_idc (hex byte)
;; CC = constraint_set flags byte: bits 7..2 are constraint_set0..5_flag
;;      (MSB first), bits 1..0 are reserved-zero.
;; LL = level_idc (hex byte). level = level_idc / 10, EXCEPT level_idc == 11
;;      (0x0B) is ambiguous: it means level "1b" when constraint_set3_flag is
;;      set, otherwise level 1.1. (Historical artifact: level 1b predates the
;;      level_idc encoding and was folded in via this one flag re-use.)

(def avc-profile-names
  "profile_idc -> keyword name, per Table A-1 in the AVC spec (the subset
   WebCodecs/browsers actually emit or accept)."
  {0x42 :baseline
   0x4D :main
   0x58 :extended
   0x64 :high
   0x6E :high-10
   0x7A :high-422
   0xF4 :high-444-predictive})

(def avc-profile-idcs
  (into {} (map (fn [[k v]] [v k])) avc-profile-names))

(defn- constraint-set-flag?
  "true if constraint_setN_flag (n in 0..5) is set in the CC byte."
  [constraint-flags n]
  (when (<= 0 n 5)
    (bit-test constraint-flags (- 7 n))))

(defn- hex2
  "Render `b` (0-255) as exactly 2 uppercase hex digits."
  [b]
  (let [s #?(:clj  (Integer/toHexString (bit-and b 0xFF))
             :cljs (.toString (bit-and b 0xFF) 16))
        s (str/upper s)]
    (if (= 1 (count s)) (str "0" s) s)))

(defn- parse-hex-byte [s]
  #?(:clj  (Integer/parseInt ^String s 16)
     :cljs (js/parseInt s 16)))

(defn avc-level-idc->level
  "level_idc + constraint_flags -> level number, or :1b (keyword, since \"1b\"
   is not a valid Clojure number) for the ambiguous 11/constraint_set3 case."
  [level-idc constraint-flags]
  (if (and (= level-idc 11) (constraint-set-flag? constraint-flags 3))
    :1b
    (/ level-idc 10.0)))

(defn avc-level->level-idc
  "level number (e.g. 3.1) or :1b -> level_idc. :1b also requires the caller
   to set constraint_set3_flag in the CC byte (this fn only returns the LL
   byte value, 11, not the CC byte — see `format-avc-codec-string`)."
  [level]
  (if (= level :1b)
    11
    #?(:clj  (long (Math/round (double (* level 10))))
       :cljs (js/Math.round (* level 10)))))

(defn parse-avc-codec-string
  "\"avc1.42001f\" -> {:profile-idc 0x42 :profile :baseline
                        :constraint-flags 0x00 :level-idc 0x1f :level 3.1}
   Returns nil if `s` isn't a well-formed avc1/avc3 codec string."
  [s]
  (when-let [[_ four-cc pp cc ll] (re-matches #"(avc[13])\.([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})" (str s))]
    (let [profile-idc (parse-hex-byte pp)
          constraint-flags (parse-hex-byte cc)
          level-idc (parse-hex-byte ll)]
      {:four-cc four-cc
       :profile-idc profile-idc
       :profile (avc-profile-names profile-idc)
       :constraint-flags constraint-flags
       :level-idc level-idc
       :level (avc-level-idc->level level-idc constraint-flags)})))

(defn format-avc-codec-string
  "{:profile :baseline :constraint-flags 0 :level 3.1} -> \"avc1.42001f\".
   :profile may be a keyword (looked up in avc-profile-idcs) or a raw
   profile_idc int. :four-cc defaults to \"avc1\" (vs. \"avc3\", used for the
   length-delimited-NALU-with-inline-parameter-sets variant)."
  [{:keys [profile constraint-flags level four-cc] :or {constraint-flags 0 four-cc "avc1"}}]
  (let [profile-idc (if (keyword? profile) (avc-profile-idcs profile) profile)
        level-idc (avc-level->level-idc level)
        cc (if (= level :1b) (bit-set constraint-flags (- 7 3)) constraint-flags)]
    (str four-cc "." (hex2 profile-idc) (hex2 cc) (hex2 level-idc))))

;; --- Opus / AAC (audio, used alongside AVC in an EncodedAudioChunk config) -

(defn parse-simple-codec
  "Non-AVC codec strings WebCodecs also accepts are simple fixed tokens with
   no embedded profile/level (\"opus\", \"alaw\", \"ulaw\", \"flac\", or the
   4-part dotted mp4a.oo.OO... AAC form) — this repo only needs to
   round-trip the token itself for now; full mp4a object-type parsing is out
   of scope for v0 (utsushi owns AAC bitstream concerns, not this binding
   layer)."
  [s]
  (when (and (string? s) (seq s)) {:codec (str s)}))

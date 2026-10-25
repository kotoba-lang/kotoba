(ns iec60870.time
  "CP56Time2a — the seven-octet absolute time tag IEC 60870-5-104 attaches
  to timestamped information objects (e.g. M_ME_TF_1, type 36).

      octet 0-1  milliseconds, 0..59999, 16-bit LE
      octet 2    bits 0-5 minutes 0..59, bit 6 reserved, bit 7 IV (invalid)
      octet 3    bits 0-4 hours 0..23, bits 5-6 reserved, bit 7 SU (summer time)
      octet 4    bits 0-4 day-of-month 1..31, bits 5-7 day-of-week 1..7
      octet 5    bits 0-3 month 1..12, bits 4-7 reserved
      octet 6    bits 0-6 year 0..99 (2-digit, relative to a century the
                 station configuration supplies), bit 7 reserved

  ;; constructed, not a published spec vector — this bit layout is
  ;; reproduced from this session's recollection of the CP56Time2a
  ;; structure (IEC 60870-5-101's common time-tag definition, referenced by
  ;; -104), not cross-checked against the standard's own table text this
  ;; session. The mechanics (bit positions, little-endian millisecond
  ;; field) are the part of this namespace to trust; the exact section
  ;; number is not asserted."
  )

(defn encode-cp56time2a
  [{:keys [milliseconds minutes invalid hours summer-time day-of-month day-of-week month year]}]
  [(bit-and milliseconds 0xFF)
   (bit-and (unsigned-bit-shift-right milliseconds 8) 0xFF)
   (bit-or (bit-and minutes 0x3F) (if invalid 0x80 0))
   (bit-or (bit-and hours 0x1F) (if summer-time 0x80 0))
   (bit-or (bit-and day-of-month 0x1F) (bit-shift-left (bit-and day-of-week 0x07) 5))
   (bit-and month 0x0F)
   (bit-and year 0x7F)])

(defn decode-cp56time2a
  "Decode 7 bytes of CP56Time2a starting at `i`. Returns
  `{:point {...} :size 7}`, following the same `{:point :size}` shape
  `dnp3.objects`'s point decoders use, since a timestamp is exactly a
  fixed-size sub-object nested inside a larger information element."
  [bs i]
  {:point {:milliseconds (+ (nth bs i) (* 256 (nth bs (+ i 1))))
           :minutes (bit-and (nth bs (+ i 2)) 0x3F)
           :invalid (bit-test (nth bs (+ i 2)) 7)
           :hours (bit-and (nth bs (+ i 3)) 0x1F)
           :summer-time (bit-test (nth bs (+ i 3)) 7)
           :day-of-month (bit-and (nth bs (+ i 4)) 0x1F)
           :day-of-week (bit-and (unsigned-bit-shift-right (nth bs (+ i 4)) 5) 0x07)
           :month (bit-and (nth bs (+ i 5)) 0x0F)
           :year (bit-and (nth bs (+ i 6)) 0x7F)}
   :size 7})

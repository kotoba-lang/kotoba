(ns codec-primitives.scan)

(def zigzag-4x4
  "4x4 ブロックの標準 zigzag スキャン順(row-major index の並び替え)。
   H.264(ITU-T H.264 / ISO/IEC 14496-10, Table 8-12 相当)の既定 4x4
   zig-zag scan と同じ順序(ffmpeg の zigzag_scan テーブルと一致)。"
  [0 1 4 8 5 2 3 6 9 12 13 10 7 11 14 15])

(defn scan
  "row-major の16要素ベクタをscan-order(permutation vector)で並び替える。"
  [scan-order row-major-vec]
  (mapv #(nth row-major-vec %) scan-order))

(defn unscan
  "scan の逆操作。"
  [scan-order scanned-vec]
  (let [result (vec (repeat (count scan-order) nil))]
    (reduce (fn [acc [pos val]] (assoc acc pos val))
            result
            (map vector scan-order scanned-vec))))

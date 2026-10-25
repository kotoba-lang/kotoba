(ns codec-primitives.transform)

(defprotocol BlockTransform
  "画素残差ブロックの正変換/逆変換の契約。実装(係数テーブル・ブロックサイズ)は
   codec 固有(例: h264.transform, av1.transform)が提供する。ここでは共有しない。"
  (forward [this block] "空間領域ブロック(2D int vector)を係数領域へ変換する")
  (inverse [this coeffs] "係数領域(2D int vector)を空間領域ブロックへ逆変換する"))

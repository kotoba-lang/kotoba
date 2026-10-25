(ns codec-primitives.quant)

(defprotocol QuantScale
  "QP から量子化スケールを得る契約。実際のテーブル値は codec 固有実装が持つ。"
  (qp->scale [this qp] "QP(int)から量子化スケール(number)を返す"))

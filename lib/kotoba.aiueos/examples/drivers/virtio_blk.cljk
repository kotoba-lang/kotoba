;; virtio-blk driver logic — safe-kotoba subset (no eval/require/slurp/reflection).
;;
;; Phase-0 stub: a pure, deterministic computation standing in for the real
;; request path. In later phases `read-block` takes a DmaBuffer capability and
;; drives the virtqueue via kernel-provided mmio/dma/irq adapters; the shape
;; (sector in, status out) is what the block/read capability exports.
(defn read-block [sector]
  (+ sector 1))

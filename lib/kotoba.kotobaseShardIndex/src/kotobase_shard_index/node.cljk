(ns kotobase-shard-index.node
  "Node adapters: the sha-256 the codec asks for, and an object-per-CID store
  on the filesystem.

  The filesystem store is the S3 shape with the network removed — one
  immutable object per key, range-readable, never updated in place. Swapping
  it for a real bucket changes the latency of a GET and nothing about how many
  the query issues, which is the quantity every claim here rests on."
  (:require ["node:crypto" :as crypto]
            ["node:fs" :as fs]
            ["node:path" :as path]
            [kotobase-shard-index.block :as block]))

(defn sha256-hex [s]
  (-> (.createHash crypto "sha256") (.update s "utf8") (.digest "hex")))

(defn fs-store
  "Object-per-CID under `dir`. Content-addressed names mean a write is never
  an update, so there is no consistency window to reason about."
  [dir]
  (when-not (.existsSync fs dir)
    (.mkdirSync fs dir #js {:recursive true}))
  (reify
    block/IBlockStore
    (-get [_ cid]
      (let [p (.join path dir cid)]
        (when (.existsSync fs p) (.readFileSync fs p "utf8"))))
    (-get-range [_ cid offset length]
      (let [p (.join path dir cid)]
        (when (.existsSync fs p)
          (let [buf (.readFileSync fs p)
                end (min (.-length buf) (+ offset length))]
            (.toString (.subarray buf offset end) "utf8")))))
    block/IBlockSink
    (-put! [_ cid payload]
      (.writeFileSync fs (.join path dir cid) payload "utf8")
      cid)))

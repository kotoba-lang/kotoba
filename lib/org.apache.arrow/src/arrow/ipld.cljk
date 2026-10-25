(ns arrow.ipld
  "Read an Arrow IPC file that is stored as an IPLD byte DAG.

  `arrow.source/open` asks the world for `[start, end)` and nothing else. That
  is the whole seam, and it means an Arrow file does not have to be one object:
  chunked into an FBL, it can live as content-addressed blocks and still be
  read the way Arrow wants to read it -- footer first, then one batch header,
  then one column's buffers.

  This is the payoff of both halves. Arrow already fetches only the ranges it
  needs, and FBL already fetches only the leaves a range overlaps, so the
  composition reads a column out of a chunked file without materialising the
  file. Nothing here re-implements either; it is the adapter between two
  range contracts that already agree on `[start, end)`.

  ## Why this deliberately does not claim to borrow

  `columnar.bytes` has a second protocol, `IByteViewSource`, for sources that
  can hand back a view of storage they already hold. This source does not
  implement it, and that is a statement rather than an omission: a range
  spanning two FBL leaves is not contiguous in any buffer, so producing it
  allocates. Implementing the borrow protocol and copying underneath would
  make the copy boundary invisible at exactly the layer that exists to make
  it visible -- `arrow.source` reports `:copy-boundary`, and a byte source
  that lied about its own would corrupt that report from below.

  A caller that wants the distinction reads `fbl/read-range` directly, which
  reports `:borrowed-leaf` or `:assembled` per range."
  (:require [arrow.source :as asrc]
            [columnar.bytes :as bytes]
            [ipld.fbl :as fbl]))

(defn source
  "A `columnar.bytes/IByteSource` over the FBL rooted at `root-cid`.

  `get-fn` maps a CID string to block bytes and is expected to verify; this
  passes it through to `ipld.fbl`, which fetches only the leaves a range
  overlaps and refuses a short read rather than returning one. That refusal is
  the load-bearing part here: Arrow computes buffer offsets from the footer
  and does not re-check the width it got back, so a layout that quietly
  returned fewer bytes would shift every field after it and still parse."
  [get-fn root-cid]
  (let [size (fbl/size get-fn root-cid)]
    (reify bytes/IByteSource
      (-size [_] size)
      (-read-range [_ start end]
        (:bytes (fbl/read-range get-fn root-cid start end))))))

(defn open
  "An `arrow.source` column source over an Arrow IPC file stored as an FBL."
  [get-fn root-cid]
  (asrc/open (source get-fn root-cid)))

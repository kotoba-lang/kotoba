(ns filecoin.node.protocols
  "The seams. Everything a node does that this library deliberately does not.

  Each of these is a place where a real node reaches outside itself — to a
  disk, to a curve implementation, to a randomness beacon, to a peer. Naming
  them as protocols keeps the encoding above them portable, and keeps the
  library honest about the fact that it cannot validate a block on its own:
  it can tell you the bytes a signature covers, and nothing about whether the
  signature is good.")

(defprotocol IBlockstore
  "Content-addressed storage. Everything the chain refers to — headers,
  message AMTs, actor state HAMTs — is a CID resolved through one of these."
  (get-block [this cid] "CID string → bytes, or nil.")
  (put-block [this bytes] "bytes → the CID they were stored under."))

(defprotocol IVerifier
  "Signature verification, which needs curves this library does not carry.

  `verify-bls` is the one that matters most and is hardest to obtain: block
  signatures and `f3` accounts are BLS12-381, a pairing-friendly curve with
  no implementation anywhere in this workspace. `verify-secp256k1` has one
  (`kotoba-lang/eth-crypto`) and still belongs behind a seam, because a node
  that pins a curve implementation stops being portable."
  (verify-secp256k1 [this digest signature public-key])
  (verify-bls [this message signature public-key])
  (verify-bls-aggregate [this messages signature public-keys]
    "The header's `bls-aggregate` covers every BLS message in the block at
    once. Verifying them individually is not the same check and will not
    reproduce the aggregate."))

(defprotocol IBeacon
  "drand. Every tipset carries beacon entries, and the randomness they supply
  is what makes the leader election unpredictable — so a node that cannot
  reach the beacon cannot validate a header, only parse it."
  (beacon-entry [this round] "round → the drand signature bytes for it."))

(defprotocol IChainStore
  "Enough of a chain view to answer the questions the pure code cannot.

  `tipset-messages` is what the base fee calculation needs: the utilisation
  form deduplicates by message CID and the premium form by (sender, nonce),
  and neither can be done from headers alone."
  (tipset-at [this height] "height → the tipset, or nil for a null round.")
  (tipset-messages [this tipset]
    "→ {:bls [messages…] :secp256k1 [signed-messages…]}, deduplicated."))

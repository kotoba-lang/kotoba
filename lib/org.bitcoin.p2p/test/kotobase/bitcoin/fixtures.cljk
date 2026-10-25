(ns kotobase.bitcoin.fixtures
  "REAL Bitcoin header data, hardcoded as test fixtures (per
  ADR-2607172600's verification bar: real historical header data proving
  validation logic against a real chain, not synthetic-only). Fetched
  from blockstream.info's public block-explorer REST API
  (`GET /api/block/<hash>/header` -> raw 80-byte header hex) on
  2026-07-17 and independently cross-checked in this session: each
  header's own sha256d, byte-reversed, was recomputed with plain
  `openssl dgst -sha256` chained twice and confirmed byte-for-byte equal
  to the well-known display hash before being hardcoded here -- these are
  not copied from memory of \"the genesis hash\", they are re-derived and
  verified from the raw header bytes.

  mainnet-headers-0-3 / testnet-headers-0-3: the first 4 headers (heights
  0-3, i.e. genesis + 3) of Bitcoin mainnet and testnet3, in chain order.
  Genesis's own :prev-block is 32 zero bytes on both networks (no
  predecessor) -- protocol_test.cljc's chain-validation tests start
  linkage checking from height 1."
  (:require [kotobase.bitcoin.protocol :as proto]))

(def mainnet-header-hex
  ["0100000000000000000000000000000000000000000000000000000000000000000000003ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a29ab5f49ffff001d1dac2b7c"
   "010000006fe28c0ab6f1b372c1a6a246ae63f74f931e8365e15a089c68d6190000000000982051fd1e4ba744bbbe680e1fee14677ba1a3c3540bf7b1cdb606e857233e0e61bc6649ffff001d01e36299"
   "010000004860eb18bf1b1620e37e9490fc8a427514416fd75159ab86688e9a8300000000d5fdcc541e25de1c7a5addedf24858b8bb665c9f36ef744ee42c316022c90f9bb0bc6649ffff001d08d2bd61"
   "01000000bddd99ccfda39da1b108ce1a5d70038d0a967bacb68b6b63065f626a0000000044f672226090d85db9a9f2fbfe5f0f9609b387af7be5b7fbb7a1767c831c9e995dbe6649ffff001d05e0ed6d"])

(def mainnet-header-hash-hex
  ["000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
   "00000000839a8e6886ab5951d76f411475428afc90947ee320161bbf18eb6048"
   "000000006a625f06636b8bb6ac7b960a8d03705d1ace08b1a19da3fdcc99ddbd"
   "0000000082b5015589a3fdf2d4baff403e6f0be035a5d9742c1cae6295464449"])

(def testnet-header-hex
  ["0100000000000000000000000000000000000000000000000000000000000000000000003ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4adae5494dffff001d1aa4ae18"
   "0100000043497fd7f826957108f4a30fd9cec3aeba79972084e90ead01ea330900000000bac8b0fa927c0ac8234287e33c5f74d38d354820e24756ad709d7038fc5f31f020e7494dffff001d03e4b672"
   "0100000006128e87be8b1b4dea47a7247d5528d2702c96826c7a648497e773b800000000e241352e3bec0a95a6217e10c3abb54adfa05abb12c126695595580fb92e222032e7494dffff001d00d23534"
   "0100000020782a005255b657696ea057d5b98f34defcf75196f64f6eeac8026c0000000041ba5afc532aae03151b8aa87b65e1594f97504a768e010c98c0add79216247186e7494dffff001d058dc2b6"])

(def testnet-header-hash-hex
  ["000000000933ea01ad0ee984209779baaec3ced90fa3f408719526f8d77f4943"
   "00000000b873e79784647a6c82962c70d228557d24a747ea4d1b8bbe878e1206"
   "000000006c02c8ea6e4ff69651f7fcde348fb9d557a06e6957b65552002a7820"
   "000000008b896e272758da5297bcd98fdc6d97c9b765ecec401e286dc1fdbe10"])

(defn decoded [hex-strs]
  (mapv #(proto/decode-block-header (proto/hex->bytes %)) hex-strs))

(def mainnet-headers (decoded mainnet-header-hex))
(def testnet-headers (decoded testnet-header-hex))

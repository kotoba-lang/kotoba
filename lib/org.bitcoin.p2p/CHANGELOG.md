# Changelog

## 0.5.2 — 2026-07-31

- Match Bitcoin Core's exact `SetCompact` negative and overflow boundaries.
- Accept exponent 33/34 compact targets when leading mantissa bytes keep the
  decoded target within 256 bits, while continuing to reject true overflow.

## 0.5.1 — 2026-07-30

- Compute each decoded block-header hash once instead of repeating SHA-256d.
- Encode JVM display-order hashes directly into a fixed `char[]`, avoiding
  reflective and lazy-sequence allocation during mainnet-scale header loads.

## 0.5.0 — 2026-07-30

- Use the JDK SHA-256 provider for JVM message checksums and block hashes while
  retaining the portable ClojureScript implementation and identical bytes.

## 0.4.1 — 2026-07-30

- Decode the full unsigned 64-bit range on the JVM without signed-long
  overflow, allowing interoperability with arbitrary peer version and ping
  nonces.
- Encode and decode `net_addr` ports in the protocol-mandated network byte
  order instead of little-endian.

## 0.4.0 — 2026-07-30

- Add Bitcoin Core v31.1 testnet4 and default signet proof-of-work parameters
  and hard-coded genesis trust anchors.
- Implement BIP94 testnet4 retargeting from the first block of each difficulty
  period while preserving the minimum-difficulty exception between periods.

## 0.3.0 — 2026-07-30

- Add Bitcoin Core-compatible regtest genesis, magic, port, proof limit, and
  no-retarget header consensus for deterministic fork/reorg testing.

## 0.2.0 — 2026-07-30

- Enforce mainnet and testnet3 expected difficulty, including bounded
  retargeting and testnet minimum-difficulty recovery.
- Enforce median-time-past and the two-hour future timestamp bound.
- Add exact 256-bit header work, cumulative chainwork, and more-work fork
  comparison.
- Persist height and chainwork atomically with validated header batches.
- Reject wrong-network magic, oversized messages, more than 2,000 headers,
  non-zero header transaction counts, truncation, and trailing data.
- Refuse legacy stored tips without chainwork instead of silently assigning an
  incorrect work value.

This remains a read-only headers client. It does not validate transactions,
Merkle roots, Script, or the UTXO set and must not be described as a full node.

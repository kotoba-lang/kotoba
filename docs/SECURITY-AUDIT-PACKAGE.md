# Kotoba / kotobase.net — Security Audit Acceptance Package

> Purpose: give a third-party auditor (code audit + pen-test) and an enterprise
> procurement reviewer a single, grounded entry point — scope, trust boundaries,
> crypto inventory, the authn/authz model, the data-at-rest exposure model, key
> management & recovery, the audit trail, and an honest risk register with the
> deferred items called out. Every claim cites source (`crate/path.rs`) so it can
> be checked, not taken on faith.
>
> Companion docs: [`SECURITY-ARCHITECTURE.md`](./SECURITY-ARCHITECTURE.md)
> (R0–R3d accountability layers), [`ADR-sealed-cold-tier.md`](./ADR-sealed-cold-tier.md)
> (encrypt-at-rest + custody), [`ADR-anchoring-offchain-relayer.md`](./ADR-anchoring-offchain-relayer.md)
> (the build-here / submit-elsewhere boundary for anchoring & slashing).

## 1. System under review

Two artifacts:

| Artifact | What it is | Repo |
|---|---|---|
| **kotoba** | Rust + WASM core: content-addressed Datomic-style graph DB, CACAO authz, IPFS cold tier, custody, XRPC/MCP server | `etzhayyim/kotoba` |
| **net-kotobase** (kotobase.net) | Cloudflare Worker BFF / edge in front of the kotoba origin | `gftdcojp/net-kotobase` |

Typical enterprise SaaS topology being assessed:

```
  end user / app
       │  HTTPS
       ▼
  ┌─────────────────────┐   Cloudflare Worker (net-kotobase)
  │ kotobase.net (CF)    │   · TLS termination, OIDC/IdP (operator-built)
  │  - OIDC verify       │   · mints edge JWT `sub`, sets x-internal-trust
  │  - CORS, WAF, RL     │   · CORS / WAF / rate-limit at the edge
  └─────────┬───────────┘
            │  Cloudflared tunnel (TLS 1.3)
            ▼
  ┌─────────────────────┐   kotoba origin (in-cluster)
  │ kotoba serve :8080   │   · CACAO verify (real crypto)
  │  - graph_auth gate   │   · access receipts (audit)
  │  - rate_limit (opt)  │   · sealed cold tier (opt) → Kubo/IPFS
  └─────────┬───────────┘
            ▼
        Kubo / IPFS  ── only ciphertext if sealing ON; PLAINTEXT if OFF
```

## 2. Trust boundaries

| # | Boundary | Who is trusted | Enforcement | Source |
|---|---|---|---|---|
| TB1 | Internet → CF Worker | nobody | TLS, edge WAF/RL (operator) | net-kotobase |
| TB2 | CF Worker → origin | the Worker (shared secret) | `x-internal-trust` constant-time compare; raw LB IP blocked (CF error 1003) | `graph_auth.rs` `require_internal_trust`; `deploy/cloudflared-kotobase.yaml` |
| TB3 | Caller → graph data | the CACAO signer | Ed25519/secp256k1 signature, capability, graph scope, replay nonce | `kotoba-auth` `delegation.rs`; `nonce_store.rs` |
| TB4 | Node → IPFS network | nobody (public) | **sealing (opt-in)** — only ciphertext leaves when `KOTOBA_BLOCK_KEY*` set | `kotoba-store` `sealed_store.rs` |
| TB5 | Operator → key material | the key custodians | self-custody key, optional Shamir t-of-N split | `kotoba-custody`; `kotoba-cli` `key` |

Critical reviewer note: **the edge JWT `sub` signature is NOT verified at the
origin** — the Worker is the signature trust boundary (`graph_auth.rs:98-100`).
Any IdP/OIDC assurance lives in the Worker the operator builds. CACAO (TB3) is
the only path whose signature the origin verifies itself.

## 3. Cryptographic inventory

| Use | Primitive | Implementation | Source |
|---|---|---|---|
| AEAD at rest | AES-256-GCM | `aes_gcm` (RustCrypto) | `kotoba-crypto/src/aead.rs` |
| KDF | HKDF-SHA256 | `hkdf` (RustCrypto) | `kotoba-crypto/src/hkdf.rs` |
| Signatures | Ed25519 | `ed25519-dalek` | `kotoba-auth`, `kotoba-vault` |
| Key agreement / HPKE | X25519 | `x25519-dalek` | `kotoba-vault`, `kotoba-custody` |
| Hashing | SHA-256 / SHA-3 / RIPEMD-160 / BLAKE3 | RustCrypto + `blake3` | throughout |
| EVM recover | secp256k1 / keccak | `sha3`, recover | `kotoba-auth/src/eth*` |
| Secret sharing | Shamir GF(2⁸) | `sharks` | `kotoba-custody/src/shares.rs` |

**Hand-rolled (encoding/checksum only, no bespoke crypto):** Base58Check,
bech32/bech32m, EIP-55 checksum, legacy Bitcoin signed-message digest
(`kotoba-auth/src/btc/*`, `eth.rs`). `kotoba-crypto` is `#![deny(unsafe_code)]`;
no `unsafe` in auth/crypto/custody.

**Nonce safety (GCM):** default path uses random nonces (`OsRng`). The
content-addressed `SealedBlockStore` uses a deterministic nonce
`HKDF(block_key, sha2-256(plaintext))` — because `cid = sha2-256(plaintext)`, a
repeated `(key, nonce)` implies identical plaintext, so catastrophic GCM nonce
reuse across distinct plaintexts cannot occur (`sealed_store.rs:22-28`).

**Audit asks (recommended):** dependency SBOM + `cargo audit` in CI; fuzz
bech32/Base58 decoders; confirm `test-utils` feature (which exposes
`verify_skip_sig`) is never enabled in release builds.

## 4. Authentication & authorization

- **CACAO delegation (primary, origin-verified):** signature is mandatory on the
  production path (`delegation.rs verify`/`verify_with_resolver`). Enforces
  temporal validity (expiry, or 7-day max-age cap), capability match, graph
  scope, depth-2 attenuation (no capability/scope escalation; depth ≥3 rejected),
  and replay protection via a sharded nonce store (`nonce_store.rs`).
  `verify_skip_sig` exists **only** under the `test-utils`/`test` feature gate.
- **Visibility tiers** (`graph_auth.rs`): `public` / `authenticated` (Bearer) /
  `private` (CACAO `datom:read`). Default `KOTOBA_DEFAULT_VISIBILITY=private`.
- **Direct-access gate (S1):** `require_internal_trust` (constant-time compare on
  `KOTOBA_INTERNAL_SECRET`) blocks pod-direct JWT forgery on write paths.
- **Multi-tenant:** `kotobase/{accounts,pins}/{tenant_did}` namespace + CACAO
  `graph_scope = "private/{owner_did}"` (`kotobase_xrpc.rs`, `graph_auth.rs`).
  Isolation correctness depends on every endpoint enforcing scope — see RR-7.

**Not provided (operator builds on top):** OAuth2 / OIDC / SAML SSO, SCIM
provisioning, RBAC admin UI, group ACLs, break-glass. The Gmail OAuth in
`kotoba-ingest` is email ingestion only, not end-user login.

## 5. Data-at-rest & IPFS exposure model

**This is the highest-impact finding for a SaaS deployment.**

- `SealedBlockStore` (AES-256-GCM envelope) is **disabled by default**:
  `SealedKeyConfig::from_env` returns `None` when no key is configured, and the
  server logs `cold tier UNSEALED — blocks replicate beyond this node in
  PLAINTEXT` and proceeds (`sealed_store.rs:59-71`, `server.rs` ~499-506).
- With sealing OFF, blocks written to Kubo/IPFS are plaintext; CIDs flow through
  commit/firehose, so content is **not** secret.
- Even with sealing ON, two seams still move plaintext (documented follow-ups):
  the **CAR-on-B2 export queue** and the **`KOTOBA_DURABILITY_DHT`
  NeighborhoodBlockStore** peer replication (`sealed_store.rs:40-42`).

**Mandatory for customer data:** set `KOTOBA_BLOCK_KEY` / `_FILE` / `_CMD`;
disable CAR export and DHT durability until sealed; run Kubo as a private swarm
(no public gateway pin).

## 6. Key management & recovery

- Key sources (`sealed_store.rs SealedKeyConfig::from_env`, precedence):
  `KOTOBA_BLOCK_KEY` (inline hex) → `KOTOBA_BLOCK_KEY_FILE` (file) →
  **`KOTOBA_BLOCK_KEY_CMD`** (vendor-neutral KMS/HSM/Vault hook — runs a command
  whose stdout is the hex key; a non-zero exit or empty output is a hard error,
  never a silent fallback to plaintext).
- Agent identity (`kotoba-vault/agent_identity.rs`): Keychain/dotfile → env hex →
  ephemeral. Vault key wrapped to the agent X25519 key (`sovereign_key.rs`), with
  versioned rotation + old-key retention.
- **Recovery:** Shamir t-of-N custody (R3a) is implemented with CLI
  (`kotoba key gen-key|deal|combine`, `kotoba-cli/main.rs`). There is **no KMS
  escrow and no "forgot key" path** — if the block key is lost and was never
  dealt to custodians, sealed data is unrecoverable. **Deal the key before
  go-live** (or back the key with `KOTOBA_BLOCK_KEY_CMD` → managed KMS).
- Deferred: custodian network release protocol with receipts (R3b), Feldman VSS
  for cheating-dealer detection (R3c) — see SECURITY-ARCHITECTURE §"deferred".

## 7. Audit & accountability

- **Access receipts (R1):** every authorized non-public read / key release emits
  a who/which/what/why/when datom into `kotoba/audit/access-receipts/v1`
  (`access_receipt.rs`); `x-kotoba-purpose` header, `KOTOBA_REQUIRE_PURPOSE` to
  enforce; client IP (`CF-Connecting-IP`) / UA / request-id captured;
  `audit.listReceipts` (operator-gated).
- **Tamper-evidence:** author-signed CommitDag (Ed25519) is the canonical chain;
  `audit.verifyChain` walks it. The Base **anchoring** that would make operator
  rewrite externally detectable is built here but submitted by an **off-chain
  relayer** — the on-chain enforcement is not productionized. See
  [`ADR-anchoring-offchain-relayer.md`](./ADR-anchoring-offchain-relayer.md) for
  the residual risk and the contractual language to use until then.

## 8. Risk register

Severity is residual (after the mitigations in §9 are applied at deploy time).

| ID | Risk | Likelihood | Impact | Mitigation | Residual |
|---|---|---|---|---|---|
| RR-1 | Sealing off by default → plaintext on IPFS | High if unconfigured | Critical | Set `KOTOBA_BLOCK_KEY*`; private swarm | Low |
| RR-2 | Plaintext via CAR export / DHT replication even when sealed | Medium | High | Disable CAR/DHT durability until sealed | Low–Med |
| RR-3 | Block-key loss → unrecoverable data | Medium | Critical | Shamir deal pre-go-live, or KMS via `_CMD` | Low |
| RR-4 | Edge JWT `sub` unverified at origin | Medium | High | Harden Worker OIDC; keep `KOTOBA_INTERNAL_SECRET` | Med |
| RR-5 | No native SSO/SCIM/RBAC | High (gap) | Med | Operator builds IAM on CACAO + BFF | Med |
| RR-6 | DoS / amplification (no RL at origin) | Medium | Med | `KOTOBA_RATE_LIMIT_RPS`; edge RL/WAF; firehose backfill cap | Low |
| RR-7 | Tenant-scope regression on a new endpoint | Low–Med | High | Scope-enforcement regression tests | Low |
| RR-8 | Tamper-evidence depends on off-chain relayer | Low | Med | Productionize anchoring or document SLA | Med |
| RR-9 | Cheating dealer in custody (no VSS yet) | Low | Med | Trusted-dealer assumption; R3c follow-up | Med |
| RR-10 | No third-party audit / pen-test yet | — | — | This package + engagement | — |

## 9. SaaS deployment prerequisites (go-live checklist)

Mandatory (do not expose customer data without these):

- [ ] `KOTOBA_BLOCK_KEY` / `_FILE` / `_CMD` set (sealing ON). [RR-1]
- [ ] CAR-on-B2 export and `KOTOBA_DURABILITY_DHT` disabled until sealed. [RR-2]
- [ ] Kubo private swarm; no public gateway pinning. [RR-1]
- [ ] Block key dealt to Shamir custodians **or** backed by managed KMS via
      `KOTOBA_BLOCK_KEY_CMD`. [RR-3]
- [ ] `KOTOBA_DEFAULT_VISIBILITY=private` (default) confirmed. [TB3]
- [ ] `KOTOBA_INTERNAL_SECRET` set; raw origin IP not routable. [TB2/RR-4]
- [ ] Worker performs real OIDC/IdP token verification before minting `sub`. [RR-4]
- [ ] `KOTOBA_RATE_LIMIT_RPS` set at origin; WAF/RL at the edge. [RR-6]
- [ ] `KOTOBA_REQUIRE_PURPOSE=1` if purpose-binding is a compliance requirement. [§7]

Edge-owned (configure at Cloudflare / ingress, not the origin): request timeout,
idle/connection timeout, body-size ceiling at the edge, TLS policy. The origin
additionally caps SSE connection lifetime via `KOTOBA_SSE_MAX_SECS` and firehose
backfill span via `KOTOBA_MAX_FIREHOSE_BACKFILL`.

Recommended before "enterprise-ready" claim:

- [ ] Third-party code audit + pen-test (this package is the entry point). [RR-10]
- [ ] `cargo audit` + SBOM in CI; fuzz Base58/bech32. [§3]
- [ ] Anchoring on-chain productionized, or "off-chain relayer" assumption in the
      customer security addendum. [RR-8]
- [ ] Tenant-scope enforcement regression suite. [RR-7]

## 10. Verification evidence

- Crypto/custody/auth audit + edge audit: this branch's review (2026-06-22).
- Tests: `cargo test -p kotoba-server` (incl. `rate_limit::*`, firehose),
  `cargo test -p kotoba-store --lib sealed` (incl. `key_cmd_*`),
  `cargo test -p kotoba-auth` (CACAO depth-2, real EdDSA), `cargo test -p kotoba-custody`.
- Live-verified accountability flow R1–R3d: see SECURITY-ARCHITECTURE §"Live-verified flow".

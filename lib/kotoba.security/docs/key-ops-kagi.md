# Key Operations via kagi

Status: operational runbook  
Date: 2026-07-18

## Purpose

Production private keys for the Kotoba fleet live in **kagi** (OS-Keychain
unlock, compartment `personal`). This repository may record **public** key
material and custody metadata only. Private PEMs must never be committed.

## Inventory (probed 2026-07-18)

| kagi item | Present | Public form recorded in key-register |
|---|---|---|
| `fleet-owner-key` | yes (private in vault) | `ed25519:7414dd47…` (`fleet-owner-key-2026-07-16`) |
| `fleet-owner-root` | yes | `did:key:z6Mkk13t…` |
| `fleet-gov1` | yes | `did:key:z6MkqmFd…` |
| `fleet-gov2` | yes | `did:key:z6MkqZim…` |
| `security-package-signing` | yes (retired public row) | `ed25519:1f414dff…` (`security-package-signing-2026-07-18`, **:retired**, verify-until 2033-07-18) |
| `security-package-signing-2026-07-18-rot` | **yes** (minted + active 2026-07-18 rotation) | `ed25519:a8cfa6c1…` + `did:key:z6MkqpEBn…` (`security-package-signing-2026-07-18-rot`) |
| `security-audit-signing` | **yes** (minted 2026-07-18) | `ed25519:d4c230fa…` + `did:key:z6MktmnDn…` (`security-audit-signing-2026-07-18`) |

Public fleet material is also the superproject SSOT
`manifest/fleet-keys.edn` (no private fields).

## CLI location

```sh
export FLEET_ROOT=/path/to/com-junkawasaki   # superproject root
KAGI="$FLEET_ROOT/orgs/kotoba-lang/kagi/bin/kagi"
```

kagi is not always on `PATH`; use the repo binary above (same path fleet CLI
uses for `--kagi`). Vault data lives under `orgs/kotoba-lang/kagi/.kagi/`
(the `bin/kagi` wrapper `cd`s into the kagi repo before launching Clojure).

## Safe operations

```sh
# List items (names only; no secret material)
"$KAGI" ls

# Fetch private material only into a signing tool stdin — never into git
# or chat. Prefer fleet --kagi rather than printing PEM:
FLEET_ROOT=$FLEET_ROOT kbb --backend sci --classpath orgs/kotoba-lang/kagami/src \
  orgs/kotoba-lang/kagami/bin/fleet.cljs pin-advance \
  --db manifest/fleet-db.edn --repo security --new <sha> \
  --kagi fleet-owner-key

# kagi has no --public export flag (2026-07-18). Public forms are:
#   1) recorded at mint time (ed25519 hex + did:key) into key-register
#   2) re-derived offline: kagi get <name> | node (createPublicKey → SPKI tail)
# Never paste PEM private blocks into registers or evidence.
```

## Mint commands used (2026-07-18 package + audit)

Offline Ed25519 PKCS8 generation (Node `crypto.generateKeyPairSync`), then
stdin into kagi. Private PEM stayed in `/tmp` only long enough to pipe and was
unlinked; never committed.

```sh
export FLEET_ROOT=/path/to/com-junkawasaki
KAGI="$FLEET_ROOT/orgs/kotoba-lang/kagi/bin/kagi"

# 1) generate PKCS8 PEM to a mode-0600 temp file (example for package)
node -e 'const c=require("crypto");const k=c.generateKeyPairSync("ed25519",{privateKeyEncoding:{format:"pem",type:"pkcs8"},publicKeyEncoding:{format:"der",type:"spki"}});process.stdout.write(k.privateKey);' \
  > /tmp/security-package-signing.pem
chmod 600 /tmp/security-package-signing.pem

# 2) store private material only in kagi (compartment personal)
cat /tmp/security-package-signing.pem | "$KAGI" add security-package-signing -c personal
# same pattern for security-audit-signing

# 3) derive PUBLIC only (never commit PEM)
# node: createPublicKey(createPrivateKey(pem)).export({format:"der",type:"spki"})
# take last 32 bytes as hex → ed25519:<hex>
# did:key = multibase base58btc of (0xed 0x01 || raw32)  → did:key:z6Mk...
# (same encoding as orgs/kotoba-lang/kagami/src/fleet/did.cljc)

# 4) shred temp PEM
rm -f /tmp/security-package-signing.pem /tmp/security-audit-signing.pem
```

Register rows after mint:

- `:key/id` `security-package-signing-2026-07-18` / `security-audit-signing-2026-07-18`
- `:key/status :active`, `:key/storage :kagi`, `:key/intent :production`
- `:key/kagi-name` matching the kagi item
- `:key/public` and `:key/did` only (no private fields)

Residual until HSM: custody is kagi + OS-Keychain unlock, not a FIPS HSM module.

## Register a new production public key

1. Generate/custody the private key in kagi only (`kagi add <name>`).
2. Record **public** hex / `did:key` in `registers/key-register.edn` with:
   - `:key/status :active` (or `:pre-active` until first use)
   - `:key/storage :kagi`
   - `:key/kagi-name "<name>"`
   - `:key/kagi-compartment "personal"`
   - `:key/intent :production`
   - `:key/public` and/or `:key/did`
3. Run key-register gates:
   ```sh
   kbb --backend sci --classpath src scripts/check-key-register.cljk --require-active
   bb scripts/check-key-register.bb   # shape + no private PEM (key_lifecycle)
   ```
4. Refresh `evidence/<date>/key-status-snapshot.edn` and evidence-index.
5. Never commit private material; CI/key-register gate rejects PEM blocks.

## Dry-run validation

```sh
kbb --backend sci --classpath src scripts/check-key-register.cljk --require-active
bb scripts/check-key-register.bb
kbb -M:test -n kotoba.security.key-lifecycle-test
```

Expected shape invariants are enforced by
`src/kotoba/security/key_lifecycle.cljk` and
`src/kotoba/security/key_status.cljk`.

## One-time identity migration

If `kagi get` fails with `plaintext identity requires migration`, run
`kagi identity-migrate` once to move the identity into the OS Keychain. After
migration, the public key for `fleet-owner-key` matches the `7414dd47…` entry in
`manifest/fleet-keys.edn`, and signing the fleet head succeeds. Never print or
record the private key while checking this.

## Rotation (2026-07-18 package-signing)

Planned rotation (not incident):

1. Mint new private material → kagi item `security-package-signing-2026-07-18-rot`.
2. Register public only; promote new to `:active`.
3. Retire old `security-package-signing-2026-07-18` with `:key/verify-until "2033-07-18"`.
4. Pure drill: `kbb --backend sci --classpath src scripts/check-key-rotation-drill.cljk --write`.
5. `kbb --backend sci --classpath src scripts/check-key-register.cljk --require-active`.

Evidence: EV-0014, `evidence/2026-07-18/key-lifecycle-rotation-drill.edn`.

## Residual (R-002)

- Package-signing and audit-signing **production-intent** keys are issued in
  kagi and registered with public material (2026-07-18).
- Package-signing **rotation** exercised (pure drill + live public register
  update + kagi mint of `-rot` key, 2026-07-18).
- Remaining residual: OS-Keychain kagi custody (not HSM); fleet pin/governance
  keys must not sign package manifests.

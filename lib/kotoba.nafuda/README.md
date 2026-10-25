# nafuda (名札)

**Identity for a phone system with no numbering authority.**

- **Root key, offline** — its device certificates say which phone, PC or home
  node may act for the person, in which roles (`:call :page :home :message`),
  for how long. Revocation by serial.
- **Root continuity** — succession signed by the old root, or recovery by a
  k-of-n guardian quorum; `current-root` follows both.
- **Seed backup** — the root seed split with `shamir` and each share
  encrypted to a guardian, with a commitment to detect a wrong combination.
- **Contact card** — root-signed card (name, device certs, home nodes) as a
  `nafuda:` QR string. In-person exchange is the strongest trust.
- **Community names** — a registry (village office, co-op) signs
  `tanaka@yamanaka` and a short number `#yamanaka/1000`; clients resolve only
  against registries they chose to trust. No global namespace.
- **E.164 bindings** — a licensed gateway can attest "this key holds +81…",
  for importing an ordinary phone book.
- **Petnames** — the user's own names win over everything.

Every credential is a signed statement: canonical EDN, Ed25519
(`nafuda.statement`).

```sh
npm test
```

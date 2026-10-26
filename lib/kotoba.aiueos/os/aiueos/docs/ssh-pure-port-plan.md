# SSH server → pure-Kotoba native graph: Gate-N2.5 port plan

- Status: planning (no code landed; this document is the deliverable)
- Date: 2026-09-04
- Branch: `ssh-port-plan-only`
- Scope: the SSH server component described by `os/aiueos/contracts/ssh-v1.edn`
  becomes pure-Kotoba objects on the x86_64-aiueos-kernel-v1 native graph, in
  dependency-ordered tranches, once Gate N2 (persistent TCP stream) lands.
- Docs convention note: ADRs live in `os/aiueos/90-docs/adr/`; this is a
  port-planning document, so it lives in `os/aiueos/docs/` and references ADRs
  rather than being one.

## 0. Ground rules this plan is bound by

1. **Authority chain (ADR-0106).** `kotoba-lang/org-ietf-ssh` (pure `.cljc`,
   605 lines across `ssh.transport`, `ssh.kex`, `ssh.keys`, `ssh.record`,
   `ssh.userauth`, `ssh.connection`) is the single source of truth for the SSH
   wire rules. Every new `.kotoba` object is a byte-for-byte port of named
   functions from those namespaces. The precedent is the C kernel's
   `aiueos_ssh_kex_h()` (`os/aiueos/kernel/main.c:386`), which mirrors
   `ssh.transport/h-transcript` and is proven equal to it by
   `os/aiueos/scripts/smoke-qemu-ssh-kex.cljk`.
2. **Q9 whole-component migration.** The unit of migration is the whole SSH
   component: after the last tranche, every SSH *decision* (admission, framing
   validity, transcript assembly, key derivation, digest comparison, authorize,
   command route) lives in a compiler-emitted `.kotoba` object. A scalar shadow
   or predicate fallback does not count. Acceptance is `kotoba check` **and**
   `amu check --jvm-free` over the object set; no JVM anywhere in acceptance.
   The C pump (`net_ssh_*` in `os/aiueos/kernel/pci.c`) remains as
   decision-free *mechanism* only (socket recv/send, ACK ordering, NVRAM key
   load, `aiueos_random_bytes`), per ADR-2607241100 D6.
3. **Object constraints.** Target `x86_64-aiueos-kernel-v1`, default fuel tier
   1,048,576. Kernel objects take up to 5 i64 args (pointers + lengths). The
   kernel-target compile emits a fixed 32768-byte image `.text` region; a
   source whose emitted code region exceeds it cannot ship through the default
   path — the measured precedent is `ecdsa-p256-sign.kotoba` (kernel object
   50864 bytes, ~52 KB region, `.o` file 52264 bytes / `.text` 51421 in this
   checkout), which needed the ADR-0105 recipe
   (`os/aiueos/scripts/reproduce-ecdsa-sign-object.cljk`: kernel-object entry +
   250,000,000 fuel tier + `package-kernel` stub, pending an upstream pin
   advance).
4. **Objects cannot call objects.** A Kotoba object is self-contained code
   (that is why `ecdsa-p256-sign.kotoba` carries a verbatim copy of
   `ecdsa-p256.kotoba`'s field/scalar helpers — the ADR-0030 copy pattern).
   Therefore every object below that needs SHA-256 or AES-128-GCM *inside its
   decision* carries a verbatim copy of the existing object's source, and the
   size estimates below are dominated by that copy.
5. **KIR cannot vector-test memory-using objects** (ssh-v1.edn
   `:crypto-bricks` note). Every object is measured by native compile + boot
   KAT; the host-side oracle is an nbb script that requires the org-ietf-ssh
   core.

## 1. Measured baseline (this checkout, 2026-09-04)

Existing pure-Kotoba objects (`os/aiueos/kotoba/`, `objdump -h` `.text` sizes;
file size is the whole relocatable `.o`):

| object | `.text` bytes | file bytes | on the SSH path |
|---|---:|---:|---|
| sha256.kotoba | 16,964 | 17,792 | yes — H, key derivation |
| x25519.kotoba | 20,867 | 21,696 | yes — Q_S, K (already in the 250M fuel set) |
| aes128-gcm.kotoba | 13,253 | 14,088 | yes — the GCM primitive |
| ecdsa-p256.kotoba (verify) | 48,219 | 49,072 | yes — host-key + userauth verify |
| ecdsa-p256-sign.kotoba | 51,421 | 52,264 | yes — KEX reply signature (50864 kernel object, 250M tier) |
| tls13-record.kotoba | 16,751 | 17,592 | no — TLS 1.3, shape precedent only |
| digest-equal.kotoba | — | 1,728 | yes — constant-time compare helper |
| hkdf-sha256.kotoba | — | 13,056 | **no** — SSH key derivation is the plain RFC 4253 §7.2 HASH loop, not HKDF; `ssh.keys` is the authority |

Reference point for the limit: 32,768 bytes (image `.text` region); the
ecdsa-p256-sign precedent exceeded it at 50,864. Everything this plan proposes
is estimated ≤ ~21,000 bytes of `.text`, i.e. under the limit with the same
kind of margin `sha256.kotoba` (16,964) already has — but each tranche
*measures* at compile time rather than trusting the estimate.

## 2. Layer-by-layer mapping

For each ssh-v1.edn `:transport` layer: the existing pure-Kotoba object that
covers it, the org-ietf-ssh namespace/function that is the byte-for-byte
authority, what is MISSING, and the measured-size/fuel risk.

### 2.1 Binary packet framing (RFC 4253 §6)

- **Covered today:** nothing on the Kotoba side; the C pump's `ssh_unwrap` /
  `ssh_seal` in `os/aiueos/kernel/pci.c` do the admission.
- **Authority:** `ssh.transport` — `u32`, `string-bytes`, `name-list`,
  `mpint`, `pad-length`, `packet`, `packet-payload`
  (`org-ietf-ssh/src/ssh/transport.cljc:60-119`).
- **MISSING:** `ssh-packet.kotoba` — pre-NEWKEYS framing admission
  (length/padding validation, payload extraction) and payload framing. Pure
  byte mechanism on buffers the C pump passes in.
- **Size/fuel risk: LOW.** No crypto inside; work is linear in packet length.
  Estimated `.text` ≈ 2–4 KB (digest-equal-sized scale), fuel ≪ default tier.
  Largest hazard is bounds arithmetic (the `packet-payload` nil cases), which
  the KAT pins.

### 2.2 KEXINIT (RFC 4253 §7.1)

- **Covered today:** C builds it inline in `pci.c`; the name-list profile is
  baked.
- **Authority:** `ssh.transport` — `profile`, `kexinit-payload`
  (`transport.cljc:33-46, 121-141`).
- **MISSING:** `ssh-kexinit.kotoba` — assembles the payload from a supplied
  16-byte cookie. Cookie *generation* stays C mechanism (`aiueos_random_bytes`,
  ADR-0103); the object does the deterministic assembly.
- **Size/fuel risk: LOW.** Fixed name-list strings; ≈ 2–3 KB `.text`.

### 2.3 curve25519-sha256 kex (Q_S, K, KEX_ECDH_REPLY)

- **Covered today:** `x25519.kotoba` computes the scalar multiplications
  (`.text` 20,867; already in the 250M fuel set with x25519's own entry —
  `reproduce-ecdsa-sign-object.clj:40-52`); `ecdsa-p256-sign.kotoba` signs H.
  What is missing is the *reply assembly*.
- **Authority:** `ssh.kex` — `ec-point`, `host-key-blob`,
  `signature-blob`, `kex-ecdh-reply-payload`, `ecdsa-digest` (the
  SHA-256(H)-as-ECDSA-digest rule), `newkeys-payload`
  (`org-ietf-ssh/src/ssh/kex.cljc:26-77`).
- **MISSING:** `ssh-kex-reply.kotoba` — K_S blob, signature blob, the
  SSH_MSG_KEX_ECDH_REPLY payload, and the NEWKEYS payload byte. Takes (K_S
  point, Q_S, r, s) buffers; the ephemeral scalar and the `(r,s)` still come
  from the existing objects via C glue.
- **Size/fuel risk: LOW.** Assembly only ≈ 3–5 KB `.text`. The heavy objects it
  depends on are already landed and measured; the fuel story does not change
  (250M tier stays where it is — inside x25519/ecdsa calls made from C).

### 2.4 Exchange hash H (RFC 5656 §4 / RFC 8731)

- **Covered today:** the *hash* is `sha256.kotoba` (linked; ssh-v1.edn
  `:exchange-hash :hash :kernel-sha256-object`); the *transcript assembly* is
  C (`aiueos_ssh_kex_h`, `main.c:386-411`) mirroring
  `ssh.transport/h-transcript` (ADR-0106).
- **Authority:** `ssh.transport` — `h-transcript`, `exchange-hash`
  (`transport.cljc:143-169`).
- **MISSING:** `ssh-kex-hash.kotoba` — the byte-for-byte port of
  `h-transcript` + inline SHA-256 (verbatim copy of `sha256.kotoba`'s source,
  ADR-0030 pattern, because objects cannot call objects). Inputs: (V_C, V_S,
  I_C, I_S, K_S, Q_C, Q_S, K) as pointer+length pairs; output: 32-byte H.
  This is the object ADR-0106 already names as the long-term home
  (`transport.cljc:17-19`: "compiles `ssh/exchange_hash.kotoba`"; this plan
  fixes the concrete name `ssh-kex-hash.kotoba`).
- **Size/fuel risk: MEDIUM — the headline measurement of this plan.** Estimated
  `.text` ≈ 19–21 KB (16,964 for the SHA-256 copy + ~1–2 KB transcript
  assembly) — **under** the 32768 limit, ~12 KB of headroom, but it is the
  largest new object in the plan and the estimate must be measured at compile,
  not assumed. Fuel: one SHA-256 compression over a 173-byte transcript is
  the same order as `sha256.kotoba`'s existing boot work (default tier
  suffices); verify the compiler-reported fuel ≤ 1,048,576. If the composite
  overshoots 32768, the fallback is the ADR-0105 recipe (kernel-object entry +
  fuel tier + `package-kernel` stub) — recorded here so nobody improvises it.
- **Oracle already exists:** `os/aiueos/scripts/ssh-kex-kat.cljk` (landed with
  this plan) computes H = `520a9ba70d60201af9365b0e53ffafa1a31446d17ec24315eb678a9b2e709833`
  and transcript length 173 from the org-ietf-ssh core for the exact fixed
  inputs the C KAT bakes (`main.c:390-398`) — the pure port gets the same
  oracle the C path had.

### 2.5 NEWKEYS (RFC 4253 §7.3)

- **Covered today:** C emits the one-byte payload.
- **Authority:** `ssh.kex` — `newkeys-payload` (`kex.cljc:68-71`).
- **MISSING:** nothing as a separate object. The payload is `[21]`; its
  emission is part of `ssh-kex-reply.kotoba` (T3) and the post-NEWKEYS state
  transition belongs to the record layer object's caller. Asserted by gates,
  not a new object.

### 2.6 aes128-gcm@openssh.com record layer (RFC 5647 + OpenSSH variant)

- **Covered today:** the GCM primitive is `aes128-gcm.kotoba` (`.text` 13,253)
  called from C; the nonce counter, AAD rule, padding rule and framing are C
  (`ssh_seal`/`ssh_open` in `pci.c`).
- **Authority:** `ssh.record` — `pad-len`, `nonce` (byte-wise 64-bit counter),
  `seal`, `open` (`org-ietf-ssh/src/ssh/record.cljc:27-83`).
- **MISSING:** `ssh-record.kotoba` — the whole per-packet decision: framing,
  AAD selection (length field in clear), nonce construction, padding, and the
  GCM call. Because objects cannot call objects, this object carries a
  verbatim copy of `aes128-gcm.kotoba`'s source.
- **Size/fuel risk: MEDIUM.** Estimated `.text` ≈ 16–19 KB (13,253 GCM copy +
  ~2–3 KB framing) — under 32768, similar margin to `tls13-record.kotoba`
  (16,751). Fuel is data-length-linear (AES over up to a 32 KB packet); the
  existing object already serves the landed record layer, but the composite
  must have its compiler-reported fuel checked against the default tier, and
  the ADR-0105 tier path exists if it is not. Drift risk between the copied
  GCM and `aes128-gcm.kotoba` is mitigated by the KAT asserting byte-identical
  seal output and by the copy being verbatim (source-sha256 pinned in
  provenance.edn).

### 2.7 Session-key derivation (RFC 4253 §7.2) — implied by the record layer

- **Covered today:** `sha256.kotoba` does the hashing; the `mpint(K) || H ||
  letter || session_id` assembly is C (`net_ssh_userauth`,
  `pci.c:2594-2608`).
- **Authority:** `ssh.keys` — `derive`, `session-keys`
  (`org-ietf-ssh/src/ssh/keys.cljc:22-42`).
- **MISSING:** `ssh-session-keys.kotoba` — four derivations
  (IV/key, c→s and s→c) from (K, H). Verbatim SHA-256 copy again (objects
  cannot call objects); the tradeoff — two objects each carrying an SHA-256
  copy, ~40 KB of kernel image total — is accepted for tranche independence
  and recorded here.
- **Size/fuel risk: LOW-MEDIUM.** Same SHA-256-dominated estimate as 2.4
  (~20 KB); four compressions over 74-byte inputs, default fuel tier. Note
  explicitly: this is **not** `hkdf-sha256.kotoba` — `ssh.keys` is the plain
  HASH loop.

### 2.8 publickey userauth (RFC 4252 §7)

- **Covered today:** `ecdsa-p256.kotoba` (verify, `.text` 48,219) verifies;
  `digest-equal.kotoba` compares; the signed-data reconstruction and the
  authorize decision are C.
- **Authority:** `ssh.userauth` — `pubkey-blob`, `signed-data`,
  `parse-userauth-request`, `userauth-success-payload`,
  `userauth-failure-payload` (`org-ietf-ssh/src/ssh/userauth.cljc:39-110`).
- **MISSING:** `ssh-userauth-check.kotoba` — parse the USERAUTH_REQUEST,
  reconstruct the `signed-data` blob exactly, match the offered key against
  the provisioned authorized key (`digest-equal`-style comparison is inside
  this object's decision), and return the digest/flag C feeds to the existing
  verify object. Refusal reasons (`:wrong-key :wrong-user :bad-signature
  :unbound-hostkey`) are this object's outputs.
- **Size/fuel risk: LOW.** ≈ 4–6 KB `.text`; no crypto inside (verify stays in
  the existing object called from C). The existing verify object is over the
  32768 region today (48,219) — it already ships, so nothing new opens there.

### 2.9 session/exec channel + the three commands (RFC 4254)

- **Covered today:** `ecdsa`-free C in `pci.c:2795-2891` parses
  CHANNEL_OPEN/REQUEST and builds the reply sequence; command dispatch is
  `aiueos_kototama_runtime_management_command`
  (`os/aiueos/kernel/kototama_runtime.c:172-196`).
- **Authority:** `ssh.connection` — `parse-channel-open`,
  `parse-channel-request`, `parse-channel-data`,
  `channel-open-confirmation-payload`, `channel-success-payload`,
  `channel-data-payload`, `channel-exit-status-payload`,
  `channel-eof-payload`, `channel-close-payload`
  (`org-ietf-ssh/src/ssh/connection.cljc:30-124`).
- **MISSING (two objects, split by decision type):**
  - `ssh-session-route.kotoba` — channel message parse/admit + reply payload
    assembly (confirmation, success, data, exit-status, eof, close).
  - `ssh-command-route.kotoba` — the bounded command decision: exact match of
    `runtime status` / `runtime restart` / `system reboot-pxe`, the response
    text build, unknown-command refusal. Side effects (runtime restart,
    UEFI cold reset) remain C mechanism calls the object's verdict routes to.
- **Size/fuel risk: LOW.** ≈ 4–6 KB each; linear in message length.

## 3. Missing-object summary

Nine new `.kotoba` objects (all new code; none replaces an existing object),
grouped into eight tranches T1–T8 (T8 carries the last two):

| # | object | ports | est. `.text` |
|---|---|---|---:|
| 1 | ssh-packet.kotoba | ssh.transport framing fns | 2–4 KB |
| 2 | ssh-kexinit.kotoba | ssh.transport/kexinit-payload | 2–3 KB |
| 3 | ssh-kex-hash.kotoba | ssh.transport/h-transcript + sha256 copy | 19–21 KB |
| 4 | ssh-kex-reply.kotoba | ssh.kex reply/blob fns | 3–5 KB |
| 5 | ssh-session-keys.kotoba | ssh.keys/derive + sha256 copy | ~20 KB |
| 6 | ssh-record.kotoba | ssh.record + aes128-gcm copy | 16–19 KB |
| 7 | ssh-userauth-check.kotoba | ssh.userauth | 4–6 KB |
| 8 | ssh-session-route.kotoba | ssh.connection | 4–6 KB |
| 9 | ssh-command-route.kotoba | kototama command texts (the three commands) | 4–6 KB |

Existing objects reused as-is (no new object, no recompile):
`sha256.kotoba`, `x25519.kotoba`, `aes128-gcm.kotoba` (primitive; also copied
verbatim into #6), `ecdsa-p256.kotoba`, `ecdsa-p256-sign.kotoba`,
`digest-equal.kotoba`.

## 4. Tranches, dependency-ordered

Nine objects land as eight tranches T1–T8, ordered so no tranche waits on a
later one: framing first (leaf), then H, then the reply that signs H, then the
key derivation the record layer consumes, then the record layer itself, then
the two decisions above it, and finally the command route with the
whole-component closure.

Common gate definitions:
- **compile gate** = `kotoba check` + `amu check --jvm-free` clean; amu compiles
  the object for `x86_64-aiueos-kernel-v1`; compiler-reported fuel within the
  required tier (default 1,048,576 unless the tranche says otherwise); emitted
  code region ≤ 32,768 bytes (measure, don't assume); object + provenance row
  land in `os/aiueos/kotoba/` via `reproduce-kotoba-kernel-object.sh`.
- **QEMU gate** = boot in QEMU (`smoke-qemu-uefi.sh` under
  `AIUEOS_SSH_LISTEN=1 AIUEOS_TEST_NET=1`) with the object linked; the named
  serial marker is emitted and the named nbb gate passes.
- **physical gate** = same artifact PXE-boots on the K16 (RTL8125) and the
  marker/behavior is observed from outside the installer per ssh-v1.edn
  `:reachability`.

**T1 — ssh-packet.kotoba (framing leaf)**
- Inputs: none (leaf; only `ssh.transport` source to port).
- Host KAT: the org-ietf-ssh `transport_test.cljs` fixture vectors (hand-computed
  framing bytes; RFC 4253 §6 has no official vectors) — same vectors become the
  object's baked KAT.
- Compile gate: common; region ≤ 32768 (est. 2–4 KB).
- QEMU gate: new marker `AIUEOS_SSH_PKT_OK` — frame→admit→reframe round-trip
  against baked bytes.
- Physical gate: K16 boot emits `AIUEOS_SSH_PKT_OK`; OpenSSH interop unchanged.
- Existing test asserting the source of truth:
  `org-ietf-ssh/test/ssh/transport_test.cljs`.

**T2 — ssh-kex-hash.kotoba (H)**
- Depends: T1 (shared encodings), sha256.kotoba source.
- Host KAT: **the** KAT — `os/aiueos/scripts/ssh-kex-kat.cljk` (landed with
  this plan) pins H = `520a9ba70d60201af9365b0e53ffafa1a31446d17ec24315eb678a9b2e709833`
  and transcript length 173 for the fixed inputs of `main.c:390-398` /
  ssh-v1.edn `:kat-h`. The object's boot KAT must hit the same values.
- Compile gate: common; fuel ≤ 1,048,576 (SHA-256-dominated); region ≤ 32768
  (est. 19–21 KB; ADR-0105 recipe is the recorded fallback if exceeded).
- QEMU gate: the existing `AIUEOS_SSH_KEX_H <hex>` marker emitted by the
  object; `os/aiueos/scripts/smoke-qemu-ssh-kex.cljk` passes unchanged (same
  want[], new producer).
- Physical gate: K16 PXE reboot emits the same H (extends the landed
  `:exchange-hash :landed` evidence to the pure object).
- Existing tests: `org-ietf-ssh/test/ssh/transport_test.cljs`,
  `os/aiueos/scripts/smoke-qemu-ssh-kex.cljk`, plus the new
  `scripts/ssh-kex-kat.cljs`.

**T3 — ssh-kex-reply.kotoba (K_S blob, signature blob, reply+NEWKEYS)**
- Depends: T2 (H feeds `ecdsa-digest`), existing x25519/ecdsa-sign objects.
- Host KAT: fixture — fixed host key (RFC 6979 A.2.5 `d`) + fixed Q_C; expected
  K_S/sig-blob/reply bytes from `org-ietf-ssh/test/ssh/kex_test.cljs` (Node
  crypto oracle on both sides).
- Compile gate: common (est. 3–5 KB; no new fuel tier — the 250M tier lives in
  the existing x25519/sign objects called from C).
- QEMU gate: `AIUEOS_SSH_KEX_REPLY_OK` preserved;
  `os/aiueos/scripts/smoke-qemu-ssh-real.cljk` passes — Node independently
  verifies the signature over H against the pinned host key.
- Physical gate: external client completes the handshake after PXE boot
  (extends the landed ADR-0107 evidence).
- Existing tests: `org-ietf-ssh/test/ssh/kex_test.cljs`,
  `os/aiueos/scripts/smoke-qemu-ssh-real.cljk`.

**T4 — ssh-session-keys.kotoba (RFC 4253 §7.2 ×4)**
- Depends: T2 (K, H).
- Host KAT: fixture — `org-ietf-ssh/test/ssh/session_test.cljs` fixed inputs;
  expected IV/key bytes from `ssh.keys/session-keys` (RFC 4253 §7.2 has no
  published vectors; parity with the core is the oracle).
- Compile gate: common (est. ~20 KB with the verbatim SHA-256 copy).
- QEMU gate: derived keys identical to the C path's — the encrypted login
  still completes; `AIUEOS_SSH_AUTH_OK` path unchanged.
- Physical gate: login works on the metal after reboot.
- Existing tests: `org-ietf-ssh/test/ssh/session_test.cljs`,
  `os/aiueos/scripts/smoke-qemu-ssh-auth.cljk`.

**T5 — ssh-record.kotoba (aes128-gcm@openssh.com seal/open)**
- Depends: T4 (keys), aes128-gcm.kotoba source (verbatim copy).
- Host KAT: NIST GCM vectors already covering the primitive + framing parity
  against `ssh.record/seal`/`open` with Node GCM
  (`session_test.cljs` fixtures); negative: tampered tag/length refuses (nil).
- Compile gate: common (est. 16–19 KB); fuel is data-length-linear — check the
  compiler report against the tier `aes128-gcm` effectively runs at today;
  ADR-0105 tier path if over.
- QEMU gate: full encrypted login + command session pass:
  `smoke-qemu-ssh-auth.cljs`, `smoke-qemu-ssh-session.cljs`.
- Physical gate: the unprivileged Mac transport (`k16-ssh-transport.py` via
  OpenSSH ProxyCommand) completes a session.
- Existing tests: `org-ietf-ssh/test/ssh/session_test.cljs`,
  `os/aiueos/scripts/smoke-qemu-ssh-auth.cljk`,
  `os/aiueos/scripts/smoke-qemu-ssh-session.cljk`.

**T6 — ssh-userauth-check.kotoba (publickey decision)**
- Depends: T5 (requests arrive decrypted), existing ecdsa-p256.kotoba.
- Host KAT: fixture — positive signed-data reconstruction from
  `session_test.cljs` vectors; negative vectors: wrong key, wrong user, bad
  signature, unbound host key → the four refusal reasons of ssh-v1.edn
  `:userauth :refuses`.
- Compile gate: common (est. 4–6 KB).
- QEMU gate: `AIUEOS_SSH_AUTH_OK` + wrong-key refused with reason (the QEMU
  half of the negative matrix).
- Physical gate: the **currently UNVERIFIED** physical negative checks in
  ssh-v1.edn `:blockers` (`:physical-negative-auth`) — wrong key and password
  refused on the metal. This tranche is where that gap closes.
- Existing tests: `org-ietf-ssh/test/ssh/session_test.cljs`,
  `os/aiueos/scripts/smoke-qemu-ssh-auth.cljk`.

**T7 — ssh-session-route.kotoba (channel open/exec/data plumbing)**
- Depends: T5, T6.
- Host KAT: `org-ietf-ssh/test/ssh/session_channel_test.cljs` fixtures (open,
  exec, data, exit-status, eof, close byte layouts).
- Compile gate: common (est. 4–6 KB).
- QEMU gate: `smoke-qemu-ssh-session.cljs` passes with the object producing
  the reply payloads.
- Physical gate: `runtime status` over the metal listener (extends the landed
  ADR-0109 evidence).
- Existing tests: `org-ietf-ssh/test/ssh/session_channel_test.cljs`,
  `os/aiueos/scripts/smoke-qemu-ssh-session.cljk`.

**T8 — ssh-command-route.kotoba (the three commands) + whole-component check**
- Depends: T7.
- Host KAT: fixture ported from `kototama_runtime.c:172-196` behavior — three
  accept vectors (`runtime status`, `runtime restart`, `system reboot-pxe`)
  with byte-identical response texts, plus unknown-command refusal (the
  `:unknown-command :refused` clause).
- Compile gate: common (est. 4–6 KB).
- QEMU gate: command outputs byte-identical through the session;
  `smoke-qemu-ssh-session.cljs` command assertions pass.
- Physical gate: `runtime status` and the `reboot-pxe` ack path on the metal
  (ack-before-reset, UEFI cold reset to PXE — unchanged behavior, new
  producer).
- Whole-component closure (Q9): after T8, no SSH decision remains in C —
  `kotoba check` and `amu check --jvm-free` run over the complete SSH object
  set; the C pump retains only recv/send/ACK/NVRAM/randomness mechanism.
- Existing tests: `org-ietf-ssh/test/ssh/session_channel_test.cljs`,
  `os/aiueos/scripts/smoke-qemu-ssh-session.cljk`, plus the physical
  `runtime status` evidence recorded in ssh-v1.edn `:openssh-interop`.

## 5. What this plan deliberately does NOT do

- No kernel source changes, no build, no QEMU run, no PXE-server touch, no
  merge — planning only, per the Gate-N2.5 scope.
- No rekey tranche (ssh-v1.edn `:rekey :not-in-r0`), no pty/interactive shell
  (breadth, not a missing layer), no ed25519/SHA-512 (rejected with measured
  cost in ssh-v1.edn `:crypto-bricks :rejected-ed25519-path`).
- No RFC 4253 §7.2 → HKDF confusion: `hkdf-sha256.kotoba` is a TLS-1.3 brick,
  not on the SSH path.

## 6. Verification runbook (this branch)

```
# host oracle for the H KAT (requires org-ietf-ssh on the nbb classpath)
ORG_IETF_SSH_SRC=<org-ietf-ssh checkout> \
  kbb --backend sci --classpath <org-ietf-ssh>/src os/aiueos/scripts/ssh-kex-kat.cljk
# expect: SSH_KEX_KAT_OK transcript-length got 173 want 173
#         SSH_KEX_KAT_OK kat-h got 520a9ba70d60201af9365b0e53ffafa1a31446d17ec24315eb678a9b2e709833
#         AIUEOS_SSH_KEX_KAT_PASS
```

Measured on 2026-09-04 against
`kotoba-lang/org-ietf-ssh` (deps.edn `:paths ["src"]`): PASS, exit 0.

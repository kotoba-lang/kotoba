# ADR-0243 — a headless box is given its Wi-Fi by sound, bound to its label

- Status: proposed (design only; prototype measured on one Mac and one phone, no K16 run)
- Date: 2026-10-01
- Owner request: 「PC を起動した時にモニター接続なしで、電源を入れる -> 音が流れる ->
  スマホで聞いて認識する -> 登録 -> スマホや PC から無線 LAN 情報を渡す、そのまま登録
  ノードとして接続」. Owner decisions the same day: (1) bind the exchange to a secret
  printed on the box's label, (2) require a speaker and a microphone on the box,
  (3) record the design as an ADR before any implementation.
- Extends ADR-0113 (`auth.kotoba.cloud` device authorization and the sealed Wi-Fi
  profile) and `os/aiueos/contracts/network-bootstrap-v1.edn` (`:wifi-acquisition`).
  Changes no gate state. Does not reopen the softap/captive-portal decision recorded
  there as `:not-taken`.

## What is missing

ADR-0113 seals a Wi-Fi profile to the device's X25519 key, but the profile arrives by
polling the authority, "so the box must already be online". The contract names two
ways to get a headless box online (`:r1` USB tether, `:r2` Wi-Fi Easy Connect) and
states that the QR runs box-to-phone only. `:r2` is Android-native only and
`:ios-configurator` is `:unverified`; `:r1` needs a cable and a trust tap. Neither
gives the experience requested: power on, hear it, hand over Wi-Fi from either phone
family or a PC, no screen, no cable.

## Observation (prototype, 2026-10-01)

A browser prototype (not committed here) showed, on one Mac and one phone:

- the phone's browser decoded an ultrasound ggwave beacon played by the Mac while the
  audible part was only a short bell motif (the data is not audible);
- a Wi-Fi profile sealed in the phone browser (WebCrypto X25519 + HKDF-SHA256 +
  AES-256-GCM) was played back by sound and opened by the receiving side; the owner
  reported it was heard and decrypted;
- in simulation with noise, an 84-byte sealed profile decoded over ultrasound-normal,
  ultrasound-fast and audible-normal ggwave protocols, and a flipped bit or a wrong
  binding was refused.

This is existence evidence, not a reliability figure. There is no success rate over
distance, noise or phone models, and no run on the K16.

## Decision

1. **A third acquisition route, `:r3 :acoustic-sealed`, beside `:r1` and `:r2`.** The
   box sends a beacon; the phone or a PC helper plays back a sealed profile. It needs
   no cable, no Wi-Fi radio state and no authority round trip, and works from iOS and
   Android browsers and from a PC CLI. The softap route stays `:not-taken`.

2. **Hardware: the box must have a speaker and a microphone** (a USB speakerphone is
   acceptable). A box without a microphone cannot use this route and falls back to
   `:r1`/`:r2`. The K16's built-in audio is **unmeasured**; the requirement and the
   purchasing consequence are recorded, not assumed met.

3. **The exchange is bound to a secret on the box's label, not to a code the box
   broadcasts.** The prototype bound the envelope to the broadcast session code, so
   anyone within earshot could point the box at a Wi-Fi of their choosing. Here the
   factory generates a per-device label secret `ls` (16 random bytes, base64url), keeps
   it in the device's factory state (private file, mode 0600) and prints it in the
   label QR next to the existing claim fields. Whoever can read the label can provision
   the box; an eavesdropper who only heard the beacon cannot produce an envelope that
   opens.

4. **Wire format** (all values big-endian where numeric; text is UTF-8):

   - Beacon, sent by the box, ASCII: `mk1|<code>|<fp>|<key>` where `<code>` is 6
     characters from `ABCDEFGHJKMNPQRSTUVWXYZ23456789`, `<fp>` is the first 8 hex digits
     of SHA-256 of the device DID, and `<key>` is the box's X25519 public key, base64url
     (43 characters). `<code>` is regenerated every boot and every successful or refused
     attempt window; it is a session label, not a credential.
   - Profile message, sent to the box, binary:
     `0x57 | ephemeralPublicKey(32) | AES-256-GCM(ciphertext || tag(16))`.
     Plaintext is `security(1) | ssid | 0x00 | passphrase` with `security` 0 open,
     1 wpa2-personal, 2 wpa3-personal; SSID is 1–32 bytes, a passphrase 8–63 bytes
     (absent for open); `ssid + 0x00 + passphrase` is at most 88 bytes so the whole
     message stays within ggwave's 140-byte payload.
   - Keying: `shared = X25519(ephemeral, deviceKey)`;
     `aad = "aiueos-wifi-profile-v1-acoustic\n" + code + "\n" + fp`;
     `salt = UTF-8(ls)`; `okm = HKDF-SHA256(salt, shared, info = aad, 44 bytes)`;
     `key = okm[0..32)`, `iv = okm[32..44)`. The IV is derived rather than sent because a
     fresh ephemeral key is used for every message, so a (key, iv) pair is never reused.
     This is a different suite from ADR-0113's (`…-v1`, which sends its IV) and carries
     its own suite name, `x25519-hkdf-sha256-aes-256-gcm-v1-acoustic`; it is not
     interchangeable with it.
   - Acknowledgement, sent by the box after it opened and stored a profile:
     `ack|<code>`.

5. **The window is closed by default.** The box emits the beacon only while it is
   unclaimed (factory state) and not online. A received and opened profile, a timeout,
   or the attempt limit closes the window; each message that does not open rotates the
   code and counts as an attempt, and five close it. If the box is still offline after a
   profile (a mistyped passphrase) a new window opens, so a wrong password does not
   strand it. The first successful claim closes it for good. After that the only way to
   change Wi-Fi is the authenticated path of ADR-0113. The box keeps the received
   message **encrypted** and never writes the passphrase to a log, a process argument or
   a file of its own. Applying the profile necessarily hands the plaintext to the
   platform's network manager (item 7); that is the one place it exists, in the network
   manager's own private store.

6. **Order of events is sound, then network, then claim.** The acoustic route proves
   nothing about ownership. Once the box is online, ownership is established by the
   existing claim (label token, `GET /api/devices/:did/challenge`, signed
   `POST …/attest`). The label secret `ls` and the claim token are separate fields; `ls`
   is deleted from the box when its claim window closes.

7. **Application of the profile depends on the platform.**

   | Platform | Gate |
   |---|---|
   | NixOS node (Linux) | May apply now. Write a NetworkManager keyfile (mode 0600) and reload; never pass the passphrase as an `nmcli` argument, which is visible in the process list. A value containing a newline is refused rather than escaped. |
   | aiueos bare metal | **Carry only.** ADR-0113 and `device-onboarding-v1` keep `:native-k16-application :pending-wifi-driver`; this ADR does not lift it. |

8. **A PC helper is a first-class sender.** `murakumo node wifi-share` reads the
   passphrase from the OS (macOS keychain with the OS prompt, NetworkManager, `netsh`)
   into its own process, seals it there, and has a local page play the sealed bytes. The
   passphrase never reaches the browser, a log or the network. macOS hides the connected
   SSID from command-line tools, so the helper lets the person choose from saved
   networks. The helper asks for confirmation before sending to a heard beacon.

9. **Sound is part of the product, not decoration.** Data is carried in ultrasound by
   default (`ULTRASOUND_FAST`, with `AUDIBLE_NORMAL` at low volume as a fallback), while
   the audible part is a short bell motif (D major pentatonic). Arrival and
   acknowledgement have their own sounds, because a headless box has no other way to
   say what state it is in.

10. **Where it lives.** This ADR and the contract entry here; the pure protocol
    (beacon and message codec, keying, validation, golden vectors) in
    `kotoba-lang/grant` as one namespace shared by every runtime; the device command
    `murakumo node onboard`, the helper, and a NixOS unit in `kotoba-lang/murakumo`
    (after its claim-responder work is released); the phone page in
    `network-awai/cloud-murakumo-app`, loading the decoder only when that page opens;
    the CLI pin in `cloud-murakumo-installer`. The browser prototype becomes a
    development simulator and is not shipped. Cross-runtime agreement is carried by
    golden vectors, not by shared code.

## Threats and what this does and does not cover

- **Eavesdropper who heard the beacon:** cannot seal an envelope that opens (no `ls`);
  cannot read a captured envelope (no device private key).
- **Someone who can read or photograph the label:** can provision the box until its
  claim window closes. This is the same exposure the claim token already accepts
  (`docs/devices.md`: the label is static and photographable; the window bounds it).
- **Replay of a captured envelope:** it opens only against the session `code`/`fp` it
  was sealed for, and the window closes on first use.
- **Wrong or hostile Wi-Fi:** a box that joins an attacker's network still must reach
  the authority over verified TLS and pass the claim; it can be denied service, not
  claimed by the attacker.
- **Acoustic denial:** anyone can jam the channel. The route is a convenience with the
  `:r1`/`:r2` fallbacks, not the only path.
- **Not covered:** the strength of a user's Wi-Fi passphrase; a microphone-less box.

## Acceptance (none run)

Nothing here is promised publicly until all of these pass on the target hardware, in
line with the node-boot-media ADR's rule that no capability is published before
physical acceptance:

1. The box has working speaker and microphone; record the device and driver.
2. Success rate of beacon decode and profile delivery by distance (0.5 m, 1 m, 3 m),
   room noise, and at least two iPhones and two Android phones, quiet and audible modes.
3. Golden vectors agree across the browser, the device runtime and the helper.
4. A flipped bit, a wrong `code`, a wrong `fp`, a wrong `ls`, and a replay are each
   refused.
5. Unbox to claimed: power on, Wi-Fi handed over, online, claim granted, with the time
   taken recorded.
6. The profile is never present in a log, a process list or an unencrypted file.

## Consequences

- (+) A headless box can be put on Wi-Fi from iOS, Android or a PC with no cable and no
  screen, and says what it is doing.
- (+) The existing claim and ADR-0113 paths are unchanged; this only supplies the
  network they assume.
- (−) The box needs a speaker and a microphone; the K16's are unmeasured.
- (−) The label QR gains a secret field and the factory must generate and store `ls`.
- (−) A second envelope suite exists and must be kept separate from ADR-0113's.
- (−) Reliability is unknown until the acceptance run; ultrasound reaches some phones
  and speakers better than others.

## Open

- Whether `ls` is printed in the existing claim QR or a second QR (changes the label
  spec in the factory flow).
- Exact `ggwave` version pin and licence handling for the vendored decoder in the site.
- Whether the audible fallback is permitted in quiet environments by policy.

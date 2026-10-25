# org-wi-fi-easy-connect

**The Wi-Fi Easy Connect (DPP) bootstrapping URI — the QR payload a headless
machine shows so a phone can put it on a network without anyone typing a
password.**

The name follows the origin-plane rule (AGENTS.md, ADR-2608040100): Wi-Fi Easy
Connect is specified by the Wi-Fi Alliance, so the reverse-DNS of the authority
(`wi-fi.org` → `org-wi-fi`) plus the subject gives `org-wi-fi-easy-connect`.

## Why this exists

A server with no keyboard and no screen has to get onto Wi-Fi somehow, and every
obvious answer moves a passphrase through something that should not hold one.

DPP inverts the direction. The **enrollee** (the headless box) publishes a
bootstrapping public key as a QR code. The **configurator** (a phone already on
the network) scans it and hands over the credential encrypted to that key, over
the air. The passphrase is never displayed, never typed, never pasted, and never
passes through any web page we write.

That is also why the QR points the other way from the usual one: the box has a
screen but no camera, so **a QR can only travel box → phone.** Anything going
phone → box needs radio, a cable, or a server in the middle.

```
   ┌──────────────┐   DPP: URI as a QR    ┌────────────────┐
   │  enrollee    │ ────────────────────▶ │  configurator  │
   │ (headless)   │   bootstrapping       │    (phone)      │
   │  shows QR    │   PUBLIC key only      │  already on     │
   └──────▲───────┘                        │  the network    │
          │   credential, encrypted to     └────────┬───────┘
          └──── that key, over 802.11 ───────────────┘
```

## Scope — the URI, not the protocol

This repository holds **only the bootstrapping information**: the URI a QR
encodes, and the decision about whether to act on it. The DPP protocol itself —
the authentication and configuration exchanges carried in 802.11 action frames —
is **not here**.

That is the same cut [`org-ietf-ssh`](https://github.com/kotoba-lang/org-ietf-ssh)
makes: the wire rules live in one portable place that every consumer reads, and
the sockets live with whoever owns the radio. A bootstrapping URI that two
implementations parse differently is a device that cannot be onboarded, so the
parse belongs in one place.

## Mechanism and decision are separate functions

```clojure
(require '[dpp.uri :as uri])

(uri/parse "DPP:C:81/6;M:0123456789ab;K:MDkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDIgAD...;;")
;; => {:fields {:channels "81/6" :mac "..." :public-key "MDkw..."}
;;     :unknown-tags [] :order ["C" "M" "K"]}

(uri/admit "DPP:C:81/6;M:0123456789ab;K:MDkw...;;")
;; => {:ok? true
;;     :key {:curve :p-256 :form :compressed :point [3 122 ...]}
;;     :mac "0123456789ab"
;;     :channels [{:operating-class 81 :channel 6}]}

(uri/generate {:version 2 :mac "aabbccddeeff"
               :channels [{:operating-class 81 :channel 1}]
               :public-key "MDkw..."})
;; => "DPP:V:2;M:aabbccddeeff;C:81/1;K:MDkw...;;"
```

`parse` is structural and judges nothing — it will happily tell you it found a
tag it does not know. `admit` is the decision, and it is **fail-closed in both
directions that matter**:

- an **unknown tag is refused** unless the caller opts in, because a tag we do
  not understand may be the one that changes what the URI means;
- a **public key that is not an EC SubjectPublicKeyInfo on an admitted curve is
  refused**, rather than handed onward for someone else to worry about.

Every refusal is a named reason (`:point-length-mismatch`,
`:unsupported-curve`, `:public-key-not-last`, `:field-not-terminated`, …).
`nil` would make a malformed key and an unsupported curve the same answer.

`generate` holds itself to `admit`: if what it just built would not be accepted,
it returns an error instead of shipping it to a phone.

## What is verified, and what is not

**Verified** (`kbb --backend sci test/dpp/uri_test.cljk`, 35 checks):

- base64 decoding against Node's `Buffer` — a different code path;
- a real P-256 key from Node's ECDH, with the SubjectPublicKeyInfo **built by
  hand in the test**, so the bytes the library parses were not produced by the
  library;
- compressed and uncompressed points; generate → admit round trip;
- 18 refusals, each pinning its own reason literal.

The suite was **checked by mutation**, both directions:

| mutation | what failed |
|---|---|
| drop the point-length check | exactly `refuses-key/truncated-point` |
| let unknown tags through by default | exactly `refuses/unknown-tag` |

⚠ **UNVERIFIED — interop.** No real Wi-Fi Easy Connect configurator has been
handed a URI from this code. Android has had native support since Android 10
(Settings → Wi-Fi → Add device); **whether iOS exposes a general DPP
configurator has not been measured here.** Do not design an onboarding flow that
assumes iOS can act as one until someone measures it — that would leave iOS users
with no path at all. This is a bootstrapping-URI codec that is internally
consistent and independently cross-checked; it is not yet an onboarded device.

## A trap this repository fell into, so you do not

`nbb.edn` declares `{:paths ["src" "test"]}`, and **nbb reads it from the working
directory, where it wins over `--classpath`.** A mutation test that pointed
`--classpath` at a copy of `src` with the check removed therefore ran against the
*unmutated* source and reported 35/35 green — the mutation had applied to the
file and simply was not on the path.

The green looked exactly like a passing suite. To mutate, copy `src`, `test` and
`nbb.edn` into a directory and run from **there**, and confirm an unmutated copy
still passes first, so a broken copy cannot be mistaken for a discriminating one.

## Run

```sh
kbb --backend sci --classpath src:test test/dpp/uri_test.cljk   # from this directory
```

The suite is an nbb script, not a `clojure.test` namespace, so it runs under
nbb only; `deps.edn` carries the workspace's standard `:test` / `:lint` aliases
but no JVM suite has been written or run here. `src/dpp/uri.cljk` is portable
`.cljc` and the JVM reader branches are exercised by the reader conditionals,
not by a green JVM run — do not report one.

Pure `.cljc`, zero dependencies, no I/O and no host interop: byte vectors of
`0..255` ints in and out.

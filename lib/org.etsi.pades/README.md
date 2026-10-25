# kotoba-lang/org-etsi-pades

**PAdES (ETSI EN 319 142) baseline signatures — a writer**, by incremental
update. Portable `.cljc` on `org-ietf-cms` + `org-iso-pdf`.

```clojure
(require '[pades.core :as pades] '[cms.core :as cms] '[cms.jvm :as jvm])

(pades/sign pdf-bytes
  {:name "署名者" :reason "本契約に署名します"
   :signing-time-pdf (pades/pdf-date "2026-07-30T13:49:55Z")
   :sign-cms (fn [bytes]
               (cms/build-signed-data {:content bytes :detached? true
                                       :certificates [cert] :digest-fn jvm/digest
                                       :signature-algorithm :ecdsa-with-sha256
                                       :sign-fn signer}))})
```

## Why a writer, when the evidence record is better

`cloud.itonami.app.esign` produces an evidence record more precise than a signed
PDF — exhaustive outline, frozen status list, DID-named signers. **A
counterparty will not run its verifier.** They will open a PDF and look for the
blue bar.

So this does one job: hand the outside world something their software already
checks. The record stays the authority; the PDF is the export.

## Incremental update

Nothing already in the file moves. The signature is **appended** — new objects,
a new xref, a trailer with `/Prev`. The original bytes are inside the signed
range, so the document as-signed is a prefix of the file you hold. Rewriting
instead, even to identical semantics, would mean signing bytes the author never
saw.

## `/ByteRange` and the gap

`[0 a b c]` covers `[0,a)` and `[b,b+c)`. The gap is the `/Contents <…>` string
**including its angle brackets** — the one thing that cannot be inside its own
digest. Two ways to get it wrong, both silent:

1. **A gap that does not exactly cover the placeholder** leaves signature bytes
   inside the signed range, or document bytes outside it. Acrobat calls the
   first invalid and — worse — the second **valid**, over a region an attacker
   can edit.
2. **Numbers that change width when filled in** move every following byte. So
   they are written zero-padded to a fixed width and patched in place; `prepare`
   asserts the length is unchanged rather than trusting it.

The suite checks the range against the **file**, not against the code that
computed it: every byte is signed or in the hole, none is both, the hole is
exactly `<0…0>`, and the signature is asserted **not** to verify over the whole
file — which is the mistake that otherwise reads as working.

## Level

**B-B.** `profile` reports the level rather than claiming one: B-T needs a
signature timestamp in the CMS unsigned attributes, B-LT a DSS, B-LTA a document
timestamp. A file that says `:b-b` is one nobody will mistake for archival.

A CMS that does not fit the reservation is **refused, not truncated** — a
truncated signature is a file that looks signed and verifies nowhere.

## Test

```bash
kbb -M:test
kbb -M:lint
```

Apache-2.0.

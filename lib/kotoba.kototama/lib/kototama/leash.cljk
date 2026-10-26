(ns kototama.leash
  "kototama · leash — the revocable member CACAO capability, distilled from
  ibuki delegation + ADR-2606111400. Autonomous identity = a scoped, expiring,
  revocable capability a MEMBER signs in their own runtime; the organism only
  ever PRESENTS the opaque token (present-only — it NEVER signs, holds no
  custodial key). The kotoba node verifies the member signature and attributes
  every autonomous write to the consenting member (`write-author`).

  The leash is the off-switch of the 種をまく doctrine: stop re-issuing (or let
  it expire) and the organism self-disables, falling back to its local log."
  (:require [kotoba.lang.text :as str]))

(defn leash
  "Construct the present-only leash view of a member-issued delegation bundle.
  Required: :member-did :capability :graph :exp (unix seconds). :cacao-b64 is the
  opaque member-signed CBOR (present-only; this lib never inspects or signs it)."
  [{:keys [member-did capability graph exp cacao-b64 nonce]}]
  {:member-did member-did :capability capability :graph graph
   :exp exp :cacao-b64 cacao-b64 :nonce nonce})

(defn valid?
  "A leash is valid iff present, not expired (exp > now), and scoped to the
  intended capability + graph. `now` is a caller-supplied unix-seconds int
  (no wall-clock in the lib → replay-safe).

  SECURITY NOTE (2026-07-13 audit finding, reviewed and intentionally left
  as-is -- see reasoning below): this is a STRUCTURAL/TEMPORAL pre-filter
  only. It never decodes `cacao-b64` or checks any embedded signature, and
  `exp`/`member-did` are trusted as caller-supplied plain fields rather
  than derived from a verified CACAO payload -- so, taken in isolation, a
  caller could pass any `member-did`/`exp` alongside an unrelated/garbage
  `cacao-b64` placeholder and this would return true.

  This is deliberately NOT the real cryptographic gate, by design, not by
  omission:

  1. Nothing reachable from this repo ever performs the actual
     state-changing write this leash would authorize. `kototama.emit/
     envelope` (the only downstream consumer that treats `valid?` as a
     go/no-go gate) hard-codes `:status :dry-run` unconditionally and
     never asserts `:published`; there is no XRPC/HTTP call anywhere in
     this codebase that submits the resulting envelope to a PDS. The
     namespace docstring above (\"the kotoba node verifies the member
     signature\") and ADR-0002 (\"outward broadcast … is a governance
     gate … layered ON TOP of this ABI — it is not a host function\") both
     say the real signature check and the real publish action live in a
     SEPARATE downstream system this repo does not contain.
  2. This machinery (`lib/kototama/*.cljc`, the atproto actor/organism
     layer distilled from the etzhayyim `ibuki` lineage) is architecturally
     independent from `src/kototama/*` (the Chicory WASM tender that is
     this repo's actual untrusted-guest execution boundary) -- `src/`
     never references `leash`/`cacao` at all, so a forged leash here
     cannot escalate into a WASM host-import grant.
  3. `lib/*.cljc` is deliberately dependency-free/portable (bb/JVM/cljs,
     per ADR-0002's \"License: MIT — the lib is dependency-free and
     portable\"); `deps.edn` has no CACAO-verification dependency today.
     Adding one here to verify a token this repo never actually acts on
     would be dead weight, not a real fix.

  If `lib/kototama/*` ever grows real publish machinery, or any consumer
  starts treating THIS function's answer as sufficient authorization for
  an actual state-changing write, this must be revisited (decode
  `cacao-b64`, verify its signature, and derive `exp`/`member-did` from
  the verified payload instead of trusting the caller-supplied plain
  fields — the actual forgery vector today)."
  [{:keys [member-did capability graph exp cacao-b64]} now
   & [{:keys [need-capability need-graph]}]]
  (boolean (and member-did cacao-b64 (number? exp) (> exp now)
                (or (nil? need-capability) (= need-capability capability))
                (or (nil? need-graph) (= need-graph graph)))))

(defn write-author
  "The member DID an autonomous write is attributed to (accountability by
  consent). nil when unleashed → caller must fall back to operator-bearer or
  refuse the write."
  [leash] (:member-did leash))

(defn revoked?
  "A leash is revoked when absent or expired."
  [leash now] (not (valid? leash now)))

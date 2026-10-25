# ADR-0001: `kotoba.ekyc` — JPN 犯収法 / NIST SP 800-63A verification-method catalog

- Status: Accepted (2026-07-14)
- Repository: `ekyc` (kotoba-lang)

## Context

`cloud-itonami-isic-6493` (a factoring-business governed actor, ISIC Rev.5
6493) needs a real, spec-conformant electronic KYC (identity verification)
capability library to eventually wire into its client/debtor intake flow,
even though no live identity-verification vendor connection is attached
here — that requires a licensed operator with real vendor contracts, out of
scope for this codebase to fabricate. The explicit requirement was code
genuinely identical to the real specification, not an invented
approximation, researched from authoritative sources rather than recalled
from memory.

This repo already carries a substantial, independently-built
`ekyc.core`/`ekyc.model`/`ekyc.ports`/`ekyc.adapters.*` implementation (a
generic provider-session-lifecycle substrate: host ports, an EDN provider,
Kagi evidence-custody adapter, VC issuer, identity-ledger bridge,
production-provider transport adapter) authored 2026-07-05–10, depending on
`kotoba-lang/identity`. It targets a different concern — session/evidence
lifecycle against a pluggable vendor host port — and does not cite any
specific regulatory framework. `kotoba.ekyc` (this ADR) is additive: it does
not modify, replace, or depend on `ekyc.core`'s namespaces or files. It is
the layer a `PolicyGovernor` checks structurally (is the claimed method one
of the real enumerated ones, is its required evidence combination present)
*before* a session's chosen method is accepted as legally valid — the two
are meant to compose.

## Research

**Primary source — Japan, seed jurisdiction (this fleet's other financial
actors already cite JPN/金融庁 as a seed jurisdiction).** 犯罪による収益の
移転防止に関する法律施行規則 (Act on Prevention of Transfer of Criminal
Proceeds, Enforcement Regulation; 犯収法施行規則), Article 6, Paragraph 1.
Full current consolidated statutory text retrieved via e-Gov 法令検索's
public data API (`https://laws.e-gov.go.jp/api/2/law_data/420M60000F5A001`,
retrieved 2026-07-14, revision effective 2026-04-15) — not paraphrased from
a secondary source. Cross-checked against 金融庁 (FSA) reference material
"犯罪収益移転防止法におけるオンラインで完結可能な本人確認方法の概要"
(`fsa.go.jp/common/law/guide/kakunin-qa/2.pdf`) and 警察庁 JAFIC guidance,
both of which independently confirm the same letter-to-method mapping.

Ten methods are modeled: for natural-person (自然人) customers, sub-items
ホ (image + live facial image), ヘ (IC-chip read + live facial image), ト(1)
(image-or-chip + reliance on another operator's existing confirmation
record), ト(2) (image-or-chip + transfer to the customer's own
already-verified bank account), ル (カード代替電磁的記録 — the digital
My Number Card equivalent under 番号利用法), カ (公的個人認証サービスの署名
用電子証明書, J-LIS-issued), ワ (accredited certification-business
certificate), ヨ (specific recognized private certification-business
certificate); for corporate (法人) customers, ロ (registry-information-
service lookup) and ホ (electronic-certification-registry-office
certificate). Each catalog entry's required-evidence combination and
document/certificate field requirements (e.g. ホ's image must expose 氏名/
住居/生年月日/写真/厚みその他の特徴; ヘ's IC-chip data exposes 氏名/住居/
生年月日/写真; ワ/ヨ/カ's certificates carry 氏名/住居/生年月日) are taken
directly from the statute's own enumeration, not inferred.

A 2027-04-01 reform is publicly scheduled to abolish the ホ method
(counterfeit-document risk) and renumber the remaining letters. This
catalog models the law as currently in force (as of 2026-07-14); ホ carries
an explicit `:ekyc.method/scheduled-abolition` note rather than silently
pretending the 2027 change doesn't exist or silently pre-adopting it before
it takes effect.

Methods イ/ロ/ハ/ニ/リ/ヌ/ヲ (in-person presentation, non-forwarding postal
mail, proxy-postal delivery) are real but are not "electronic" (eKYC) in the
non-face-to-face-software-mediated sense this library targets; they are
knowingly uncovered rather than fabricated, matching this fleet's "missing
jurisdictions/methods are uncovered, never fabricated" convention (see
`cloud-itonami-isic-2816` docs/adr/0001).

**Secondary source — multi-jurisdiction consistency (matching the rest of
this fleet's facts catalogs' JPN/USA/GBR/DEU pattern).** NIST Special
Publication 800-63A-4, *Digital Identity Guidelines: Identity Proofing and
Enrollment* (final, published July 2025 — the current revision, which
substantially restructured 800-63A-3's IAL framework: IAL1 now requires one
piece of real evidence rather than "no proofing required"; IAL2 and IAL3
now share the identical evidence-strength requirement, 1 FAIR+1 STRONG or 2
STRONG or 1 SUPERIOR, differing only in proofing-attendance type and
mandatory biometric-sample collection). Full text retrieved from
`nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-63A-4.pdf`
2026-07-14 and read directly (not summarized secondhand), including the
Table 1 requirements summary and Appendix A evidence-strength examples.

## Decision

1. `kotoba.ekyc` models ten catalog entries (`method-catalog`), each with a
   real statute citation, an OR-of-AND-groups `:required-evidence` shape
   (matching the statute's "A の画像又はB の情報...とともにC" structure —
   e.g. ト accepts image-OR-chip, together with a required second slot),
   per-kind `:document-fields`, and a live-capture requirement flag.
2. `assurance-level`/`ial-approx` is an HONEST, per-method, non-uniform
   mapping onto NIST IAL, reasoned from the evidence-strength framework
   (Appendix A's FAIR/STRONG/SUPERIOR examples) rather than a single
   constant applied to every method:
   - ホ → `:ial1` (a single document-strength piece meets IAL1's floor but
     falls short of IAL2's 2-piece/SUPERIOR minimum with only one document).
   - ヘ / ル / カ → `:ial2` (their IC-chip / cryptographic-credential /
     PKI-certificate evidence is analogous to NIST's SUPERIOR-evidence
     examples — mDL, PIV Card, digital Verifiable Credential — one piece
     of which independently satisfies IAL2).
   - ワ / ヨ → `:ial2-conditional` (PKI-based, but assurance is inherited
     from a private certifier's own issuance-time proofing rigor, which
     this library cannot independently verify).
   - ト(1) / ト(2) → `:not-directly-comparable` (a transitive-reliance /
     federation-like trust model — NIST 800-63A scores a single proofing
     event's evidence strength, not reliance on another party's proofing,
     which is 800-63C's federation scope).
   - 法人 ロ / ホ → `:not-applicable` (NIST IAL is a natural-person
     framework with no legal-entity mapping).
   - No individual eKYC method reaches `:ial3`: IAL3 mandates on-site
     attended proofing regardless of evidence strength, and every 犯収法
     electronic method modeled here is remote/software-mediated.
3. `validate` returns `:fail` (never a fabricated fallback level) for any
   method id outside the real catalog — the fabrication guard the governor
   needs before accepting a client/debtor.
4. No network, no I/O, no biometric matching, no liveness detection, no
   document OCR/authenticity forensics anywhere in this namespace — only
   structural/evidentiary completeness against the real enumerated
   requirements. `:ekyc.evidence/captured-live?` is a boolean flag a real
   vendor integration sets after its own liveness check; this library never
   performs that check itself.
5. Mirrors `kotoba-lang/banking` and `kotoba-lang/swift`'s exact capability-
   library shape: a pure `.cljc` core, `kotoba.ekyc.ui` (read-only
   governor-gated operator console, no `<form>`/`<button>`), and
   `kotoba.ekyc.export` (RFC-4180 CSV + JSON), all built on
   `kotoba-lang/html` + `kotoba-lang/css`.
6. This repo's pre-existing MIT LICENSE (with the real copyright holder
   already filled in, covering the pre-existing `ekyc.core` code) is kept
   as-is rather than switched to match banking/swift's Apache 2.0 —
   changing it now would retroactively relicense that already-shipped code,
   which is out of this addition's scope, and MIT does not conflict with
   coexisting alongside Apache-licensed sibling libraries.

## Consequences

(+) `cloud-itonami-isic-6493` gets a governor-checkable, real-regulation
identity-verification method catalog with an honest (not fabricated)
assurance-level cross-reference, ready for a licensed operator to wire a
real vendor behind with minimal translation work.
(+) Coexists cleanly with the pre-existing `ekyc.core` provider-session
substrate — different namespaces, different files, complementary layers.
(−) Only JPN is modeled; other jurisdictions' eKYC regulations (e.g. EU
eIDAS, US state-level identity-proofing rules referenced by NIST 800-63A's
RP ecosystem) are not covered and must not be inferred from this catalog.
(−) The 2027-04-01 reform will require a follow-up revision to this catalog
(abolish ホ, renumber remaining letters) — tracked as a known future change,
not modeled preemptively.
(−) `ial-approx` is explicitly approximate; it must never be presented to a
real relying party as a certified NIST IAL determination.

## Related

- Sibling architecture/convention: `kotoba-lang/banking`, `kotoba-lang/swift`
  (capability-library shape, operator console, CSV/JSON export).
- Superproject fleet ADR for this addition: see `90-docs/adr/` in the
  com-junkawasaki superproject (JPN 犯収法 / NIST 800-63A citations mirrored
  there).
- "Missing jurisdictions are uncovered, never fabricated" convention:
  `cloud-itonami-isic-2816` docs/adr/0001.

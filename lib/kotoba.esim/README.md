# kotoba-esim

[![CI](https://github.com/kotoba-lang/esim/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/esim/actions/workflows/ci.yml)

**GSMA Remote SIM Provisioning (eSIM) identifiers, profile lifecycle and
provisioning ports in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library that gives an
eSIM provisioning operator the records it keeps — eUICC identifiers (EID),
profile identifiers (ICCID), installed profile descriptors and their state,
activation codes an LPA consumes, lifecycle notifications, SM-DS event
registrations and subject-level ownership transfers — plus a **pure state
machine** over the profile lifecycle and the **host-injected ports** a
provisioning actor implements.

Two RSP variants are distinguished because their manager roles differ:
`:consumer` (GSMA **SGP.22**, an LPA on the device driving SM-DP+ / SM-DS) and
`:m2m` (GSMA **SGP.02**, an SM-SR / SM-DP pair with no local assistant).

The library models **records, not the wire format** — the same posture
[`kotoba-lang/card`](https://github.com/kotoba-lang/card) takes toward ISO 8583
and [`kotoba-lang/rcs`](https://github.com/kotoba-lang/rcs) takes toward
SIP/MSRP. No network, no I/O. Portable `.cljc` across JVM / ClojureScript /
SCI / GraalVM.

> **Never carries key material.** ES2+/ES9+/ES10x message framing, BPP (Bound
> Profile Package) construction, SCP03t secure channel, GSMA CI trust-chain
> verification and profile content are all explicitly out of scope.

## Delegated authorities

This library does not re-implement what a sibling already owns:

| Concern | Delegated to |
|---|---|
| ICCID check digit (ITU-T E.118 mod-10) | [`kotoba.card/luhn-valid?`](https://github.com/kotoba-lang/card) |
| MSISDN validity **and canonical form** | [`kotoba.phone/normalize-e164`](https://github.com/kotoba-lang/phone) |

`kotoba.phone` deliberately accepts a bare national digit string as
normalizable, so `profile` stores the normalized `+<digits>` form rather than
the caller's input — delegating a numbering plan means delegating its canonical
form too, not just its yes/no. One line cannot appear as two records.

## The lifecycle is the point

`kotoba.esim.lifecycle` exists so that *is this operation even reachable from
the state we have on record?* is answered by a **total, deterministic function
with no I/O, no model and no policy**. It is the intended callee of a consent
surface's pre-check, which must reject an unreachable operation *before* any
human approval is requested.

```
:absent --download--> :disabled --enable--> :enabled
                          ^                    |
                          +------disable-------+
                          |
                       delete
                          |
                          v
                      :deleted   (terminal)
```

```clojure
(require '[kotoba.esim :as esim] '[kotoba.esim.lifecycle :as lc])

(lc/reachable? :disabled :enable)   ;=> true
(lc/reachable? :enabled  :delete)   ;=> false
(lc/describe   :enabled  :delete)
;=> "delete: refused from enabled (reachable from disabled)"
```

Two rules are worth naming because they are decisions, not transcriptions:

- **`:delete` is admitted only from `:disabled`.** Refusing to delete an enabled
  profile is a deliberately conservative reading, not a quoted requirement: a
  device may well disable-then-delete in one user gesture, but a gate that has
  to justify itself to an operator is better off requiring the disable to be an
  explicit, separately consented step — the failure mode of getting it wrong is
  a subject losing connectivity with no profile enabled.
- **Enabling a second profile is refused, naming the incumbent.** An eUICC has
  at most one enabled profile, so enabling another implicitly disables the
  first. `apply-operation` returns `:enable/would-displace` with the incumbent's
  ICCID instead of silently taking a subject's working line away as a side
  effect. The displacement stays expressible — as two explicit decisions.

```clojure
(lc/apply-operation [(esim/profile a :enabled) (esim/profile b :disabled)] b :enable)
;=> {:esim/ok? false
;    :esim/issues [{:esim/issue :enable/would-displace :esim/incumbent "89810...30"}]}
```

`apply-operation` is total: it returns data and never throws, and every refusal
carries a reason a governor can cite rather than re-derive.

## Ports

`kotoba.esim.ports` defines the protocols; the host — a governed actor such as
`cloud-itonami/cloud-itonami-esim` — supplies implementations backed by a real
SM-DP+ / SM-DS, or by fixtures offline. Modeled on
[`kotoba-lang/koe`](https://github.com/kotoba-lang/koe)'s voice ports.

- `IProfileProvisioning` — `euicc-info`, `download-profile`, `enable-profile`,
  `disable-profile`, `delete-profile`
- `IEventRegistration` — SM-DS event registration; **SGP.22 Consumer only**,
  since SGP.02 M2M has no discovery server
- `IOwnershipTransfer` — deliberately **separate**, so a transfer is a distinct
  authority a host can decline to implement or gate far more strictly, and a
  caller cannot reach it merely by holding a provisioning port

No SDK, endpoint, certificate or credential lives in this library. An
implementation that hardcodes an SM-DP+ address or a GSMA CI trust anchor here
has put deployment configuration in a portable library.

## Identifiers are quasi-PII

EID and ICCID are device-bound. `kotoba.esim.export` therefore **masks them by
default**, emitting only the last four digits unless the caller passes
`:reveal-identifiers? true` — an export is precisely where identifiers leak (a
CSV lands in a spreadsheet, a mail attachment, a ticket). Subject identifiers
are *not* masked: an audit exists to name the accountable parties.

This is a deliberate departure from the sibling exports in `kotoba-lang/rcs` and
`kotoba-lang/phone`, whose E.164 endpoints are not device-bound the way an EID
is.

## On specification citations

This library cites the specification **documents** (SGP.22 Consumer, SGP.02
M2M, ITU-T E.118) and the structural rules verified against records here, and
deliberately does **not** cite individual clause or annex numbers, because those
were not checked against the specification text in this build.

Concretely: `eid-valid?` checks 32 decimal digits with the telecom MII `89` and
**does not verify the EID checksum**. GSMA specifies one, but this build did not
verify which algorithm, and guessing would reject valid EIDs. The predicate
answers the narrower structural question rather than a wrong stronger one, and
says so in its docstring. Where a rule is a conservative reading rather than a
requirement, the docstring says that too.

## Maturity

| | |
|---|---|
| Role | capability library |
| Tests | 32 tests / 177 assertions, all green (`kbb -M:test`) — including the D6 port separation, asserted structurally |
| Lint | clj-kondo 0 errors, 0 warnings (`kbb -M:lint`) |
| EID checksum | not enforced — see above |
| Operator console (UI/UX) | not yet — siblings ship a `ui.cljc`; this one does not |
| Governed actor | not yet — `cloud-itonami/cloud-itonami-esim` is step 4 of ADR-2607300300 |

## Design authority

Created as step 1 of the build order in **ADR-2607300300** (`com-junkawasaki/root`,
`90-docs/adr/`), which integrates eSIM, inbound voice reception and card issuing
onto one identity subject in `cloud-itonami-app`. That ADR records why this
library exists rather than extending
[`kotoba-lang/com-gsma-opengateway`](https://github.com/kotoba-lang/com-gsma-opengateway):
that clean-room actor's schema carries `Subscriber`/`Session`/`Number`/
`UsageRecord` and **no** eUICC, EID, ICCID, profile state, SM-DP+ or SM-DS, so
using it would mean growing the entire eSIM domain onto a record set that never
had it.

## Development

```bash
kbb -M:test     # sibling ../phone and ../card are resolved via :local/root
kbb -M:lint
```

## License

Apache-2.0. See [LICENSE](LICENSE).

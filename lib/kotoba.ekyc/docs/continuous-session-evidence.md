# Continuous session evidence v1

The research admission path now requires two independent inputs: reviewed identity
routes and current session evidence. Identity points do not cancel session alerts,
revocation, account suspension, screening, scope or quota failures.

## Model and numerical meaning

`identity-session` maintains discounted positive evidence r and unresolved adverse
evidence s. Its generalized Beta parameters are alpha=1+r and beta=1+s. The same
state is projected into Subjective Logic: b=r/(r+s+2), d=s/(r+s+2), u=2/(r+s+2),
base rate a=0.5 and projected value b+a*u. These are one model, not two independent
votes. Fixed evidence masses are provisional policy choices, not learned
likelihood ratios or counts of independently adjudicated observations. Results
are explicitly `calibrated=false`; no statistical confidence/credible interval,
ATO detection rate, or guaranteed probability of identity is published.

The registered authentication observer contributes r=18 for authenticated session
opening, or replaces it with r=198 after a qualified step-up. Positive evidence
has a 30-minute half-life, session lifetime is 30 minutes, and step-up evidence
expires within 15 minutes without extending the session lifetime. Ordinary usage
is not positive evidence. Repeated authentication never adds independent mass.
New-device and behavior alerts contribute bounded s=2 and s=18 per category.
Open alerts require explicit signed benign resolution; even a strong step-up
cannot wash them away. Confirmed session revocation is a latch and cannot reopen.
Observers must not emit these events merely from unverified client assertions.

Initial policy supports code-review, vulnerability-triage and remediation. All are
non-executing research operations and use b>=0.85, d<=0.05, u<=0.20, with no open
alerts. Other action classes are denied; key issuance/export need separate policy
and action-bound step-up qualification before they can be supported.

## Authentic events, not browser scores

`identity-authority/observe-session` verifies an Ed25519 JWS of type
`kotoba-session-event+jwt` using the canonical observer registry. Registry entries
contain active status, public JWK, immutable key ID/thumbprint and allowed kinds.
The CAS transition rechecks the registry after signature verification. Every
admission rechecks the current authentication observer key and permission, so
rotating/revoking its key invalidates old supporting evidence.

The signed event binds policy version, observer, event ID/nonce, session ID,
principal, holder-key ID, observed timestamp, evidence reference and event kind.
JWT claims last at most 120 seconds; observations cannot be future-dated or older
than 120 seconds on ingestion. Duplicate IDs are refused. Late positive events
are refused; recent delayed revocation/adverse signals are still applied, without
rewinding the session's logical clock. Evidence IDs identify the exact finding
being resolved. Kind authorization can separate authentication, risk detectors
and review/resolution operators.

One session retains at most 1024 event references; exhaustion closes admission.
There is no silent evict-and-replay fallback. The storage host must retain revoked
session tombstones through the underlying token lifetime and replay window.
It must not reopen an expired/revoked session reference by pruning its history.
Source integration must enforce telemetry-lag/availability budgets and transport
retry/recovery; the reducer itself is not a sensor or monitoring service.

## Request and execution binding

The gateway hashes the already authenticated session cookie with a fixed service
scope and principal into a private `sessionRef`. It does not forward the raw cookie
to the research authority or expose the reference in public status. The hash is a
binding identifier, not a replacement authentication mechanism: a stolen cookie
still requires real detection/revocation signals.

Private status requests include the session reference and exact research action.
Session projections expire within 15 seconds and before evidence/session expiry.
The gateway requires the same session/action, valid opinion mass, policy version,
thresholds and freshness. Completion requests and receipts must echo the exact
session reference and session policy version. An old or cross-session receipt is
rejected. The authority must re-evaluate from canonical state immediately before
quota reservation/dispatch; a cached status response does not grant execution.
`identity-policy/:reserve` now invokes this evaluation before releasing its effect.
Queued jobs still require another current check at dispatch time.

## Activation boundary

This release implements/test-runs the reducer, observer signature host and API
admission gates. No production observer keys, browser behavioral collection,
real-time attack detector or private canonical authority has been provisioned.
Production intake remains closed. Browser review/storage work remains outstanding.
Real labeled outcomes, calibration, drift/telemetry-loss qualification and controlled
shadow evaluation are required before making accuracy claims or deploying learned
risk models. Conformal prediction and confidence sequences are future work, not
features supplied by this initial opinion model. No raw biometrics, document bytes
or inference content are required by this event schema.

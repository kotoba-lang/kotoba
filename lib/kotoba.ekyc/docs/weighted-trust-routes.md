# Web-first weighted trust routes

Identity profile: `kotoba-identity-2026-09-v2`.
Scoring policy: `kotoba-trust-routes-2026-09-v1`.

| Route | Points | Required evidence | Rollout role |
| --- | ---: | --- | --- |
| `web-reviewed` | 60 | Account-bound browser document capture, supervised live video comparison, signed registered-operator approval | Initial trust root; no native app required |
| `app-passport` | 80 | Verified passport signature/chain/DG1/DG2 and supervised holder comparison, signed registered-operator approval | Separate route added later |

Admission threshold is 60; the sum is capped at 100. These are provisional
internal assurance points, not measured probabilities, legal assurance levels,
or evidence of independence between every underlying document attribute.
The Web path alone qualifies. Adding the app route yields 100, not 140.
Once operationally enabled, the app route can also meet the threshold alone.
App completion is not a launch prerequisite for the Web path.

## Web evidence is reviewed, not chip-authenticated

`:web-document` accepts only a private host event bound to an existing pending
application, account/holder proof and enrollment challenge. It stores private
capture references and digests with `captured-unverified`; it does not assert
passport authenticity. Uploaded images and successful camera access earn zero.
The challenge must be consumed by the host and incorporated in the supervised
live session; replay-resistant capture/liveness must be qualified there.

`:approve-web` requires a registered operator other than the applicant, an actual
operator JWS through `identity-authority/review`, matching document/live digests,
document review, adult/holder/liveness findings, document expiry, private review
evidence, current screening and approved scope. The host derives the private
document tag from reviewed normalized document fields; clients cannot choose it.
No browser request may be converted directly into these trusted events.

## Addition, expiry and revocation

Evidence is keyed by route, so repeated submissions never multiply points.
`:link-route` links an independently approved source application to the same
principal and holder key. It requires signed operator authorization, an explicit
same-person finding and evidence reference. Both applications must currently
qualify, and only original source approvals can be linked. Existing valid route
evidence cannot be overwritten by another same-route submission.

All scores are derived from current evidence using fixed server weights. Wrong
policy, wrong principal/key, unknown routes, expired or revoked evidence do not
contribute. `:revoke-route` invalidates the original route and all linked copies. Credentials
without sufficient remaining evidence are also revoked; restoring a route does
not silently reactivate a revoked credential.
`:revoke` is a hard application/credential stop and also invalidates that
application's originating evidence elsewhere. Other applications' independently
reviewed routes survive a route revocation. A person-wide suspension must be
enforced by the admission host, not simulated by subtracting points.

Review status, credential expiry, AML/CTF clearance, research scope and quota
remain independent mandatory gates. A score of 100 cannot bypass them. Revoking
the Web application stops that application's access even if it had an app bonus.

`identity-trust/projection` is the minimal wire snapshot for the research API:
`policyVersion`, `score`, distinct route IDs, `evaluatedAt`, `expiresAt`.
It includes no document identifier or private evidence reference. It expires
within 60 seconds and before any contributing evidence or identity expires.
The private authority recomputes it from canonical state; the gateway checks
freshness and recomputes the fixed-policy total. Before actual inference dispatch
the authority must recheck live status. Never persist a snapshot as authority.

Credentials carry the new identity and trust policy versions, not a permanently
embedded score. Old v1 records without reviewed route evidence fail admission;
there is no automatic migration that invents evidence for them.

## Qualification boundary

This release implements and tests state transitions, signature verification,
scoring, revocation propagation and the gateway wire gate. Browser capture,
supervised-review UI/operations, protected canonical storage and end-to-end real
customer enrollment remain pending. No production intake is enabled. ZK proving
is separate and is not implemented by assigning points or issuing a JWT.

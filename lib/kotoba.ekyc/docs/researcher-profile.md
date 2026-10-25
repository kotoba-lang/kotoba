# Affiliation and qualification review

The `/identity` application records a holder-signed researcher declaration alongside
purpose and authorized scope. Affiliation can be `independent` or an organization
with its official name, department/role and an evidence reference. Qualifications
can be `none` or up to five credentials, each with name, issuer, registration
reference, evidence source and expiry date (or explicit no-expiry declaration).
Independent researchers and applicants without qualifications may apply.

These are self-declarations until a registered, assigned reviewer checks them.
Names and credential numbers are excluded from status lists and reviewer queues.
The `profile` read goes through the authenticated private identity service, which
checks ownership or assignment and commits an audit before returning the record.
Evidence references are displayed as text; the browser does not fetch submitted
URLs. Nothing is written to localStorage, analytics or public object storage.
The declaration is signed in the `start` proof, immutable for that case, and its
form is locked once the case starts. A new declaration requires a new case.

Approval requires the existing identity, live-interview, screening and authorized
scope checks plus a signed `profile-review` covering every declared organization
and credential. Verification records include a holder match, source, private
review evidence reference, check time and expiry. Credential verification cannot
outlive the declared credential; every verification is capped at one year.
Status distinguishes self-declared absence, pending, verified and expired. This
adds no identity trust weight, research permissions or inference entitlement.

Browser intake requires `profilePolicyVersion` equal to
`kotoba-researcher-profile-2026-09-v1`. The holder notice is
`kotoba-web-intake-2026-09-v2`; older incomplete cases cannot be approved under
this policy and need a new application. Raw client verification flags are never
accepted as authority.

## Operational state

The production private `IDENTITY_AUTHORITY` binding, private storage adapter,
reviewer enrollment and approved retention/deletion/operator notice are not yet
connected. Intake stays closed: this change does not enable real document uploads
or claim that any person, organization or qualification has been verified.
Reviewer signing remains an operator workflow; this release does not add browser
approval buttons. Renewal/revocation requires the private authority operational
workflow; credential expiry is reflected on status reads, never silently renewed.

# Governance and insider-resistance qualification

W6 composes a signed, nonce-consumed capability for one operation; four-axis
subject/resource/action/environment ABAC; digest-bound independent approval;
a bounded break-glass drill with independent signed post-review; and the shared
production evidence plane.

The gate rejects self-approval, duplicate approvers or roles, request-digest
substitution, stale attributes, capability replay, excessive effects, expired
emergency access, missing incident records, self-review, late review, and
unsigned or local evidence.

Break-glass remains an audited exceptional path, never an authorization bypass.
The implementation and fixtures do not qualify production governance; W6 stays
pending until real authorities and a remote receipt log pass this gate.

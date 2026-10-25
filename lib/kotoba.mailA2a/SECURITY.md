# Security policy

MailA2A is an experimental protocol specification and validator, not a secure
mail implementation. Report suspected specification or validator
vulnerabilities privately through GitHub Security Advisories for this
repository.

Do not include production mailbox credentials, private keys, wallet material,
decrypted messages, personal data, or live payment authorizations in a report.

Security-sensitive claims require separate evidence for MIME parsing,
canonicalization, signature verification, identity binding, authorization,
replay storage, MLS state, and x402 verification/settlement. Passing this
repository's validator proves only envelope-shape and event-order checks.

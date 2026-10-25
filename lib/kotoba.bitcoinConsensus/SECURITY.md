# Security

Do not use this kernel as a replacement for Bitcoin Core until every release
blocker in the README is implemented, differentially tested, fuzzed, and
independently reviewed. Invalid or ambiguous encodings fail closed.

Every change replays the bounded consensus fuzz seed in CI. Nightly jobs widen
the deterministic seed corpus. A failure report contains its target, seed,
case index, input length, and bounded hexadecimal prefix; reproduce it with
`kbb -M:fuzz <seed> <iterations>` before reducing the case.

No private-key, signing, wallet, mining, or transaction-broadcast API belongs
in this repository.

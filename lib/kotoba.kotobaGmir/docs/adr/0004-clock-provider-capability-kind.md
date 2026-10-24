# ADR 0004: Reserve the clock-v1 native capability kind

## Status

Accepted.

## Decision

The closed native capability-kind table assigns code `4` to `:clock-v1`.
Unlike the earlier same-type codecs, this discriminator names the sealed pair
of clock request and result descriptors; those descriptors differ but travel
through one bounded provider syscall contract.

The numeric capability id still controls authority. The kind controls only
the value codec and cannot grant a capability.

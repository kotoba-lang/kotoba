# Production authentication hardening

`authentication.production` defines the fail-closed contracts hosts must apply
before exposing Identity BaaS publicly: exact redirect allowlists, double-submit
CSRF plus origin checks, fixed-window rate limits, session rotation and global
revocation, bounded signing-key activation, redacted audit events, and
multi-factor account recovery with cooldowns.

HTTP middleware and persistence adapters remain host responsibilities. Hosts
must transact session rotation/revocation atomically and use a strongly
consistent coordinator for rate-limit and one-time-token consumption.

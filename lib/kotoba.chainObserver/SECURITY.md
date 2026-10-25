# Security policy

Report vulnerabilities through GitHub private vulnerability reporting.

This library carries no keys or credentials and performs no transaction
submission. Keep those properties invariant. Injected transports must enforce
TLS, response-size and time bounds, request correlation, endpoint policy, and
least-privilege credentials. A `:remote-rpc` observation is not proof of
consensus. Bind production adapters to expected chain identity or genesis
values and require an explicit trust policy before acting on observations.

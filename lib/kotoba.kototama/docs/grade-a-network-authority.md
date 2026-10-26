# Grade A network and database provider authority

Production `http-post` admission requires one complete authority envelope:

- an exact canonical HTTPS endpoint set;
- the fixed `POST` method;
- a workload purpose matching the policy purpose;
- an opaque credential reference resolved only inside the host;
- maximum calls, request bytes, and response bytes.

`kototama.network-authority` rejects incomplete policies, HTTP/userinfo
endpoints, lookalike domains, path substitution, method changes, purpose
confusion, invalid credential resolution, and quota overflow.
`kototama.tender` validates the envelope before artifact parsing and rechecks
the exact URL, method, request size, call number, credentials, and response
bound for every guest-triggered request. Secret credential values never enter
guest memory or the checked-in policy.

Verification:

```sh
kbb -M:test -n kototama.browser-test \
  -n kototama.network-authority-test \
  -n kototama.tender-test
```

T-06 remains `in-progress`. The native transport and PostgreSQL providers have
their own exact endpoint/ABAC/opaque-handle qualification, but one consolidated
cross-provider confused-deputy corpus is still required. The JDK HTTP resolver
also cannot pin the address checked before connection, so DNS rebinding remains
an explicitly inventoried TCB risk.

# Grade A trusted-computing-base inventory

Grade A gap T-01 uses `qualification/tcb-inventory.edn` as the reviewed,
machine-verifiable tender TCB boundary.

The inventory pins every authority-bearing source file by SHA-256, records its
security role, pins six external runtime/provider dependencies, and explicitly
lists native or unsafe boundaries. The current high-risk boundaries are
Chicory's unsafe execution listener, JDK HTTP/DNS resolution, and same-process
JVM/JIT isolation.

`kototama.tcb/validate` fails on a missing file, duplicate path, missing role,
digest drift, absent external-boundary inventory, or an unversioned external
dependency:

```sh
kbb -M:tcb-check
kbb -M:test -n kototama.tcb-test
```

Changing trusted source now requires an intentional inventory review and
digest update. T-01 remains `in-progress` until mutation/adversarial coverage
is complete and an independent reviewer audits these boundaries and verifies
the remediation retest.

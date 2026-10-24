# provider-incidence

Physical, capability-scoped durability for Kotoba's content-addressed
incidence dataspace.

One provider instance receives one explicit `java.nio.file.Path` directory
and one exact dataspace name. It has no ambient default path. An append is
acknowledged only after the addressed incidence is hash-verified, written to a
temporary file, `fsync`ed, atomically moved to its CID filename, read back,
and the blocks directory is `fsync`ed. Recovery parses inert EDN with no tagged
readers, verifies every filename/CID pair, and rebuilds the bounded anti-entropy
replica from disk.

Independent provider instances can replicate verified blocks into independent
directories. This is physical multi-node recovery evidence, not consensus and
not proof of a remote machine merely because directories differ.

The adapter re-checks the concrete `:host/ledger-append` capability and exact
dataspace at the native filesystem boundary. The directory object and live
provider are runtime capabilities; neither is serialized.

`export-bundle` / `import-bundle!` provide a bounded inert-EDN transfer
boundary. A bundle contains no capability; the receiver supplies a fresh
dataspace-scoped append capability, and the complete bundle is CID-validated
before the first target append.

Qualification entrypoints live outside the production classpath:

```bash
kbb -M:physical-drill seed ROOT BUNDLE
kbb -M:physical-drill import ROOT BUNDLE
kbb -M:physical-drill recover ROOT

# Resumable target count with multi-cycle B/C partitions and store reopen.
kbb -M:soak ROOT 1000
```

The physical drill is meant to run the phases on separate hosts and remove
the source host's temporary store before recovery. Three directories on one
disk remain a local durability test, not multi-machine evidence.

```bash
kbb -M:test
kbb -M:lint
```

# v0.1.0 compatibility evidence

The checked-in corpus under `test/fixtures/onepux/` is entirely synthetic. It covers login,
credit-card and unknown future category/field preservation without embedding personal data.

Release verification:

```bash
kbb -M:test
kbb -M:lint
```

Known limits:

- 1Password documents only part of the category taxonomy.
- Attachment path semantics remain best-effort.
- Live `op` CLI import is outside v0.1.0.
- Real customer exports must never be committed as fixtures.

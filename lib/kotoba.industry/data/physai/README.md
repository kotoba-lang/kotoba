# physai-isic industry actor bot registry

Archived registration of the `physai-isic-*` industry actor bot fleet (Hermes
profiles under the `itonami` profile). Saved here 2026-10-18 per owner
direction; the local profile copies were removed after this landed.

* `manifest.edn` - the fleet roster (profile, ISIC code, business repo, ledger).
* `ledgers/<profile>/necessity-impact.jsonl` - schema
  `itonami.necessity-impact.v1`, append-only measurement ledgers copied
  verbatim as of the save date. `status: UNMEASURED` rows carry no invented
  numbers by design.

Each bot's business repository is `cloud-itonami-isic-<code>`. Secrets were
never part of these profile directories and are not included.

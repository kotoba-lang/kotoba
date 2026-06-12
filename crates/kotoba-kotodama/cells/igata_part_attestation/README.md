# igata_part_attestation — Pregel cell for final lineage + IPFS pin + material balance

Per **ADR-2605261200 §Design Pregel cells #8**.

Paired actor: [igata](../../igata/).

Murakumo node (proposed): **levi** (verification + attestation specialist; same as `igata_post_cast_qc`).

**G14 + G10 enforcement cell** — full lineage chain + IPFS pin + material balance ≥95% enforced here.

Lineage chain walked back through all 7 upstream cells:

```
partAttestation.lineage = [
  alloyAttestation_CID,       # from igata_alloy_melt
  dieAttestation_CID,         # from igata_die_preparation
  castShotRecord_CID,         # from igata_shot_injection (full @ 1 kHz profile)
  ejectedPartRecord_CID,      # from igata_solidification_eject
  qcAttestation_CID,          # from igata_post_cast_qc (X-ray CT + mech + visual)
  trimmedPartRecord_CID,      # from igata_trim_machining (scrap mass log)
  heatTreatedRecord_CID,      # from igata_heat_treatment (HT branch + verify)
]
```

IPFS pinning path (per ADR-2605241500 + ADR-2605232400):
- Tier D blob primitive (`kotodama.substrate.blob.upload_blob`) — bit-identical `{cid, sizeBytes, mediaType}` receipt
- Pinned via libp2p mesh sibling (iroh 0.28.1 or Kubo loopback)
- DataLad + git-annex `directory` remote for dataset-CID substrate continuity

Material balance ≥95% (G10 invariant):

```
recovered_mass = sprue_mass + runner_mass + flash_mass + chip_mass + reject_part_mass + die_spray_residue_mass
theoretical_loss = melt_input_mass - final_part_mass

invariant: recovered_mass / theoretical_loss >= 0.95
```

Reject `partAttestation` emission if invariant violated (escalate to silen review).

Cross-actor downstream (R2+):
- `wadachi.vehicle_body_assembly` (R3 gate; G11 + N7 structural cert audit)
- `tatekata.structural_assembly` (R2 pilot OK)
- `watatsumi.hull_ring_fabrication` (R3 gate; ≤200m depth class only)
- `silicon.silicon_packaging` (R2 bidirectional; fab equipment frame casting)

R0..R1 = no cross-actor messages emitted; only `partAttestation` MST record written.

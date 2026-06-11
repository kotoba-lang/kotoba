# seigyo_opcua_bridge — Pregel cell for the OPC UA L2.5 gateway

Per **ADR-2606111000 §1** (L2.5) + **§6** row 4; exchange standard per
ADR-2604252100 (OPC UA information model / AutomationML).

Murakumo node (proposed): **judah**. §2(a)(c) risk: **MEDIUM**.

This is the seam where the existing L3 manufacturing cells meet the
control layer:

```
L3 recipe (e.g. silicon_etch: gas mix + RF power + endpoint setpoint)
  → seigyo_opcua_bridge: envelope precheck → OPC UA write (open62541)
    → L1 OpenPLC (clamps to compiled envelope regardless, ADR §3.4)
      → readback confirm → dispatch record
```

- `seigyo.ioPointRegistry` is mirrored into the OPC UA address space;
  points behind embedded proprietary controllers are
  **untrusted-external** (ADR §2).
- Dispatch is refused to controllers with a `seigyo.runtimeAttestation`
  hash mismatch (ADR §4).
- Southbound legacy: Modbus TCP/RTU; optional intra-site MQTT Sparkplug B.

Scaffold-only until Council fleet.toml attestation + silen-seigyo baseline
review (import raises `RuntimeError`).

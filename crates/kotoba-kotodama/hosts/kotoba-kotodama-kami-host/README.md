# kotoba-kotodama-kami-host

Native KAMI host with:
- `wgpu` desktop rendering
- headless automation
- screenshot capture
- golden screenshot verification
- UI/UX quality gating

## Local Commands

Update golden screenshots:

```bash
cargo run --manifest-path 20-actors/kotoba-kotodama/hosts/kotoba-kotodama-kami-host/Cargo.toml -- \
  --update-golden 20-actors/kotoba-kotodama/hosts/kotoba-kotodama-kami-host/golden \
  --artifact-dir /tmp/kotoba-kotodama-kami-golden-update
```

Verify screenshots and UI/UX score:

```bash
cargo run --manifest-path 20-actors/kotoba-kotodama/hosts/kotoba-kotodama-kami-host/Cargo.toml -- \
  --verify-golden 20-actors/kotoba-kotodama/hosts/kotoba-kotodama-kami-host/golden \
  --min-uiux-score 85 \
  --artifact-dir /tmp/kotoba-kotodama-kami-golden-verify
```

Run headless sample only:

```bash
cargo run --manifest-path 20-actors/kotoba-kotodama/hosts/kotoba-kotodama-kami-host/Cargo.toml -- \
  --headless \
  --artifact-dir /tmp/kotoba-kotodama-kami-headless
```

## CI Contract

The golden verify workflow fails when either condition is true:
- screenshot diff exceeds the allowed mismatch threshold
- `uiux-report.json` has `score < 85`
- `uiux-report.json` contains any `High` or `Critical` findings

Failure artifacts include the latest screenshots and any generated `*.diff.png`.

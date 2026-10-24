# Changelog

## 0.1.0 — initial release

- `kotoba.lang.force3d.core`: simulation construction (`simulation`), single
  `tick`, and `simulate` (run-to-alpha-threshold) integrator.
- Forces: `charge` (pairwise repulsion/attraction), `link` (spring toward
  target distance), `center` (gravitate toward a center point), `collision`
  (prevent node overlap given per-node radius).
- All forces operate on x/y/z (3D), not just x/y.

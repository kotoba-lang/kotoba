# kami-sensor-sim

Robotics sensor synthesis, `isaacsim.sensors` API-compat target. Zero-
dependency, portable CLJC (JVM / SCI / ClojureScript / GraalVM /
kotoba-WASM).

Restored from the deleted `kami-sensor-sim` Rust crate
(`kotoba-lang/kami-engine`, removed in PR #82 "Remove Rust workspace") as
part of the clj-wgsl migration, ADR-2607010930 (`com-junkawasaki/root`).

## Modules (5 namespaces + root, ~740 lines of `src/`)

| Namespace            | Lines | Restored from | Purpose |
|-----------------------|------:|-----------------|---------|
| `sensor-sim`           |    54 | `lib.rs`        | Root namespace: docstring cataloguing every submodule + documented exclusions; requires all 4 sensor submodules. |
| `sensor-sim.math`      |   171 | (`glam` usage, extracted) | vec3 / mat3 / affine3 / quat helpers shared by every sensor namespace (not a 1:1 Rust module -- glam is a dependency, not part of the original crate's own source). |
| `sensor-sim.camera`    |   127 | `camera.rs`     | Pinhole `Camera`: intrinsics from HFOV, extrinsics via `look-at`, world-point projection, z-buffer depth-image rasterization. |
| `sensor-sim.lidar`     |   175 | `lidar.rs`      | Analytic ray-cast `Lidar` (VLP-16 / toy intrinsics, ROS REP-105 sensor frame) against a `Scene` of `Primitive`s (ground-plane / sphere / AABB). |
| `sensor-sim.imu`       |    83 | `imu.rs`        | Body-frame `Imu`: finite-difference proper acceleration + rotated angular velocity; physics-engine-agnostic (world-frame link state in). |
| `sensor-sim.contact`   |   130 | `contact.rs`    | Sphere-approximated `ContactSensor` (`sample` nearest surface, `sample-all` every simultaneous overlap, deepest-first) vs the same `Primitive`/`Scene` types as `sensor-sim.lidar`. |

All four sensor types the original crate implemented before deletion
(`camera`, `lidar`, `imu`, `contact` -- see `lib.rs`'s
`SUPPORTED_SENSORS_R1_1`) are restored. The original crate's own planned
R1.2+/R1.6 WebGPU-compute acceleration (WGSL raster + ray-query against a
scene BVH) was never implemented before the crate was deleted, so there was
nothing further to port for that scope.

## Test / assertion counts

`kbb -M:test` -- **33 tests, 73 assertions, 0 failures, 0 errors.**

Every applicable original Rust `#[test]` (inline `#[cfg(test)] mod tests` in
each of the four sensor modules) was ported 1:1, plus a namespace-loads
smoke test for the root namespace:

| Test namespace | Ported from | Tests |
|-----------------|--------------|------:|
| `sensor-sim.camera-test`  | `camera.rs` inline tests  |  9 |
| `sensor-sim.lidar-test`   | `lidar.rs` inline tests   |  9 |
| `sensor-sim.imu-test`     | `imu.rs` inline tests     |  4 |
| `sensor-sim.contact-test` | `contact.rs` inline tests | 10 |
| `sensor-sim-test`         | (smoke test)              |  1 |

The `sensor-sim.imu-test` tests thread the IMU's returned `:imu` state
explicitly between calls, since `sensor-sim.imu/sample` is pure-functional
(`{:reading r :imu next-imu}`) rather than mutating `&mut self` the way the
original Rust `Imu::sample` did -- see `sensor-sim.imu`'s namespace
docstring.

## Excluded: `tests/*_on_genesis.rs` (4 files, 8 tests)

The original crate's `tests/camera_on_genesis.rs`, `contact_on_genesis.rs`,
`imu_on_genesis.rs`, and `lidar_on_genesis.rs` were cross-crate integration
tests: each drove a `kami_genesis::IsaacWorld` physics articulation (parsed
from an embedded cartpole URDF fixture via `kami_articulated::parse_urdf`)
and confirmed the corresponding sensor read real physics-engine link state
correctly (e.g. a camera's projected depth tracking a driven cart's
distance, a lidar's range shrinking as the cart approached an obstacle, an
IMU reading +g at rest and proper acceleration under drive force, a contact
sensor's penetration growing as the cart was driven into an obstacle).

Both dependencies these tests required are gaps this restoration does not
close:

- **`kami-genesis`** (the physics engine) has never been restored as a
  `kotoba-lang` repo.
- **`kami-articulated`** (the URDF parser) is currently an empty
  mid-restoration placeholder (`kotoba-lang/kami-articulated`).

`kotoba-lang/kami-shugyo` hit these exact same two gaps restoring its own
`ee_reach.rs` module and duck-typed both locally rather than waiting on
them (see its README). Faithfully porting these four integration tests here
would mean reimplementing a full rigid-body physics engine and a URDF
parser as a side effect of restoring a *sensor* crate -- out of scope.
Every *sensor-side* assertion these tests made (projected depth tracks
distance, contact penetration grows with depth, lidar range tracks
distance, IMU reads +g at rest / proper accel under force) is already
covered by the inline `#[test]` units ported 1:1 above, which construct
world-frame states directly instead of deriving them from a driven
articulation.

## Relationship to `kotoba-lang/kami-shugyo`

`kami-shugyo` (an Isaac-Lab-equivalent RL training framework, already
restored) referenced `kami-sensor-sim::ContactSensor` as a path dependency
in its original `Cargo.toml` (used by `ee_reach_env.rs`'s Cartesian
end-effector reach task). Since `kami-sensor-sim` did not exist as a
`kotoba-lang` repo at the time `kami-shugyo` was restored, its
`shugyo.ee-reach` namespace duck-typed a minimal contact sensor locally
(`ee-in-contact?`: point-goal proximity, `‖ee - goal‖ < contact-radius`)
rather than depending on this crate.

This restoration does **not** retroactively wire `kami-shugyo` to depend on
`sensor-sim.contact` -- `kami-shugyo` is treated as read-only reference
context here, per this restoration's scope. A future pass could replace
`shugyo.ee-reach`'s duck-typed contact check with a real
`sensor-sim.contact/sample` call against a `sensor-sim.lidar/scene`, now
that this crate exists.

## Usage

```clojure
(require '[sensor-sim.camera :as camera]
         '[sensor-sim.lidar :as lidar]
         '[sensor-sim.imu :as imu]
         '[sensor-sim.contact :as contact]
         '[sensor-sim.math :as m])

;; Pinhole camera projecting a world point to a pixel + depth.
(def intr (camera/camera-intrinsics-from-hfov 640 480 (m/deg->rad 90.0)))
(def cam (-> (camera/camera-new "cam" "/World/cam" intr)
             (camera/look-at [0.0 0.0 -5.0] [0.0 0.0 0.0] [0.0 1.0 0.0])))
(camera/project-world-point cam [0.0 0.0 0.0])

;; Analytic VLP-16 lidar against a small scene.
(def scene (-> (lidar/scene-new)
               (lidar/scene-add (lidar/ground-plane 0.0))
               (lidar/scene-add (lidar/sphere [5.0 0.0 0.0] 1.0))))
(def l (lidar/lidar-new "lidar" "/World/lidar" (lidar/lidar-intrinsics-vlp16)))
(lidar/acquire-data l scene)

;; Contact sensor sphere-vs-scene overlap.
(def sensor (contact/contact-sensor-new "contact" "/World/cart/contact" "cart" 0.3))
(contact/sample sensor [0.5 0.0 0.0] scene 0.0)

;; IMU reading (functional: returns {:reading r :imu next-imu}).
(def imu0 (imu/imu-new "imu" "/World/imu" "link"))
(imu/sample imu0 m/v-zero m/v-zero (m/quat-identity) 0.0)
```

## License

Apache 2.0 + Charter Compliance Rider v2.0.

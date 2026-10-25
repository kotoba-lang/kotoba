/**
 * Proves the Rust -> wasm32 -> Node bridge for `kami-isaac-sim-wasm`
 * (ADR-2607011300 follow-up): `kami-genesis::IsaacWorld` — Featherstone
 * RNEA/CRBA dynamics + PD control, 208 tests in kami-genesis alone — driven
 * end-to-end from JS via a vendored wasm-bindgen build
 * (`vendor/kami-isaac-sim-wasm/`, see its README for provenance/regen).
 *
 * This does NOT exercise `src/isaac-sim.ts` / `src/e7m-sim/` — those still
 * run the from-scratch TS Featherstone reimplementation. Wiring them to this
 * WASM engine instead is a follow-up (needs a sync-vs-async-load decision
 * the existing synchronous TS API doesn't currently accommodate).
 *
 *     pnpm exec vitest run test/isaac-sim-wasm-bridge.smoke.test.ts
 */

import { describe, it, expect } from "vitest";
// @ts-expect-error -- vendored wasm-bindgen CJS build, no package.json export map entry
import { IsaacWorldHandle, kamiIsaacSimWasmVersion } from "../vendor/kami-isaac-sim-wasm/kami_isaac_sim_wasm.cjs";

const CARTPOLE_URDF = `<?xml version="1.0"?>
<robot name="cartpole">
  <link name="rail"/>
  <link name="cart"><inertial><mass value="1"/><inertia ixx="0.1" iyy="0.1" izz="0.1"/></inertial></link>
  <link name="pole"><inertial><mass value="0.1"/><inertia ixx="0.01" iyy="0.01" izz="0.01"/></inertial></link>
  <joint name="slider_to_cart" type="prismatic">
    <parent link="rail"/><child link="cart"/>
    <origin xyz="0 0 0"/><axis xyz="1 0 0"/>
    <limit lower="-2.4" upper="2.4" effort="100" velocity="10"/>
  </joint>
  <joint name="cart_to_pole" type="revolute">
    <parent link="cart"/><child link="pole"/>
    <origin xyz="0 0 0"/><axis xyz="0 1 0"/>
    <limit lower="-3.14159" upper="3.14159" effort="0" velocity="10"/>
  </joint>
</robot>`;

describe("kami-isaac-sim-wasm bridge (Rust kami-genesis over wasm32, via Node)", () => {
  it("reports the ADR/phase version banner", () => {
    expect(kamiIsaacSimWasmVersion()).toBe("ADR-2605261800@R1.1-cartpole-poc");
  });

  it("loads a URDF, steps under an effort, and moves the cart", () => {
    const world = new IsaacWorldHandle(1 / 60);
    const h = world.add_articulation_from_urdf(CARTPOLE_URDF);

    expect(world.num_dof(h)).toBe(2);
    expect(Array.from(world.dof_names(h) as string[])).toEqual(["slider_to_cart", "cart_to_pole"]);

    const q0 = Array.from(world.get_joint_positions(h) as Float32Array);
    for (let i = 0; i < 30; i++) {
      world.set_joint_efforts(h, new Float32Array([10, 0]));
      world.step();
    }
    const q1 = Array.from(world.get_joint_positions(h) as Float32Array);
    expect(q1[0]).toBeGreaterThan(q0[0] + 0.01);
  });

  it("drives the cart to a PD position target (matches the Rust-side test)", () => {
    const world = new IsaacWorldHandle(1 / 60);
    const h = world.add_articulation_from_urdf(CARTPOLE_URDF);
    world.set_gains(h, new Float32Array([200, 0]), new Float32Array([20, 0]));
    for (let i = 0; i < 600; i++) {
      world.apply_position_action(h, new Float32Array([0.5, 0]));
      world.step();
    }
    const q = Array.from(world.get_joint_positions(h) as Float32Array);
    expect(Math.abs(q[0] - 0.5)).toBeLessThan(0.05);
  });

  it("resets joint state and the step clock", () => {
    const world = new IsaacWorldHandle(1 / 60);
    const h = world.add_articulation_from_urdf(CARTPOLE_URDF);
    for (let i = 0; i < 20; i++) {
      world.set_joint_efforts(h, new Float32Array([8, 0]));
      world.step();
    }
    expect(Math.abs((world.get_joint_positions(h) as Float32Array)[0])).toBeGreaterThan(1e-3);
    world.reset();
    const q = Array.from(world.get_joint_positions(h) as Float32Array);
    expect(q.every((v) => Math.abs(v) < 1e-6)).toBe(true);
    expect(world.current_time_step_index()).toBe(0);
  });
});

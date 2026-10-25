/* tslint:disable */
/* eslint-disable */

/**
 * JS-callable handle around an `IsaacWorld` scene of articulations.
 */
export class IsaacWorldHandle {
    free(): void;
    [Symbol.dispose](): void;
    /**
     * `world.scene.add(Articulation(urdf))` — parses `urdf_text` and
     * registers it. Returns an opaque handle index for the other methods.
     * Panics on malformed URDF or an unsupported topology, matching the
     * `kami-cartpole-wasm` precedent's `.expect(...)` style; graceful
     * `Result`-based error propagation to JS is a follow-up.
     */
    add_articulation_from_urdf(urdf_text: string): number;
    /**
     * `controller.apply_action(ArticulationAction(joint_efforts=targets))`
     * — direct feedforward effort, clamped by `set_max_efforts`.
     */
    apply_effort_action(handle: number, targets: Float32Array): void;
    /**
     * `controller.apply_action(ArticulationAction(joint_positions=targets))`
     * — PD-tracked position targets, using the gains from `set_gains`.
     */
    apply_position_action(handle: number, targets: Float32Array): void;
    /**
     * `world.current_time`.
     */
    current_time(): number;
    /**
     * `world.current_time_step_index`.
     */
    current_time_step_index(): number;
    /**
     * `articulation.dof_names` (property).
     */
    dof_names(handle: number): string[];
    /**
     * `articulation.get_joint_positions()` → `[n_dof]`.
     */
    get_joint_positions(handle: number): Float32Array;
    /**
     * `articulation.get_joint_velocities()` → `[n_dof]`.
     */
    get_joint_velocities(handle: number): Float32Array;
    /**
     * `world.get_physics_dt()`.
     */
    get_physics_dt(): number;
    /**
     * `RigidPrimView.get_world_poses(link)` → `[px,py,pz, qw,qx,qy,qz]` (7
     * floats), or an empty array if the link/handle is unknown.
     */
    get_world_pose(handle: number, link_name: string): Float32Array;
    /**
     * `new IsaacWorldHandle(physicsDt)` ~ `isaacsim.core.api.World(physics_dt=...)`.
     */
    constructor(physics_dt: number);
    /**
     * `articulation.num_dof` (property).
     */
    num_dof(handle: number): number;
    /**
     * `world.reset()` — zero all registered articulations' joint state.
     */
    reset(): void;
    /**
     * `controller.set_gains(kps, kds)`.
     */
    set_gains(handle: number, kps: Float32Array, kds: Float32Array): void;
    /**
     * `articulation.set_joint_efforts(efforts)`.
     */
    set_joint_efforts(handle: number, efforts: Float32Array): void;
    /**
     * `articulation.set_joint_positions(positions)` — seed/teleport.
     */
    set_joint_positions(handle: number, positions: Float32Array): void;
    /**
     * `articulation.set_joint_velocities(velocities)`.
     */
    set_joint_velocities(handle: number, velocities: Float32Array): void;
    /**
     * `controller.set_max_efforts(max_efforts)`.
     */
    set_max_efforts(handle: number, max_efforts: Float32Array): void;
    /**
     * `world.step(render=False)` — advance physics by one `physics_dt`.
     */
    step(): void;
}

/**
 * `kamiIsaacSimWasmVersion()` — version banner for HUD/audit strings.
 */
export function kamiIsaacSimWasmVersion(): string;

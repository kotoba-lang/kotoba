// kami-genesis cartpole_step.wgsl — vectorized Cartpole semi-implicit Euler.
//
// Mirrors kami_genesis::cartpole::CartpoleState::step formula-for-formula.
// One workgroup invocation = one environment. 64 envs per workgroup;
// dispatch ceil(num_envs / 64, 1, 1) groups.
//
// Layout binding(0): read-write storage buffer of CartpoleState records
// Layout binding(1): read storage buffer of per-env action (force_on_cart)
// Layout binding(2): read uniform CartpoleConfig

struct State {
    x:         f32,
    x_dot:     f32,
    theta:     f32,
    theta_dot: f32,
};

struct Cfg {
    cart_mass:        f32,
    pole_mass:        f32,
    pole_half_length: f32,
    gravity:          f32,
    force_mag:        f32,
    dt:               f32,
    num_envs:         u32,
    _pad:             u32,
};

@group(0) @binding(0) var<storage, read_write> states: array<State>;
@group(0) @binding(1) var<storage, read>       actions: array<f32>;
@group(0) @binding(2) var<uniform>             cfg: Cfg;

@compute @workgroup_size(64)
fn step_main(@builtin(global_invocation_id) gid: vec3<u32>) {
    let i = gid.x;
    if (i >= cfg.num_envs) {
        return;
    }

    var s: State = states[i];
    let raw_force: f32 = actions[i];
    let force: f32 = clamp(raw_force, -cfg.force_mag, cfg.force_mag);

    let sin_t: f32 = sin(s.theta);
    let cos_t: f32 = cos(s.theta);
    let total_mass: f32 = cfg.cart_mass + cfg.pole_mass;
    let pml: f32 = cfg.pole_mass * cfg.pole_half_length;

    // Sutton & Barto 1983 cartpole equations:
    let temp: f32 = (force + pml * s.theta_dot * s.theta_dot * sin_t) / total_mass;
    let theta_acc: f32 =
        (cfg.gravity * sin_t - cos_t * temp)
        / (cfg.pole_half_length * (4.0 / 3.0 - cfg.pole_mass * cos_t * cos_t / total_mass));
    let x_acc: f32 = temp - pml * theta_acc * cos_t / total_mass;

    // Semi-implicit Euler:
    s.x_dot     = s.x_dot     + cfg.dt * x_acc;
    s.x         = s.x         + cfg.dt * s.x_dot;
    s.theta_dot = s.theta_dot + cfg.dt * theta_acc;
    s.theta     = s.theta     + cfg.dt * s.theta_dot;

    states[i] = s;
}

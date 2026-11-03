// kami-genesis double_pendulum_step.wgsl — vectorized 2-link planar revolute
// chain semi-implicit Euler. Mirrors DoublePendulumState::step formula-for-
// formula. One invocation = one env. 64 envs / workgroup.
//
// Layout:
//   binding(0)  states  : storage<read_write> array<State>
//   binding(1)  torques : storage<read>       array<Torque>  // 2 floats per env
//   binding(2)  cfg     : uniform Cfg

struct State {
    q1:     f32,
    q2:     f32,
    q1_dot: f32,
    q2_dot: f32,
};

struct Torque {
    t1: f32,
    t2: f32,
    _pad0: f32,
    _pad1: f32,
};

struct Cfg {
    m1:           f32,
    m2:           f32,
    l1:           f32,
    l2:           f32,
    gravity:      f32,
    effort_limit: f32,
    dt:           f32,
    num_envs:     u32,
};

@group(0) @binding(0) var<storage, read_write> states:  array<State>;
@group(0) @binding(1) var<storage, read>       torques: array<Torque>;
@group(0) @binding(2) var<uniform>             cfg:     Cfg;

@compute @workgroup_size(64)
fn step_main(@builtin(global_invocation_id) gid: vec3<u32>) {
    let i = gid.x;
    if (i >= cfg.num_envs) { return; }

    var s: State = states[i];
    let tin = torques[i];
    let t1: f32 = clamp(tin.t1, -cfg.effort_limit, cfg.effort_limit);
    let t2: f32 = clamp(tin.t2, -cfg.effort_limit, cfg.effort_limit);

    let lc1: f32 = cfg.l1 * 0.5;
    let lc2: f32 = cfg.l2 * 0.5;
    let i1:  f32 = cfg.m1 * cfg.l1 * cfg.l1 / 12.0;
    let i2:  f32 = cfg.m2 * cfg.l2 * cfg.l2 / 12.0;

    let s2:  f32 = sin(s.q2);
    let c2:  f32 = cos(s.q2);
    let s1:  f32 = sin(s.q1);
    let s12: f32 = sin(s.q1 + s.q2);

    let m11: f32 =
        cfg.m1 * lc1 * lc1
        + cfg.m2 * (cfg.l1 * cfg.l1 + lc2 * lc2 + 2.0 * cfg.l1 * lc2 * c2)
        + i1 + i2;
    let m12: f32 = cfg.m2 * (lc2 * lc2 + cfg.l1 * lc2 * c2) + i2;
    let m22: f32 = cfg.m2 * lc2 * lc2 + i2;

    let h:   f32 = -cfg.m2 * cfg.l1 * lc2 * s2;
    let c_1: f32 = h * s.q2_dot * (2.0 * s.q1_dot + s.q2_dot);
    let c_2: f32 = -h * s.q1_dot * s.q1_dot;

    let g1: f32 = (cfg.m1 * lc1 + cfg.m2 * cfg.l1) * cfg.gravity * s1
        + cfg.m2 * lc2 * cfg.gravity * s12;
    let g2: f32 = cfg.m2 * lc2 * cfg.gravity * s12;

    let b1:  f32 = t1 - c_1 - g1;
    let b2:  f32 = t2 - c_2 - g2;
    let det: f32 = m11 * m22 - m12 * m12;
    let q1_acc: f32 = (m22 * b1 - m12 * b2) / det;
    let q2_acc: f32 = (-m12 * b1 + m11 * b2) / det;

    // Semi-implicit Euler
    s.q1_dot = s.q1_dot + cfg.dt * q1_acc;
    s.q1     = s.q1     + cfg.dt * s.q1_dot;
    s.q2_dot = s.q2_dot + cfg.dt * q2_acc;
    s.q2     = s.q2     + cfg.dt * s.q2_dot;

    states[i] = s;
}

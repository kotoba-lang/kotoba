// kami-genesis planar_chain_step.wgsl — GENERAL N-link planar articulation
// forward dynamics on the GPU (one environment per invocation).
//
// Mirrors kami_genesis::planar_chain formula-for-formula: RNEA bias + CRBA mass
// matrix + LDLᵀ solve + semi-implicit Euler. Generalizes the hand-coded
// cartpole / double-pendulum GPU kernels to an arbitrary serial chain (N ≤ 7,
// enough for a Franka-class 7-DoF arm) — the "general articulation on GPU" step.
//
// Layout (env-strided, n = cfg.n active joints):
//   binding 0 (rw storage): state[num_envs * 2n] = per env [q(n), qdot(n)]
//   binding 1 (ro storage):  torque[num_envs * n]
//   binding 2 (uniform):     Cfg { n, gravity, dt, effort_limit }
//   binding 3 (ro storage):  params[2*MAXN] = [lengths(MAXN), masses(MAXN)]

const MAXN: u32 = 7u;

struct Cfg {
    n: u32,
    gravity: f32,
    dt: f32,
    effort_limit: f32,
};

@group(0) @binding(0) var<storage, read_write> state: array<f32>;
@group(0) @binding(1) var<storage, read>       torque: array<f32>;
@group(0) @binding(2) var<uniform>             cfg: Cfg;
@group(0) @binding(3) var<storage, read>       params: array<f32>;

// Recursive Newton–Euler for a single-axis planar chain (uniform-rod links).
fn rnea(q: array<f32, 7>, qdot: array<f32, 7>, qddot: array<f32, 7>, n: u32, g: f32) -> array<f32, 7> {
    var theta: array<f32, 7>;
    var omega: array<f32, 7>;
    var alpha: array<f32, 7>;
    var a_com_x: array<f32, 7>;
    var a_com_z: array<f32, 7>;
    var p_com_x: array<f32, 7>;
    var p_com_z: array<f32, 7>;
    var p_joint_x: array<f32, 8>;
    var p_joint_z: array<f32, 8>;
    p_joint_x[0] = 0.0;
    p_joint_z[0] = 0.0;

    var cum_theta = 0.0;
    var cum_omega = 0.0;
    var cum_alpha = 0.0;
    var prev_pjx = 0.0;
    var prev_pjz = 0.0;
    var prev_ajx = 0.0;
    var prev_ajz = 0.0;
    for (var i = 0u; i < n; i = i + 1u) {
        cum_theta = cum_theta + q[i];
        cum_omega = cum_omega + qdot[i];
        cum_alpha = cum_alpha + qddot[i];
        theta[i] = cum_theta;
        omega[i] = cum_omega;
        alpha[i] = cum_alpha;
        let s = sin(cum_theta);
        let c = cos(cum_theta);
        let l = params[i];
        let lc = l * 0.5;
        p_com_x[i] = prev_pjx + lc * s;
        p_com_z[i] = prev_pjz - lc * c;
        a_com_x[i] = prev_ajx + lc * (cum_alpha * c - cum_omega * cum_omega * s);
        a_com_z[i] = prev_ajz + lc * (cum_alpha * s + cum_omega * cum_omega * c);
        let pjnx = prev_pjx + l * s;
        let pjnz = prev_pjz - l * c;
        let ajnx = prev_ajx + l * (cum_alpha * c - cum_omega * cum_omega * s);
        let ajnz = prev_ajz + l * (cum_alpha * s + cum_omega * cum_omega * c);
        p_joint_x[i + 1u] = pjnx;
        p_joint_z[i + 1u] = pjnz;
        prev_pjx = pjnx;
        prev_pjz = pjnz;
        prev_ajx = ajnx;
        prev_ajz = ajnz;
    }

    var tau_out: array<f32, 7>;
    for (var i = 0u; i < n; i = i + 1u) {
        var tau_i = 0.0;
        for (var k = i; k < n; k = k + 1u) {
            let m = params[7u + k];
            let lk = params[k];
            let i_com = m * lk * lk / 12.0;
            let f_x = m * a_com_x[k];
            let f_z = m * (a_com_z[k] + g);
            let r_x = p_com_x[k] - p_joint_x[i];
            let r_z = p_com_z[k] - p_joint_z[i];
            let torque_q = r_x * f_z - r_z * f_x;
            tau_i = tau_i + torque_q + i_com * alpha[k];
        }
        tau_out[i] = tau_i;
    }
    return tau_out;
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
    let n = cfg.n;
    let stride = 2u * n;
    let num = arrayLength(&state) / stride;
    let eid = gid.x;
    if (eid >= num) {
        return;
    }
    let sb = eid * stride;
    let tb = eid * n;

    var q: array<f32, 7>;
    var qd: array<f32, 7>;
    var tau: array<f32, 7>;
    var zero: array<f32, 7>;
    for (var i = 0u; i < MAXN; i = i + 1u) {
        zero[i] = 0.0;
    }
    for (var i = 0u; i < n; i = i + 1u) {
        q[i] = state[sb + i];
        qd[i] = state[sb + n + i];
        tau[i] = clamp(torque[tb + i], -cfg.effort_limit, cfg.effort_limit);
    }

    // bias h = RNEA(q, qdot, 0, gravity)
    let h = rnea(q, qd, zero, n, cfg.gravity);

    // M(q) via CRBA: column j = RNEA(q, 0, e_j, gravity = 0)
    var M: array<f32, 49>;
    for (var j = 0u; j < n; j = j + 1u) {
        var e: array<f32, 7>;
        for (var t = 0u; t < MAXN; t = t + 1u) {
            e[t] = 0.0;
        }
        e[j] = 1.0;
        let col = rnea(q, zero, e, n, 0.0);
        for (var i = 0u; i < n; i = i + 1u) {
            M[i * n + j] = col[i];
        }
    }
    // symmetrize
    for (var i = 0u; i < n; i = i + 1u) {
        for (var j = i + 1u; j < n; j = j + 1u) {
            let mean = 0.5 * (M[i * n + j] + M[j * n + i]);
            M[i * n + j] = mean;
            M[j * n + i] = mean;
        }
    }

    // rhs = tau - h
    var rhs: array<f32, 7>;
    for (var i = 0u; i < n; i = i + 1u) {
        rhs[i] = tau[i] - h[i];
    }

    // LDLᵀ factorisation in place on M
    for (var j = 0u; j < n; j = j + 1u) {
        var s = M[j * n + j];
        for (var k = 0u; k < j; k = k + 1u) {
            s = s - M[j * n + k] * M[j * n + k] * M[k * n + k];
        }
        M[j * n + j] = s;
        for (var i = j + 1u; i < n; i = i + 1u) {
            var s2 = M[i * n + j];
            for (var k = 0u; k < j; k = k + 1u) {
                s2 = s2 - M[i * n + k] * M[j * n + k] * M[k * n + k];
            }
            M[i * n + j] = s2 / M[j * n + j];
        }
    }
    // L y = rhs
    var y: array<f32, 7>;
    for (var i = 0u; i < n; i = i + 1u) {
        var s = rhs[i];
        for (var k = 0u; k < i; k = k + 1u) {
            s = s - M[i * n + k] * y[k];
        }
        y[i] = s;
    }
    // D z = y
    var z: array<f32, 7>;
    for (var i = 0u; i < n; i = i + 1u) {
        z[i] = y[i] / M[i * n + i];
    }
    // Lᵀ qdd = z (back substitution)
    var qdd: array<f32, 7>;
    for (var ii = 0u; ii < n; ii = ii + 1u) {
        let i = n - 1u - ii;
        var s = z[i];
        for (var k = i + 1u; k < n; k = k + 1u) {
            s = s - M[k * n + i] * qdd[k];
        }
        qdd[i] = s;
    }

    // semi-implicit Euler
    for (var i = 0u; i < n; i = i + 1u) {
        qd[i] = qd[i] + cfg.dt * qdd[i];
        q[i] = q[i] + cfg.dt * qd[i];
    }
    for (var i = 0u; i < n; i = i + 1u) {
        state[sb + i] = q[i];
        state[sb + n + i] = qd[i];
    }
}

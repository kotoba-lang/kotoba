(ns kotoba.lang.kami-nv-compat.warp.examples
  "Reference WGSL+JS kernel pairs that exercise the wgpu-launch path —
  portable .cljc port of src/warp/examples.ts. These are pedagogical
  examples — they prove the architectural pattern: a kernel author writes
  both a Clojure implementation (for the sync `warp.warp/launch` path and as
  the WebGPU CPU fallback) and a WGSL compute shader (for actual GPU
  dispatch via `warp.wgpu-backend/wgpu-launch`). The runtime picks WGSL when
  a WebGPU device is available.

  Each kernel is `wgpu/wgpu-kernel {:js :wgsl :bindings :workgroup-size}` —
  the WGSL string is unchanged verbatim from the TS source (pure portable
  data, same treatment as kami-rt.wgsl-shaders); the :js function is an
  algorithm-for-algorithm port of the TS `js:` lambda using warp.warp's
  tid/wp-get/wp-set/sin/cos, with the exact same positional argument order
  (which the :bindings' :input-index fields also key off).

  Ported across multiple waves rather than one pass (~2500 LOC / 34 exports
  across 16 WgpuKernels + 18 CPU-reference \"Inline\" functions). Wave 45:
  the 3 self-contained physics-step kernels (damping, pendulum, cartpole)
  with no \"Inline\" companion. Wave 46: two-link-arm-step-kernel — a
  closed-form 2-DoF planar arm (M(q)*q_ddot + C*q_dot + g(q) = tau, 2x2
  matrix inverse by hand); also no \"Inline\" companion. Wave 47:
  franka-fk-kernel + franka-fk-inline — the first of 4 Franka-arm kernels
  (FK is the foundation the Jacobian/reach/gravity-comp kernels build on,
  each its own later wave). franka-fk-inline is deliberately self-contained
  (own private rot-rpy/rot-z/mat3-mul-small/matvec3-small helpers) rather
  than routing through dynamics.articulated-dynamics — matches the TS
  source's own structure, which needs the same standalone-compilable-as-
  WGSL property every kernel here has; the joint xyz/rpy data matches
  assets.franka-panda's URDF origins (same canonical source).

  Note: cartpole-step-kernel's semi-implicit-Euler integration order
  (compute the NEW velocity, then integrate position using that NEW
  velocity) is a genuinely different algorithm from e7m-shugyo.cartpole's
  cartpole-step (explicit Euler: integrate position using the OLD
  velocity) — these are separate reference implementations for separate
  purposes (a GPU-kernel exemplar vs. the Isaac Lab Cartpole RL env), not
  duplicates; verified by inspection, not unified/deduped."
  (:require [kotoba.lang.kami-nv-compat.warp.warp :as wp]
            [kotoba.lang.kami-nv-compat.warp.wgpu-backend :as wgpu]))

;; ── Damping kernel: multiply each element of an array by a scalar ────────
;;
;; Bindings:
;;   @group(0) @binding(0) = WpArray<number> (storage, read_write)
;;   @group(0) @binding(1) = scalar damping (uniform)
;; Workgroup size 64 matches the kami-cartpole-wasm precedent.

(def damping-kernel
  (wgpu/wgpu-kernel
    {:js (fn [arr damping]
           (let [i (wp/tid)]
             (wp/wp-set arr i (* (wp/wp-get arr i) damping))))
     :wgsl "
struct DampingUniform {
  damping: f32,
  _pad: vec3<f32>,
};

@group(0) @binding(0) var<storage, read_write> arr: array<f32>;
@group(0) @binding(1) var<uniform> uni: DampingUniform;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = gid.x;
  if (i >= arrayLength(&arr)) {
    return;
  }
  arr[i] = arr[i] * uni.damping;
}
"
     :bindings [(wgpu/storage-binding 0 0)
                (wgpu/uniform-binding 1 1)]
     :workgroup-size 64}))

;; ── Pendulum semi-implicit Euler step (env-parallel) ──────────────────────
;;
;; Mirrors the iter 71 single-pendulum integrator stepped across N envs in
;; parallel. Per-env state: theta (angle), omega (angular velocity).
;; Per-env input: tau (applied torque). Uniform params: dt, g, length
;; (COM distance from pivot), mass.
;;
;; Dynamics: tau_total = tau_applied - m*g*L*sin(theta); alpha = tau_total / (m*L^2)
;; Semi-implicit Euler: omega' = omega + dt*alpha; theta' = theta + dt*omega'
;;
;; At equilibrium (theta=0, omega=0, tau=0): alpha=0, no drift.
;; At theta=pi/2, omega=0, tau=0: alpha = -g*L*sin(pi/2)/(m*L^2) = -g/L ~= -9.81 (m=L=1).
;;
;; Bindings (in order): theta, omega (storage read_write), tau (storage
;; read, writeback false), dt, g, length, mass (uniform).

(def pendulum-step-kernel
  (wgpu/wgpu-kernel
    {:js (fn [theta omega tau dt g length mass]
           (let [i     (wp/tid)
                 t     (wp/wp-get theta i)
                 w     (wp/wp-get omega i)
                 tor   (wp/wp-get tau i)
                 alpha (/ (- tor (* mass g length (wp/sin t))) (* mass length length))
                 w-new (+ w (* dt alpha))
                 t-new (+ t (* dt w-new))]
             (wp/wp-set omega i w-new)
             (wp/wp-set theta i t-new)))
     :wgsl "
@group(0) @binding(0) var<storage, read_write> theta:  array<f32>;
@group(0) @binding(1) var<storage, read_write> omega:  array<f32>;
@group(0) @binding(2) var<storage, read_write> tau:    array<f32>;
@group(0) @binding(3) var<uniform>             dt_u:     vec4<f32>;
@group(0) @binding(4) var<uniform>             g_u:      vec4<f32>;
@group(0) @binding(5) var<uniform>             length_u: vec4<f32>;
@group(0) @binding(6) var<uniform>             mass_u:   vec4<f32>;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = gid.x;
  if (i >= arrayLength(&theta)) {
    return;
  }
  let t = theta[i];
  let w = omega[i];
  let tor = tau[i];
  let dt = dt_u.x;
  let g = g_u.x;
  let L = length_u.x;
  let m = mass_u.x;
  let alpha = (tor - m * g * L * sin(t)) / (m * L * L);
  let w_new = w + dt * alpha;
  let t_new = t + dt * w_new;
  omega[i] = w_new;
  theta[i] = t_new;
}
"
     :bindings [(wgpu/storage-binding 0 0)
                (wgpu/storage-binding 1 1)
                (assoc (wgpu/storage-binding 2 2) :writeback false)
                (wgpu/uniform-binding 3 3)
                (wgpu/uniform-binding 4 4)
                (wgpu/uniform-binding 5 5)
                (wgpu/uniform-binding 6 6)]
     :workgroup-size 64}))

;; ── Cartpole semi-implicit Euler step (env-parallel) ──────────────────────
;;
;; Mirrors the Python iter 68 _kernel.cartpole_step (Sutton & Barto /
;; OpenAI Gym CartPole-v1 closed-form) stepped across N envs in parallel.
;; 2-DoF coupled dynamics — revolute pole on a prismatic cart.
;;
;; Per-env state: x, x_dot, theta (from vertical, +theta = pole leans +x),
;; theta_dot. Per-env input: force (caller clamps; this kernel does not).
;; Uniform params: dt, gravity, cart_mass, pole_mass, pole_half_length.
;;
;; Closed-form (Sutton & Barto):
;;   temp = (force + m_pole*L*theta_dot^2*sin(theta)) / total_mass
;;   theta_acc = (g*sin(theta) - cos(theta)*temp) / (L*(4/3 - m_pole*cos(theta)^2/total_mass))
;;   x_acc = temp - m_pole*L*theta_acc*cos(theta) / total_mass
;; Semi-implicit Euler: velocities update first, then positions integrate
;; using the NEW velocities.
;;
;; Bindings (10 total): x, x_dot, theta, theta_dot (storage read_write),
;; force (storage read, writeback false), dt, gravity, cart_mass, pole_mass,
;; pole_half_length (uniform).

(def cartpole-step-kernel
  (wgpu/wgpu-kernel
    {:js (fn [x x-dot theta theta-dot force dt gravity cart-mass pole-mass pole-half-length]
           (let [i          (wp/tid)
                 t          (wp/wp-get theta i)
                 td         (wp/wp-get theta-dot i)
                 xd         (wp/wp-get x-dot i)
                 f          (wp/wp-get force i)
                 sin-t      (wp/sin t)
                 cos-t      (wp/cos t)
                 total-mass (+ cart-mass pole-mass)
                 pml        (* pole-mass pole-half-length)
                 temp       (/ (+ f (* pml td td sin-t)) total-mass)
                 theta-acc  (/ (- (* gravity sin-t) (* cos-t temp))
                                (* pole-half-length (- (/ 4.0 3.0) (/ (* pole-mass cos-t cos-t) total-mass))))
                 x-acc      (- temp (/ (* pml theta-acc cos-t) total-mass))
                 x-dot-new  (+ xd (* dt x-acc))
                 x-new      (+ (wp/wp-get x i) (* dt x-dot-new))
                 theta-dot-new (+ td (* dt theta-acc))
                 theta-new  (+ t (* dt theta-dot-new))]
             (wp/wp-set x-dot i x-dot-new)
             (wp/wp-set x i x-new)
             (wp/wp-set theta-dot i theta-dot-new)
             (wp/wp-set theta i theta-new)))
     :wgsl "
@group(0) @binding(0) var<storage, read_write> x:         array<f32>;
@group(0) @binding(1) var<storage, read_write> x_dot:     array<f32>;
@group(0) @binding(2) var<storage, read_write> theta:     array<f32>;
@group(0) @binding(3) var<storage, read_write> theta_dot: array<f32>;
@group(0) @binding(4) var<storage, read_write> force:     array<f32>;
@group(0) @binding(5) var<uniform>             dt_u:      vec4<f32>;
@group(0) @binding(6) var<uniform>             g_u:       vec4<f32>;
@group(0) @binding(7) var<uniform>             cm_u:      vec4<f32>;
@group(0) @binding(8) var<uniform>             pm_u:      vec4<f32>;
@group(0) @binding(9) var<uniform>             L_u:       vec4<f32>;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = gid.x;
  if (i >= arrayLength(&theta)) {
    return;
  }
  let t = theta[i];
  let td = theta_dot[i];
  let xd = x_dot[i];
  let f = force[i];
  let dt = dt_u.x;
  let g = g_u.x;
  let cart_mass = cm_u.x;
  let pole_mass = pm_u.x;
  let L = L_u.x;
  let sinT = sin(t);
  let cosT = cos(t);
  let totalMass = cart_mass + pole_mass;
  let pml = pole_mass * L;
  let temp = (f + pml * td * td * sinT) / totalMass;
  let theta_acc = (g * sinT - cosT * temp) /
                    (L * (4.0 / 3.0 - pole_mass * cosT * cosT / totalMass));
  let x_acc = temp - pml * theta_acc * cosT / totalMass;
  let xDotNew = xd + dt * x_acc;
  let xNew = x[i] + dt * xDotNew;
  let thetaDotNew = td + dt * theta_acc;
  let thetaNew = t + dt * thetaDotNew;
  x_dot[i] = xDotNew;
  x[i] = xNew;
  theta_dot[i] = thetaDotNew;
  theta[i] = thetaNew;
}
"
     :bindings [(wgpu/storage-binding 0 0)
                (wgpu/storage-binding 1 1)
                (wgpu/storage-binding 2 2)
                (wgpu/storage-binding 3 3)
                (assoc (wgpu/storage-binding 4 4) :writeback false)
                (wgpu/uniform-binding 5 5)
                (wgpu/uniform-binding 6 6)
                (wgpu/uniform-binding 7 7)
                (wgpu/uniform-binding 8 8)
                (wgpu/uniform-binding 9 9)]
     :workgroup-size 64}))

;; ── Two-link arm step (env-parallel) ──────────────────────────────────────
;;
;; Closed-form 2-DoF planar arm dynamics — both joints revolute about world
;; Y-axis, both links pendulum-like (gravity pulls toward -Z). Standard
;; manipulator equation M(q)*q_ddot + C(q,q_dot)*q_dot + g(q) = tau, inverted
;; by hand (2x2 closed form). Reference: Spong, Robot Modeling & Control,
;; Ch. 7. link1/link2 = [m L r I] (mass, full length, COM offset from joint,
;; inertia about COM); link2's L is unused here (reserved for future
;; tip-frame variants — matches TS's `void L2`, so l2-mass/-r2/-I2 are read
;; but l2-len is simply never bound to a let).
;;
;; Bindings (10 total): theta1, theta1_dot, theta2, theta2_dot (storage
;; read_write), tau1, tau2 (storage read, writeback false), dt, gravity
;; (uniform), link1, link2 (uniform vec4: m, L, r, I).

(def two-link-arm-step-kernel
  (wgpu/wgpu-kernel
    {:js (fn [theta1 theta1-dot theta2 theta2-dot tau1 tau2 dt g
              m1 l1 r1 i1 m2 _l2 r2 i2]
           (let [idx    (wp/tid)
                 q1     (wp/wp-get theta1 idx)
                 q2     (wp/wp-get theta2 idx)
                 dq1    (wp/wp-get theta1-dot idx)
                 dq2    (wp/wp-get theta2-dot idx)
                 t1     (wp/wp-get tau1 idx)
                 t2     (wp/wp-get tau2 idx)
                 a      (+ (* m1 r1 r1) i1 (* m2 l1 l1))
                 b      (+ (* m2 r2 r2) i2)
                 c      (* m2 l1 r2)
                 cos-t2 (wp/cos q2)
                 sin-t2 (wp/sin q2)
                 m11    (+ a b (* 2 c cos-t2))
                 m12    (+ b (* c cos-t2))
                 m22    b
                 h1     (+ (- (* c sin-t2 dq2 dq1))
                           (- (* c sin-t2 (+ dq1 dq2) dq2))
                           (* m1 g r1 (wp/sin q1))
                           (* m2 g (+ (* l1 (wp/sin q1)) (* r2 (wp/sin (+ q1 q2))))))
                 h2     (+ (* c sin-t2 dq1 dq1) (* m2 g r2 (wp/sin (+ q1 q2))))
                 b1     (- t1 h1)
                 b2     (- t2 h2)
                 det    (- (* m11 m22) (* m12 m12))
                 ddq1   (/ (- (* m22 b1) (* m12 b2)) det)
                 ddq2   (/ (- (* m11 b2) (* m12 b1)) det)
                 dq1-new (+ dq1 (* dt ddq1))
                 dq2-new (+ dq2 (* dt ddq2))]
             (wp/wp-set theta1-dot idx dq1-new)
             (wp/wp-set theta1 idx (+ q1 (* dt dq1-new)))
             (wp/wp-set theta2-dot idx dq2-new)
             (wp/wp-set theta2 idx (+ q2 (* dt dq2-new)))))
     :wgsl "
@group(0) @binding(0)  var<storage, read_write> theta1:     array<f32>;
@group(0) @binding(1)  var<storage, read_write> theta1_dot: array<f32>;
@group(0) @binding(2)  var<storage, read_write> theta2:     array<f32>;
@group(0) @binding(3)  var<storage, read_write> theta2_dot: array<f32>;
@group(0) @binding(4)  var<storage, read_write> tau1:       array<f32>;
@group(0) @binding(5)  var<storage, read_write> tau2:       array<f32>;
@group(0) @binding(6)  var<uniform>             dt_u:       vec4<f32>;
@group(0) @binding(7)  var<uniform>             g_u:        vec4<f32>;
@group(0) @binding(8)  var<uniform>             link1_u:    vec4<f32>;
@group(0) @binding(9)  var<uniform>             link2_u:    vec4<f32>;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = gid.x;
  if (i >= arrayLength(&theta1)) { return; }
  let q1 = theta1[i];
  let q2 = theta2[i];
  let dq1 = theta1_dot[i];
  let dq2 = theta2_dot[i];
  let t1 = tau1[i];
  let t2 = tau2[i];
  let dt = dt_u.x;
  let g  = g_u.x;
  let m1 = link1_u.x; let L1 = link1_u.y; let r1 = link1_u.z; let I1 = link1_u.w;
  let m2 = link2_u.x;                     let r2 = link2_u.z; let I2 = link2_u.w;
  let a = m1 * r1 * r1 + I1 + m2 * L1 * L1;
  let b = m2 * r2 * r2 + I2;
  let c = m2 * L1 * r2;
  let cosT2 = cos(q2);
  let sinT2 = sin(q2);
  let M11 = a + b + 2.0 * c * cosT2;
  let M12 = b + c * cosT2;
  let M22 = b;
  let h1 = -c * sinT2 * dq2 * dq1
           - c * sinT2 * (dq1 + dq2) * dq2
           + m1 * g * r1 * sin(q1)
           + m2 * g * (L1 * sin(q1) + r2 * sin(q1 + q2));
  let h2 =  c * sinT2 * dq1 * dq1
           + m2 * g * r2 * sin(q1 + q2);
  let b1 = t1 - h1;
  let b2 = t2 - h2;
  let det = M11 * M22 - M12 * M12;
  let ddq1 = (M22 * b1 - M12 * b2) / det;
  let ddq2 = (M11 * b2 - M12 * b1) / det;
  let dq1New = dq1 + dt * ddq1;
  let dq2New = dq2 + dt * ddq2;
  theta1_dot[i] = dq1New;
  theta1[i] = q1 + dt * dq1New;
  theta2_dot[i] = dq2New;
  theta2[i] = q2 + dt * dq2New;
}
"
     :bindings [(wgpu/storage-binding 0 0)
                (wgpu/storage-binding 1 1)
                (wgpu/storage-binding 2 2)
                (wgpu/storage-binding 3 3)
                (assoc (wgpu/storage-binding 4 4) :writeback false)
                (assoc (wgpu/storage-binding 5 5) :writeback false)
                (wgpu/uniform-binding 6 6)
                (wgpu/uniform-binding 7 7)
                (wgpu/uniform-binding 8 8)
                (wgpu/uniform-binding 9 9)]
     :workgroup-size 64}))

;; ── Franka 7-DoF forward kinematics (env-parallel) ────────────────────────
;;
;; Computes EE position for N envs in parallel from per-env q[7]. Real
;; Franka FCI joint origins (matching assets/franka-panda's URDF xyz/rpy
;; data — same canonical source, but this is a lightweight, self-contained
;; FK loop rather than routing through the heavier dynamics.articulated-
;; dynamics machinery; algorithm-for-algorithm port of the TS kernel, which
;; is deliberately self-contained so it also compiles standalone as WGSL).
;;
;; Storage layout (struct-of-arrays for coalesced GPU access):
;;   q-in:   length 7*N — q[i] = q-in[env*7 + i]
;;   ee-out: length 3*N — ee[i] = ee-out[env*3 + i]
;;
;; Algorithm: 7 successive frame compositions. Each joint applies
;;   R_origin (from URDF rpy) . Rodrigues(axis_body_z, q_i)
;; to the cumulative world-frame rotation, plus xyz translation.
;;
;; Bindings: q-in (storage read, N*7 floats, writeback false), ee-out
;; (storage read_write, N*3 floats).

(def ^:private franka-fk-half-pi (/ Math/PI 2))

(def ^:private franka-fk-xyz
  [[0 0 0.333]
   [0 0 0]
   [0 -0.316 0]
   [0.0825 0 0]
   [-0.0825 0.384 0]
   [0 0 0]
   [0.088 0 0]])

(def ^:private franka-fk-rpy-r
  [0 (- franka-fk-half-pi) franka-fk-half-pi franka-fk-half-pi
   (- franka-fk-half-pi) franka-fk-half-pi franka-fk-half-pi])

(defn- rot-rpy
  "p=y=0 for every Franka joint origin, so only the x-rotation term survives."
  [r]
  (let [cr (wp/cos r) sr (wp/sin r)]
    [[1 0 0] [0 cr (- sr)] [0 sr cr]]))

(defn- rot-z [angle]
  (let [c (wp/cos angle) s (wp/sin angle)]
    [[c (- s) 0] [s c 0] [0 0 1]]))

(defn- mat3-mul-small [a b]
  (vec (for [i (range 3)]
         (vec (for [j (range 3)]
                (reduce + (for [k (range 3)] (* (get-in a [i k]) (get-in b [k j])))))))))

(defn- matvec3-small [m v]
  [(+ (* (get-in m [0 0]) (v 0)) (* (get-in m [0 1]) (v 1)) (* (get-in m [0 2]) (v 2)))
   (+ (* (get-in m [1 0]) (v 0)) (* (get-in m [1 1]) (v 1)) (* (get-in m [1 2]) (v 2)))
   (+ (* (get-in m [2 0]) (v 0)) (* (get-in m [2 1]) (v 1)) (* (get-in m [2 2]) (v 2)))])

(defn franka-fk-inline
  "Reference Franka 7-DoF FK in pure Clojure — used by the kernel's :js
  fallback AND callable directly for cross-validation. Returns the
  world-frame EE position [x y z] from q (a 7-element seq of joint angles)."
  [q]
  (loop [i 0 r-world [[1 0 0] [0 1 0] [0 0 1]] p-world [0.0 0.0 0.0]]
    (if (>= i 7)
      p-world
      (let [r-origin (rot-rpy (franka-fk-rpy-r i))
            r-q      (rot-z (nth q i))
            r-i-in-p (mat3-mul-small r-origin r-q)
            rotated  (matvec3-small r-world (franka-fk-xyz i))
            p-world' (vec (map + p-world rotated))
            r-world' (mat3-mul-small r-world r-i-in-p)]
        (recur (inc i) r-world' p-world')))))

(def franka-fk-kernel
  (wgpu/wgpu-kernel
    {:js (fn [q-in ee-out]
           (let [env (wp/tid)
                 q   (vec (for [j (range 7)] (wp/wp-get q-in (+ (* env 7) j))))
                 ee  (franka-fk-inline q)]
             (wp/wp-set ee-out (+ (* env 3) 0) (ee 0))
             (wp/wp-set ee-out (+ (* env 3) 1) (ee 1))
             (wp/wp-set ee-out (+ (* env 3) 2) (ee 2))))
     :wgsl "
// Real Franka FCI joint origins (xyz triplet + rpy triplet per joint).
// Pre-computed: cos/sin of rpy values inlined as constants for speed.
// rpy values: (0,0,0), (-pi/2,0,0), (pi/2,0,0), (pi/2,0,0), (-pi/2,0,0), (pi/2,0,0), (pi/2,0,0)

@group(0) @binding(0) var<storage, read_write> q_in:    array<f32>;
@group(0) @binding(1) var<storage, read_write> ee_out:  array<f32>;

// Composed rotation R_world (3x3) stored row-major in 9 f32 locals.
// p_world stored in 3 f32 locals.
// Applies R_world <- R_world . R_origin . R_q (axis z, angle q[i])
// and p_world <- p_world + R_world_pre . xyz.

fn rot_rpy(r: f32, p: f32, y: f32) -> mat3x3<f32> {
  let cr = cos(r); let sr = sin(r);
  let cp = cos(p); let sp = sin(p);
  let cy = cos(y); let sy = sin(y);
  return mat3x3<f32>(
    vec3<f32>(cy*cp, sy*cp, -sp),
    vec3<f32>(cy*sp*sr - sy*cr, sy*sp*sr + cy*cr, cp*sr),
    vec3<f32>(cy*sp*cr + sy*sr, sy*sp*cr - cy*sr, cp*cr),
  );
}

fn rot_z(angle: f32) -> mat3x3<f32> {
  let c = cos(angle); let s = sin(angle);
  return mat3x3<f32>(
    vec3<f32>(c, s, 0.0),
    vec3<f32>(-s, c, 0.0),
    vec3<f32>(0.0, 0.0, 1.0),
  );
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let env = gid.x;
  let n_envs = arrayLength(&ee_out) / 3u;
  if (env >= n_envs) { return; }

  let base = env * 7u;
  let q = array<f32, 7>(
    q_in[base + 0u], q_in[base + 1u], q_in[base + 2u], q_in[base + 3u],
    q_in[base + 4u], q_in[base + 5u], q_in[base + 6u],
  );

  let half_pi: f32 = 1.5707963267948966;
  // Joint origins: xyz vec3 + rpy.r (rpy.p, rpy.y are 0 for all Franka joints)
  let xyz = array<vec3<f32>, 7>(
    vec3<f32>(0.0,      0.0,     0.333),
    vec3<f32>(0.0,      0.0,     0.0),
    vec3<f32>(0.0,     -0.316,   0.0),
    vec3<f32>(0.0825,   0.0,     0.0),
    vec3<f32>(-0.0825,  0.384,   0.0),
    vec3<f32>(0.0,      0.0,     0.0),
    vec3<f32>(0.088,    0.0,     0.0),
  );
  let rpy_r = array<f32, 7>(
    0.0,
    -half_pi,
    half_pi,
    half_pi,
    -half_pi,
    half_pi,
    half_pi,
  );

  var R_world = mat3x3<f32>(
    vec3<f32>(1.0, 0.0, 0.0),
    vec3<f32>(0.0, 1.0, 0.0),
    vec3<f32>(0.0, 0.0, 1.0),
  );
  var p_world = vec3<f32>(0.0, 0.0, 0.0);

  for (var i = 0u; i < 7u; i = i + 1u) {
    let R_origin = rot_rpy(rpy_r[i], 0.0, 0.0);
    let R_q = rot_z(q[i]);
    let R_iInP = R_origin * R_q;
    // p contribution: rotated xyz, in current world frame (before this
    // joint's rotation).
    let rotated = R_world * xyz[i];
    p_world = p_world + rotated;
    R_world = R_world * R_iInP;
  }

  ee_out[env * 3u + 0u] = p_world.x;
  ee_out[env * 3u + 1u] = p_world.y;
  ee_out[env * 3u + 2u] = p_world.z;
}
"
     :bindings [(assoc (wgpu/storage-binding 0 0) :writeback false)
                (wgpu/storage-binding 1 1)]
     :workgroup-size 64}))

;; ── PD joint controller (env×joint parallel) ──────────────────────────────
;;
;; tau[i] = Kp[i % n] * (q*[i] - q[i]) - Kd[i % n] * qdot[i]
;;
;; Per-(env,joint) state: q_actual, qd_actual (measured); q_target (desired).
;; Per-joint gains kp, kd shared across envs (n = joints/env; idx % n picks
;; the joint). Canonical Isaac Lab / Isaac Gym PD actuator model — sits
;; between the action pipeline (action-scale-clamp-kernel below) and effort
;; saturation (effort-limit-kernel below).
;;
;; Bindings (7 total): q_actual, qd_actual, q_target, kp, kd (storage read,
;; writeback false), tau_out (storage read_write), n (uniform).

(def pd-joint-controller-kernel
  (wgpu/wgpu-kernel
    {:js (fn [q-actual qd-actual q-target kp kd tau-out n]
           (let [idx   (wp/tid)
                 j     (mod idx n)
                 q-err (- (wp/wp-get q-target idx) (wp/wp-get q-actual idx))
                 tau   (- (* (wp/wp-get kp j) q-err) (* (wp/wp-get kd j) (wp/wp-get qd-actual idx)))]
             (wp/wp-set tau-out idx tau)))
     :wgsl "
@group(0) @binding(0) var<storage, read_write> q_actual:  array<f32>;
@group(0) @binding(1) var<storage, read_write> qd_actual: array<f32>;
@group(0) @binding(2) var<storage, read_write> q_target:  array<f32>;
@group(0) @binding(3) var<storage, read_write> kp:        array<f32>;
@group(0) @binding(4) var<storage, read_write> kd:        array<f32>;
@group(0) @binding(5) var<storage, read_write> tau_out:   array<f32>;
@group(0) @binding(6) var<uniform>             n_uniform: vec4<u32>;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let idx = gid.x;
  let total = arrayLength(&tau_out);
  if (idx >= total) { return; }
  let n = n_uniform.x;
  let j = idx % n;
  let q_err = q_target[idx] - q_actual[idx];
  tau_out[idx] = kp[j] * q_err - kd[j] * qd_actual[idx];
}
"
     :bindings [(assoc (wgpu/storage-binding 0 0) :writeback false)
                (assoc (wgpu/storage-binding 1 1) :writeback false)
                (assoc (wgpu/storage-binding 2 2) :writeback false)
                (assoc (wgpu/storage-binding 3 3) :writeback false)
                (assoc (wgpu/storage-binding 4 4) :writeback false)
                (wgpu/storage-binding 5 5)
                (wgpu/uniform-binding 6 6)]
     :workgroup-size 64}))

(defn pd-joint-controller-inline
  "Reference PD joint controller in pure Clojure.
  tau[i] = Kp[i % n] * (q*[i] - q[i]) - Kd[i % n] * qdot[i]"
  [q-actual qd-actual q-target kp kd n]
  (vec (for [i (range (count q-actual))]
         (let [j (mod i n)]
           (- (* (nth kp j) (- (nth q-target i) (nth q-actual i)))
              (* (nth kd j) (nth qd-actual i)))))))

;; ── Action scale + clamp (env×joint parallel) ────────────────────────────
;;
;; Isaac Lab's ActionManager canonical pipeline:
;;
;;     q_target[i] = clamp(
;;         action_scale[j] * action[i] + action_offset[j],
;;         q_lower[j], q_upper[j])
;;
;; Sits between the policy net (action in [-1, 1]^N typically tanh-squashed)
;; and the PD controller (pd-joint-controller-kernel above). Per-joint
;; scale/offset/limits are shared across envs (storage), so 1024-env x
;; 12-joint dispatch needs only 48 floats of joint config.
;;
;; Bindings (7 total): action, action_scale, action_offset, q_lower, q_upper
;; (storage read, writeback false), q_target_out (storage read_write), n
;; (uniform).

(def action-scale-clamp-kernel
  (wgpu/wgpu-kernel
    {:js (fn [action action-scale action-offset q-lower q-upper q-target-out n]
           (let [idx (wp/tid)
                 j   (mod idx n)
                 raw (+ (* (wp/wp-get action-scale j) (wp/wp-get action idx))
                        (wp/wp-get action-offset j))
                 lo  (wp/wp-get q-lower j)
                 hi  (wp/wp-get q-upper j)]
             (wp/wp-set q-target-out idx (wp/clamp raw lo hi))))
     :wgsl "
@group(0) @binding(0) var<storage, read_write> action:       array<f32>;
@group(0) @binding(1) var<storage, read_write> action_scale: array<f32>;
@group(0) @binding(2) var<storage, read_write> action_offset:array<f32>;
@group(0) @binding(3) var<storage, read_write> q_lower:      array<f32>;
@group(0) @binding(4) var<storage, read_write> q_upper:      array<f32>;
@group(0) @binding(5) var<storage, read_write> q_target_out: array<f32>;
@group(0) @binding(6) var<uniform>             n_uniform:    vec4<u32>;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let idx = gid.x;
  let total = arrayLength(&q_target_out);
  if (idx >= total) { return; }
  let n = n_uniform.x;
  let j = idx % n;
  let raw = action_scale[j] * action[idx] + action_offset[j];
  q_target_out[idx] = clamp(raw, q_lower[j], q_upper[j]);
}
"
     :bindings [(assoc (wgpu/storage-binding 0 0) :writeback false)
                (assoc (wgpu/storage-binding 1 1) :writeback false)
                (assoc (wgpu/storage-binding 2 2) :writeback false)
                (assoc (wgpu/storage-binding 3 3) :writeback false)
                (assoc (wgpu/storage-binding 4 4) :writeback false)
                (wgpu/storage-binding 5 5)
                (wgpu/uniform-binding 6 6)]
     :workgroup-size 64}))

(defn action-scale-clamp-inline
  "Reference action scale + clamp in pure Clojure."
  [action action-scale action-offset q-lower q-upper n]
  (vec (for [i (range (count action))]
         (let [j   (mod i n)
               raw (+ (* (nth action-scale j) (nth action i)) (nth action-offset j))]
           (wp/clamp raw (nth q-lower j) (nth q-upper j))))))

;; ── Effort saturation (env×joint parallel, in-place) ─────────────────────
;;
;; Canonical safety layer between the PD controller (pd-joint-controller-
;; kernel above) and articulated-body forward dynamics. Caps each joint's
;; torque at its actuator effort limit, matching Isaac Lab's per-joint
;; effort_limit_sim clamp.
;;
;;     tau_i = clamp(tau_i, -effort_limit_j, +effort_limit_j)
;;
;; In-place storage write; per-joint effort_limit shared across envs.
;;
;; Bindings (3 total): tau (storage read_write), effort_limit (storage
;; read, writeback false), n (uniform).

(def effort-limit-kernel
  (wgpu/wgpu-kernel
    {:js (fn [tau effort-limit n]
           (let [idx (wp/tid)
                 j   (mod idx n)
                 lim (wp/wp-get effort-limit j)
                 t   (wp/wp-get tau idx)]
             (wp/wp-set tau idx (wp/clamp t (- lim) lim))))
     :wgsl "
@group(0) @binding(0) var<storage, read_write> tau:          array<f32>;
@group(0) @binding(1) var<storage, read_write> effort_limit: array<f32>;
@group(0) @binding(2) var<uniform>             n_uniform:    vec4<u32>;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let idx = gid.x;
  let total = arrayLength(&tau);
  if (idx >= total) { return; }
  let n = n_uniform.x;
  let j = idx % n;
  let lim = effort_limit[j];
  tau[idx] = clamp(tau[idx], -lim, lim);
}
"
     :bindings [(wgpu/storage-binding 0 0)
                (assoc (wgpu/storage-binding 1 1) :writeback false)
                (wgpu/uniform-binding 2 2)]
     :workgroup-size 64}))

(defn effort-limit-inline
  "Reference effort saturation in pure Clojure. TS mutates `tau` in place and
  returns void; Clojure vectors are immutable, so this returns the clamped
  vector instead (same functional result, idiomatic port)."
  [tau effort-limit n]
  (vec (for [i (range (count tau))]
         (let [j   (mod i n)
               lim (nth effort-limit j)]
           (wp/clamp (nth tau i) (- lim) lim)))))

;; ── Observation normalize + noise + clamp (env×feature parallel) ─────────
;;
;; Isaac Lab's ObservationManager canonical pipeline:
;;
;;     obs[i] = clamp(
;;         (raw[i] - mean[j]) / std[j] + noise[i],
;;         clamp_low[j], clamp_high[j])
;;
;; Host pre-generates noise[i] (Gaussian or any; WGSL has no portable RNG),
;; so the kernel itself is deterministic — the test path can pass zeros to
;; verify the normalize+clamp path independently.
;;
;; Per-feature mean/std/clamp shared across envs (storage); per-(env,
;; feature) noise. Mirror of action-scale-clamp-kernel but on the obs side.
;;
;; Bindings (7 total): obs (storage read_write), mean, std, noise,
;; clamp_low, clamp_high (storage read, writeback false), n (uniform).

(def observation-normalize-kernel
  (wgpu/wgpu-kernel
    {:js (fn [obs mean std noise clamp-low clamp-high n]
           (let [idx        (wp/tid)
                 j          (mod idx n)
                 sigma      (max (wp/wp-get std j) 1e-8)
                 normalized (+ (/ (- (wp/wp-get obs idx) (wp/wp-get mean j)) sigma)
                                (wp/wp-get noise idx))
                 lo         (wp/wp-get clamp-low j)
                 hi         (wp/wp-get clamp-high j)]
             (wp/wp-set obs idx (wp/clamp normalized lo hi))))
     :wgsl "
@group(0) @binding(0) var<storage, read_write> obs:        array<f32>;
@group(0) @binding(1) var<storage, read_write> mean:       array<f32>;
@group(0) @binding(2) var<storage, read_write> std:        array<f32>;
@group(0) @binding(3) var<storage, read_write> noise:      array<f32>;
@group(0) @binding(4) var<storage, read_write> clamp_low:  array<f32>;
@group(0) @binding(5) var<storage, read_write> clamp_high: array<f32>;
@group(0) @binding(6) var<uniform>             n_uniform:  vec4<u32>;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let idx = gid.x;
  let total = arrayLength(&obs);
  if (idx >= total) { return; }
  let n = n_uniform.x;
  let j = idx % n;
  let sigma = max(std[j], 1e-8);
  let normalized = (obs[idx] - mean[j]) / sigma + noise[idx];
  obs[idx] = clamp(normalized, clamp_low[j], clamp_high[j]);
}
"
     :bindings [(wgpu/storage-binding 0 0)
                (assoc (wgpu/storage-binding 1 1) :writeback false)
                (assoc (wgpu/storage-binding 2 2) :writeback false)
                (assoc (wgpu/storage-binding 3 3) :writeback false)
                (assoc (wgpu/storage-binding 4 4) :writeback false)
                (assoc (wgpu/storage-binding 5 5) :writeback false)
                (wgpu/uniform-binding 6 6)]
     :workgroup-size 64}))

(defn observation-normalize-inline
  "Reference observation normalize + noise + clamp in pure Clojure. TS
  mutates `obs` in place and returns void; returns the new vector instead
  (same functional result, idiomatic port)."
  [obs mean std noise clamp-low clamp-high n]
  (vec (for [i (range (count obs))]
         (let [j     (mod i n)
               sigma (max (nth std j) 1e-8)
               v     (+ (/ (- (nth obs i) (nth mean j)) sigma) (nth noise i))]
           (wp/clamp v (nth clamp-low j) (nth clamp-high j))))))

;; ── ANYmal C quadruped forward kinematics (env-parallel) ──────────────────
;;
;; Computes 4 foot positions (LF, LH, RF, RH order) for N envs in parallel
;; from per-env q[12] (3 joints/leg: HAA hip ab/adduction, HFE hip
;; flex/extension, KFE knee flex/extension). Real ANYbotics joint origins
;; (iter 94).
;;
;; Reuses mat3-mul-small/matvec3-small (wave 47) plus a NEW private helper
;; this wave introduces: rot-axis, Rodrigues' rotation matrix about an
;; arbitrary unit axis -- generalises wave 47's rot-z (fixed z-axis only).
;; Angle=0 gives the identity matrix for any axis; a 90-degree rotation
;; about the z-axis takes [1 0 0] to [0 1 0] (right-hand rule, verified
;; against the TS `_rotAxis` reference during porting).
;;
;; Storage layout: q-in length 12*N (3 joints x 4 legs per env), feet-out
;; length 12*N (4 feet x xyz per env).
;;
;; Bindings: q-in (storage read, writeback false), feet-out (storage
;; read_write).

(defn- rot-axis
  "Rodrigues' rotation matrix about an arbitrary unit axis [ax ay az] by
  angle (radians). Port of TS's private `_rotAxis` (the JS-reference
  formula; algebraically identical to the WGSL `rot_axis` function's
  column-vector mat3x3 constructor, just written out row-major here)."
  [axis angle]
  (let [c  (wp/cos angle) s (wp/sin angle) oc (- 1 c)
        ax (axis 0) ay (axis 1) az (axis 2)]
    [[(+ c (* ax ax oc))        (- (* ax ay oc) (* az s))    (+ (* ax az oc) (* ay s))]
     [(+ (* ay ax oc) (* az s)) (+ c (* ay ay oc))            (- (* ay az oc) (* ax s))]
     [(- (* az ax oc) (* ay s)) (+ (* az ay oc) (* ax s))    (+ c (* az az oc))]]))

(def ^:private anymal-joint-axes
  "HAA, HFE, KFE joint axes (body frame), shared by all 4 legs."
  [[1 0 0] [0 1 0] [0 1 0]])

(def ^:private anymal-haa-base
  "Per-leg HAA base attachment point, order LF LH RF RH (real ANYbotics
  origins, iter 94)."
  [[ 0.277  0.116 0.0]
   [-0.277  0.116 0.0]
   [ 0.277 -0.116 0.0]
   [-0.277 -0.116 0.0]])

(def ^:private anymal-hfe-local
  "HFE origin in the HAA frame (canonical, same for all legs)."
  [0 0.0635 0])

(def ^:private anymal-kfe-local
  "KFE origin in the HFE frame (canonical, same for all legs)."
  [0 0.041 -0.317])

(def ^:private anymal-foot-local
  "Foot origin in the KFE frame (canonical, same for all legs)."
  [0 0 -0.317])

(defn anymal-fk-inline
  "Reference ANYmal C foot positions in pure Clojure -- used by
  anymal-fk-kernel's :js fallback AND callable directly for
  cross-validation. q is a 12-element seq of joint angles (3 per leg, legs
  in LF/LH/RF/RH order). Returns 4 foot positions [x y z], one per leg in
  the same order."
  [q]
  (vec
    (for [leg (range 4)]
      (let [r0 [[1 0 0] [0 1 0] [0 0 1]]
            p0 (anymal-haa-base leg)
            ;; HAA joint
            r1 (mat3-mul-small r0 (rot-axis (anymal-joint-axes 0) (nth q (+ (* leg 3) 0))))
            ;; HFE origin (in HAA frame) + joint
            p1 (vec (map + p0 (matvec3-small r1 anymal-hfe-local)))
            r2 (mat3-mul-small r1 (rot-axis (anymal-joint-axes 1) (nth q (+ (* leg 3) 1))))
            ;; KFE origin (in HFE frame) + joint
            p2 (vec (map + p1 (matvec3-small r2 anymal-kfe-local)))
            r3 (mat3-mul-small r2 (rot-axis (anymal-joint-axes 2) (nth q (+ (* leg 3) 2))))
            ;; Foot origin (in KFE frame)
            p3 (vec (map + p2 (matvec3-small r3 anymal-foot-local)))]
        p3))))

(def anymal-fk-kernel
  (wgpu/wgpu-kernel
    {:js (fn [q-in feet-out]
           (let [env  (wp/tid)
                 q    (vec (for [i (range 12)] (wp/wp-get q-in (+ (* env 12) i))))
                 feet (anymal-fk-inline q)]
             (doseq [leg (range 4) k (range 3)]
               (wp/wp-set feet-out (+ (* env 12) (* leg 3) k) (get-in feet [leg k])))))
     :wgsl "
@group(0) @binding(0) var<storage, read_write> q_in:     array<f32>;
@group(0) @binding(1) var<storage, read_write> feet_out: array<f32>;

fn rot_axis(axis: vec3<f32>, angle: f32) -> mat3x3<f32> {
  let c = cos(angle); let s = sin(angle);
  let oc = 1.0 - c;
  let ax = axis.x; let ay = axis.y; let az = axis.z;
  return mat3x3<f32>(
    vec3<f32>(c + ax*ax*oc,        ay*ax*oc + az*s,    az*ax*oc - ay*s),
    vec3<f32>(ax*ay*oc - az*s,     c + ay*ay*oc,        az*ay*oc + ax*s),
    vec3<f32>(ax*az*oc + ay*s,     ay*az*oc - ax*s,    c + az*az*oc),
  );
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let env = gid.x;
  let n_envs = arrayLength(&feet_out) / 12u;
  if (env >= n_envs) { return; }

  let base_q = env * 12u;
  let base_out = env * 12u;

  // Real ANYbotics joint axes (HAA, HFE, KFE per leg).
  let axes = array<vec3<f32>, 3>(
    vec3<f32>(1.0, 0.0, 0.0),    // HAA
    vec3<f32>(0.0, 1.0, 0.0),    // HFE
    vec3<f32>(0.0, 1.0, 0.0),    // KFE
  );

  // Per-leg HAA base attachment (iter 94: real ANYbotics origins).
  // Order: LF, LH, RF, RH
  let haa_base = array<vec3<f32>, 4>(
    vec3<f32>( 0.277,  0.116, 0.0),  // LF
    vec3<f32>(-0.277,  0.116, 0.0),  // LH
    vec3<f32>( 0.277, -0.116, 0.0),  // RF
    vec3<f32>(-0.277, -0.116, 0.0),  // RH
  );

  // Canonical local joint origins (same for all legs).
  let hfe_local = vec3<f32>(0.0, 0.0635, 0.0);     // HFE in HAA frame
  let kfe_local = vec3<f32>(0.0, 0.041, -0.317);   // KFE in HFE frame
  let foot_local = vec3<f32>(0.0, 0.0, -0.317);    // foot in KFE frame

  // 4 legs, processed sequentially within this thread.
  for (var leg = 0u; leg < 4u; leg = leg + 1u) {
    // Start at per-leg HAA attachment point with identity frame.
    var R_world = mat3x3<f32>(
      vec3<f32>(1.0, 0.0, 0.0),
      vec3<f32>(0.0, 1.0, 0.0),
      vec3<f32>(0.0, 0.0, 1.0),
    );
    var p_world = haa_base[leg];
    // HAA joint
    R_world = R_world * rot_axis(axes[0], q_in[base_q + leg * 3u + 0u]);
    // HFE origin + joint
    p_world = p_world + R_world * hfe_local;
    R_world = R_world * rot_axis(axes[1], q_in[base_q + leg * 3u + 1u]);
    // KFE origin + joint
    p_world = p_world + R_world * kfe_local;
    R_world = R_world * rot_axis(axes[2], q_in[base_q + leg * 3u + 2u]);
    // Foot origin
    let foot = p_world + R_world * foot_local;
    feet_out[base_out + leg * 3u + 0u] = foot.x;
    feet_out[base_out + leg * 3u + 1u] = foot.y;
    feet_out[base_out + leg * 3u + 2u] = foot.z;
  }
}
"
     :bindings [(assoc (wgpu/storage-binding 0 0) :writeback false)
                (wgpu/storage-binding 1 1)]
     :workgroup-size 64}))

;; ── Generic serial-chain FK (env-parallel, arbitrary N <= 12) ─────────────
;;
;; Generalises the Franka-specific FK kernel (wave 47) to arbitrary
;; serial-chain revolute arms. Joint origins, rpy, and axes are runtime
;; storage inputs (per-joint), so a single kernel handles Franka (N=7),
;; UR10 (N=6), KUKA iiwa (N=7), Kinova Gen3 (N=7), UR5/UR16, etc. Max N=12
;; is a WGSL-loop-bound compile-time cap; the CLJC/JS fallback has no such
;; cap -- it simply loops q's actual length.
;;
;; Per-env input: q[N]. Robot-config storage: xyz[N*3] + rpy[N*3] +
;; axis[N*3]. Uniform: n (joint count). Per-env output: ee-pos[3].
;;
;; Algorithm: same R_origin . R_axis(q) frame composition as franka-fk, but
;; the origin rotation uses the FULL 3-DOF rot-rpy-full (a genuinely
;; different formula from wave 47's simplified rot-rpy, which assumes
;; pitch=yaw=0 and is Franka-specific -- not reused/conflated here) and the
;; joint axis is a runtime per-joint input, so rot-axis replaces rot-z.
;;
;; Bindings: q-in, joint-xyz, joint-rpy, joint-axis (storage read, writeback
;; false), ee-out (storage read_write), n (uniform).

(defn- rot-rpy-full
  "Full 3-DOF roll-pitch-yaw rotation matrix. Unlike wave 47's rot-rpy
  (Franka-specific: assumes pitch=yaw=0 for every joint origin, so only the
  x-rotation term survives), this handles all three angles -- genuinely
  different formula, not a drop-in replacement for rot-rpy and vice versa."
  [rpy]
  (let [r  (rpy 0) p (rpy 1) y (rpy 2)
        cr (wp/cos r) sr (wp/sin r)
        cp (wp/cos p) sp (wp/sin p)
        cy (wp/cos y) sy (wp/sin y)]
    [[(* cy cp) (- (* cy sp sr) (* sy cr)) (+ (* cy sp cr) (* sy sr))]
     [(* sy cp) (+ (* sy sp sr) (* cy cr)) (- (* sy sp cr) (* cy sr))]
     [(- sp)    (* cp sr)                  (* cp cr)]]))

(defn generic-serial-fk-inline
  "Reference generic serial-chain FK in pure Clojure. q is a seq of N joint
  angles; joint-xyz/joint-rpy/joint-axis are seqs of N [x y z] triples
  (per-joint origin translation, origin rpy, and joint axis, all in the
  parent joint's body frame). Returns the world-frame EE position [x y z]."
  [q joint-xyz joint-rpy joint-axis]
  (let [n (count q)]
    (loop [i 0 r-world [[1 0 0] [0 1 0] [0 0 1]] p-world [0.0 0.0 0.0]]
      (if (>= i n)
        p-world
        (let [r-origin (rot-rpy-full (nth joint-rpy i))
              r-q      (rot-axis (nth joint-axis i) (nth q i))
              r-i-in-p (mat3-mul-small r-origin r-q)
              rotated  (matvec3-small r-world (nth joint-xyz i))
              p-world' (vec (map + p-world rotated))
              r-world' (mat3-mul-small r-world r-i-in-p)]
          (recur (inc i) r-world' p-world'))))))

(def generic-serial-fk-kernel
  (wgpu/wgpu-kernel
    {:js (fn [q-in joint-xyz joint-rpy joint-axis ee-out n]
           (let [env  (wp/tid)
                 q    (vec (for [i (range n)] (wp/wp-get q-in (+ (* env n) i))))
                 xyz  (vec (for [i (range n)] [(wp/wp-get joint-xyz (+ (* i 3) 0))
                                                (wp/wp-get joint-xyz (+ (* i 3) 1))
                                                (wp/wp-get joint-xyz (+ (* i 3) 2))]))
                 rpy  (vec (for [i (range n)] [(wp/wp-get joint-rpy (+ (* i 3) 0))
                                                (wp/wp-get joint-rpy (+ (* i 3) 1))
                                                (wp/wp-get joint-rpy (+ (* i 3) 2))]))
                 axis (vec (for [i (range n)] [(wp/wp-get joint-axis (+ (* i 3) 0))
                                                (wp/wp-get joint-axis (+ (* i 3) 1))
                                                (wp/wp-get joint-axis (+ (* i 3) 2))]))
                 ee   (generic-serial-fk-inline q xyz rpy axis)]
             (wp/wp-set ee-out (+ (* env 3) 0) (ee 0))
             (wp/wp-set ee-out (+ (* env 3) 1) (ee 1))
             (wp/wp-set ee-out (+ (* env 3) 2) (ee 2))))
     :wgsl "
@group(0) @binding(0) var<storage, read_write> q_in:       array<f32>;
@group(0) @binding(1) var<storage, read_write> joint_xyz:  array<f32>;
@group(0) @binding(2) var<storage, read_write> joint_rpy:  array<f32>;
@group(0) @binding(3) var<storage, read_write> joint_axis: array<f32>;
@group(0) @binding(4) var<storage, read_write> ee_out:     array<f32>;
@group(0) @binding(5) var<uniform>             n_uniform:  vec4<u32>;

fn rot_rpy(r: f32, p: f32, y: f32) -> mat3x3<f32> {
  let cr = cos(r); let sr = sin(r);
  let cp = cos(p); let sp = sin(p);
  let cy = cos(y); let sy = sin(y);
  return mat3x3<f32>(
    vec3<f32>(cy*cp, sy*cp, -sp),
    vec3<f32>(cy*sp*sr - sy*cr, sy*sp*sr + cy*cr, cp*sr),
    vec3<f32>(cy*sp*cr + sy*sr, sy*sp*cr - cy*sr, cp*cr),
  );
}

fn rot_axis(axis: vec3<f32>, angle: f32) -> mat3x3<f32> {
  let c = cos(angle); let s = sin(angle);
  let oc = 1.0 - c;
  let ax = axis.x; let ay = axis.y; let az = axis.z;
  return mat3x3<f32>(
    vec3<f32>(c + ax*ax*oc,        ay*ax*oc + az*s,    az*ax*oc - ay*s),
    vec3<f32>(ax*ay*oc - az*s,     c + ay*ay*oc,        az*ay*oc + ax*s),
    vec3<f32>(ax*az*oc + ay*s,     ay*az*oc - ax*s,    c + az*az*oc),
  );
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let env = gid.x;
  let n = n_uniform.x;
  let n_envs = arrayLength(&ee_out) / 3u;
  if (env >= n_envs) { return; }
  let base = env * n;

  var R_world = mat3x3<f32>(
    vec3<f32>(1.0, 0.0, 0.0),
    vec3<f32>(0.0, 1.0, 0.0),
    vec3<f32>(0.0, 0.0, 1.0),
  );
  var p_world = vec3<f32>(0.0, 0.0, 0.0);

  // Loop bounded at MAX_N=12; runtime n controls early exit.
  for (var i = 0u; i < 12u; i = i + 1u) {
    if (i >= n) { break; }
    let xyz = vec3<f32>(joint_xyz[i*3u + 0u], joint_xyz[i*3u + 1u], joint_xyz[i*3u + 2u]);
    let R_origin = rot_rpy(joint_rpy[i*3u + 0u], joint_rpy[i*3u + 1u], joint_rpy[i*3u + 2u]);
    let axis = vec3<f32>(joint_axis[i*3u + 0u], joint_axis[i*3u + 1u], joint_axis[i*3u + 2u]);
    let R_q = rot_axis(axis, q_in[base + i]);
    let R_iInP = R_origin * R_q;
    let rotated = R_world * xyz;
    p_world = p_world + rotated;
    R_world = R_world * R_iInP;
  }
  ee_out[env * 3u + 0u] = p_world.x;
  ee_out[env * 3u + 1u] = p_world.y;
  ee_out[env * 3u + 2u] = p_world.z;
}
"
     :bindings [(assoc (wgpu/storage-binding 0 0) :writeback false)
                (assoc (wgpu/storage-binding 1 1) :writeback false)
                (assoc (wgpu/storage-binding 2 2) :writeback false)
                (assoc (wgpu/storage-binding 3 3) :writeback false)
                (wgpu/storage-binding 4 4)
                (wgpu/uniform-binding 5 5)]
     :workgroup-size 64}))

;; ── mulberry32 seeded PRNG + Marsaglia polar Gaussian sampler ────────────
;;
;; Host-side (CPU) helpers used to drive deterministic, reproducible obs
;; noise / domain randomization in tests and reference pipelines. No WGSL
;; counterpart — these are pure Clojure, matching the TS source (which is
;; also plain host-side JS, not a WgpuKernel).
;;
;; mulberry32 is a seeded PRNG that returns a 0-arg closure: call it
;; repeatedly to get successive uniform floats in [0, 1), with internal
;; mutable state threaded through an atom (the atom-per-instance mutable-
;; closure pattern used throughout this port, e.g. utsushimi.sampler's LCG-
;; state atom / wadachi-sim's sequence-dist cursor atom).
;;
;; The two 32-bit-truncating-multiply steps (`Math.imul` in the TS source)
;; are the one place this needs platform-specific handling. On the JVM, a
;; product of two u32 operands (each up to 0xFFFFFFFF) can reach
;; ~1.8446744e19 — *larger* than Long/MAX_VALUE (~9.2233720e18) — so a
;; checked `*` throws ArithmeticException, and the auto-promoting `*'`
;; would hand back a BigInt that `bit-and`/`bit-shift-*` then reject
;; outright ("bit operation not supported for: class clojure.lang.BigInt"
;; — the exact failure mode this project hit before in a different LCG
;; PRNG; see utsushimi.sampler's `+'`/`*'`/mod/quot workaround). The fix
;; used here instead is `unchecked-multiply`: it computes the exact 64-bit
;; two's-complement product (which always fits — max u32*u32 < 2^64), and
;; since 2^32 divides 2^64, masking the low 32 bits afterward recovers the
;; identical residue Math.imul would return, without ever producing a
;; BigInt. On CLJS, numbers are already JS doubles and `Math.imul`/`>>> `
;; are native, so the :cljs branch just calls them directly. Every value
;; that reaches a numeric `+` here is kept as a canonical nonnegative u32
;; residue beforehand (`u32` re-masks right after the seed-update add and
;; right after the line-4 add), so `bit-xor`/`bit-or` never see values
;; outside their 32-bit-clean invariant.

(defn- u32
  "Coerce to an unsigned-32-bit residue in [0, 2^32) — mirrors JS `x >>> 0`."
  [x]
  #?(:clj (bit-and x 0xFFFFFFFF)
     :cljs (unsigned-bit-shift-right x 0)))

(defn- imul32
  "32-bit truncating multiply — mirrors JS `Math.imul(a, b)` (see namespace
  comment above mulberry32 for why the JVM branch needs unchecked-multiply
  instead of plain `*`)."
  [a b]
  #?(:clj (u32 (unchecked-multiply (long a) (long b)))
     :cljs (u32 (js/Math.imul a b))))

(defn mulberry32
  "Seeded deterministic PRNG (matches TS `mulberry32`). Returns a 0-arg
  closure that, called repeatedly, produces a deterministic, repeatable
  sequence of uniform floats in [0, 1) for a given seed; different seeds
  produce different sequences. Cross-checked against a from-scratch node
  re-implementation of the TS algorithm (not this port) — seed=99 called
  from two freshly-seeded instances gives identical sequences
  [0.2604658124037087 0.8048227655235678 0.5408715349622071]."
  [seed]
  (let [state (atom (u32 seed))]
    (fn []
      (let [s  (u32 (+ @state 0x6d2b79f5))
            _  (reset! state s)
            t1 (imul32 (bit-xor s (unsigned-bit-shift-right s 15)) (bit-or s 1))
            t2 (bit-xor t1 (u32 (+ t1 (imul32 (bit-xor t1 (unsigned-bit-shift-right t1 7))
                                               (bit-or t1 61)))))]
        (/ (double (u32 (bit-xor t2 (unsigned-bit-shift-right t2 14))))
           4294967296.0)))))

(defn gaussian-marsaglia
  "Host-side Marsaglia polar Gaussian sampler. Deterministic given a
  uniform RNG (e.g. mulberry32) so the obs-noise path can be tested
  byte-for-byte across runs. `rng` is a 0-arg thunk returning a uniform
  float in [0, 1); `n` is the number of Gaussian samples to draw (the TS
  source's parameter is named `count`, renamed here since it would shadow
  `clojure.core/count`, which this fn also calls to check the accumulated
  output length)."
  [rng n]
  (loop [out []]
    (if (>= (count out) n)
      out
      (let [[u v s] (loop []
                      (let [u (- (* 2 (rng)) 1)
                            v (- (* 2 (rng)) 1)
                            s (+ (* u u) (* v v))]
                        (if (or (>= s 1) (zero? s))
                          (recur)
                          [u v s])))
            f    (wp/sqrt (/ (* -2 (wp/log s)) s))
            out' (conj out (* u f))]
        (recur (if (< (count out') n) (conj out' (* v f)) out'))))))

;; ── L2-norm-squared per env (universal reward building block) ────────────
;;
;; Most Isaac Lab reward terms reduce to ||x||^2 of some per-env vector:
;;   - action_l2           = ||a||^2
;;   - action_rate_l2      = ||a_t - a_{t-1}||^2
;;   - joint_vel_l2        = ||qdot||^2
;;   - joint_acc_l2        = ||qddot||^2
;;   - joint_torque_l2     = ||tau||^2
;;   - flat_orientation_l2 = ||up_vec - z-hat||^2
;;
;; One thread per env iterates a bounded-d input (compile-bound 64; runtime
;; d via uniform). Output: result[env] = sum_i x[env*d + i]^2.
;;
;; Compose with combine-weighted-rewards (host helper) and
;; track-vel-exp-inline to reproduce full Isaac Lab RewardManager scoring
;; per env.
;;
;; Bindings: x (storage read, writeback false), out (storage read_write),
;; d (uniform).

(def l2-norm-squared-kernel
  (wgpu/wgpu-kernel
    {:js (fn [x out d]
           (let [env (wp/tid)]
             (loop [i 0 s 0.0]
               (if (>= i d)
                 (wp/wp-set out env s)
                 (let [v (wp/wp-get x (+ (* env d) i))]
                   (recur (inc i) (+ s (* v v))))))))
     :wgsl "
@group(0) @binding(0) var<storage, read_write> x:         array<f32>;
@group(0) @binding(1) var<storage, read_write> out:       array<f32>;
@group(0) @binding(2) var<uniform>             d_uniform: vec4<u32>;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let env = gid.x;
  let n_envs = arrayLength(&out);
  if (env >= n_envs) { return; }
  let d = d_uniform.x;
  var s: f32 = 0.0;
  for (var i = 0u; i < 64u; i = i + 1u) {
    if (i >= d) { break; }
    let v = x[env * d + i];
    s = s + v * v;
  }
  out[env] = s;
}
"
     :bindings [(assoc (wgpu/storage-binding 0 0) :writeback false)
                (wgpu/storage-binding 1 1)
                (wgpu/uniform-binding 2 2)]
     :workgroup-size 64}))

(defn l2-norm-squared-inline
  "Reference per-env ||x||^2 in pure Clojure."
  [x d]
  (let [n-envs (quot (count x) d)]
    (vec (for [env (range n-envs)]
           (reduce + (for [i (range d)]
                       (let [v (nth x (+ (* env d) i))] (* v v))))))))

(defn track-vel-exp-inline
  "Isaac Lab `track_lin_vel_xy_exp`-style tracking reward (host-side
  scalar). reward = exp(-||v_target - v_actual||^2 / sigma^2)"
  [v-target v-actual sigma d]
  (let [n-envs (quot (count v-target) d)
        sigma2 (* sigma sigma)]
    (vec (for [env (range n-envs)]
           (let [s (reduce + (for [i (range d)]
                                (let [dv (- (nth v-target (+ (* env d) i))
                                            (nth v-actual (+ (* env d) i)))]
                                  (* dv dv))))]
             (wp/exp (- (/ s sigma2))))))))

(defn combine-weighted-rewards
  "Compose K per-env reward terms with per-term weights into total per-env
  reward. Mirror of Isaac Lab's RewardManager.compute(): weighted sum of
  term values."
  [term-values weights]
  (let [n-envs (count (first term-values))]
    (vec (for [env (range n-envs)]
           (reduce + (map (fn [term w] (* w (nth term env))) term-values weights))))))

;; ── Episode terminations + truncations (env-parallel) ────────────────────
;;
;; Isaac Lab `TerminationManager` canonical pattern. Per-env booleans
;; (encoded as f32 0.0/1.0) for:
;;   terminated[env] = joint_limit_violation OR base_fall   (MDP termination)
;;   truncated[env]  = step_count >= max_steps              (MDP truncation)
;;
;; Done = terminated OR truncated -> host triggers reset_env(env).
;; One thread per env scans q[env*n..env*n+n] for limit violation + checks
;; base_z + step_count. WGSL loop bound is 32 (MAX_N_TERM in the TS
;; source); n is a runtime uniform, capped by that compile bound.
;;
;; Note on bindings: the TS source's `bindings` array declares only ONE
;; uniform entry (binding 7, inputIndex 7) even though the :js fn takes 3
;; trailing scalars (n, minBaseZ, maxSteps at positions 7/8/9) — WGSL packs
;; all 3 into a single vec4 `params` uniform (.x/.y/.z), but the JS-side
;; bindings metadata only names the first. Ported verbatim (bindings is
;; inert JVM-side data here; wgpu-backend's jvm-backend dispatch ignores
;; :bindings entirely and always runs the :js fn via warp.warp/launch) —
;; not "fixed", since that would diverge from the TS source this file
;; mirrors 1:1.

(def terminations-kernel
  (wgpu/wgpu-kernel
    {:js (fn [q q-lower q-upper base-z step terminated truncated n min-base-z max-steps]
           (let [env (wp/tid)
                 limit-violated (loop [i 0]
                                  (if (>= i n)
                                    0
                                    (let [v (wp/wp-get q (+ (* env n) i))]
                                      (if (or (< v (wp/wp-get q-lower i))
                                              (> v (wp/wp-get q-upper i)))
                                        1
                                        (recur (inc i))))))
                 fell      (if (< (wp/wp-get base-z env) min-base-z) 1 0)
                 timed-out (if (>= (wp/wp-get step env) max-steps) 1 0)]
             (wp/wp-set terminated env (if (or (pos? limit-violated) (pos? fell)) 1 0))
             (wp/wp-set truncated env timed-out)))
     :wgsl "
@group(0) @binding(0) var<storage, read_write> q:          array<f32>;
@group(0) @binding(1) var<storage, read_write> q_lower:    array<f32>;
@group(0) @binding(2) var<storage, read_write> q_upper:    array<f32>;
@group(0) @binding(3) var<storage, read_write> base_z:     array<f32>;
@group(0) @binding(4) var<storage, read_write> step:       array<f32>;
@group(0) @binding(5) var<storage, read_write> terminated: array<f32>;
@group(0) @binding(6) var<storage, read_write> truncated:  array<f32>;
@group(0) @binding(7) var<uniform>             params:     vec4<f32>;
//                                                          .x = n_joints (cast u32)
//                                                          .y = min_base_z
//                                                          .z = max_steps

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let env = gid.x;
  let n_envs = arrayLength(&terminated);
  if (env >= n_envs) { return; }
  let n = u32(params.x);
  let min_base_z = params.y;
  let max_steps = params.z;

  var limit_violated: u32 = 0u;
  for (var i = 0u; i < 32u; i = i + 1u) {
    if (i >= n) { break; }
    let v = q[env * n + i];
    if (v < q_lower[i] || v > q_upper[i]) {
      limit_violated = 1u;
      break;
    }
  }
  let fell = select(0u, 1u, base_z[env] < min_base_z);
  let timed_out = select(0u, 1u, step[env] >= max_steps);
  terminated[env] = select(0.0, 1.0, (limit_violated | fell) != 0u);
  truncated[env] = select(0.0, 1.0, timed_out != 0u);
}
"
     :bindings [(assoc (wgpu/storage-binding 0 0) :writeback false)
                (assoc (wgpu/storage-binding 1 1) :writeback false)
                (assoc (wgpu/storage-binding 2 2) :writeback false)
                (assoc (wgpu/storage-binding 3 3) :writeback false)
                (assoc (wgpu/storage-binding 4 4) :writeback false)
                (wgpu/storage-binding 5 5)
                (wgpu/storage-binding 6 6)
                (wgpu/uniform-binding 7 7)]
     :workgroup-size 64}))

(defn terminations-inline
  "Reference terminations + truncations per env. Returns
  {:terminated [...] :truncated [...]} (the TS source returns an analogous
  {terminated, truncated} object)."
  [q q-lower q-upper base-z step n min-base-z max-steps]
  (let [n-envs (count base-z)]
    {:terminated (vec (for [env (range n-envs)]
                         (let [limit-violated (loop [i 0]
                                                 (if (>= i n)
                                                   0
                                                   (let [v (nth q (+ (* env n) i))]
                                                     (if (or (< v (nth q-lower i))
                                                             (> v (nth q-upper i)))
                                                       1
                                                       (recur (inc i))))))
                               fell (if (< (nth base-z env) min-base-z) 1 0)]
                           (if (or (pos? limit-violated) (pos? fell)) 1 0))))
     :truncated (vec (for [env (range n-envs)]
                        (if (>= (nth step env) max-steps) 1 0)))}))

;; ── MLP policy-net forward (env-parallel) ─────────────────────────────────
;;
;; Isaac Lab's PPO/SAC default policy: 2-layer MLP `Linear -> ReLU ->
;; Linear -> tanh`. Per-env forward pass:
;;
;;   hidden = ReLU(W1 * obs + b1)      shape [hidden_dim]
;;   action = tanh(W2 * hidden + b2)   shape [action_dim]
;;
;; Weights are shared across envs (storage, writeback false); per-env obs
;; input + action output (writeback true). WGSL hard-codes MAX_HIDDEN=128 /
;; MAX_OBS=64 as fixed-size loop bounds/array (fits comfortably in 32
;; KB/workgroup -> iPhone-12 WebGPU safe per ADR-2605241900 edge-target
;; invariant); the :js fallback has no such fixed bound and loops to the
;; actual runtime hidden-dim/obs-dim.
;;
;; Closes the trained-policy inference gap: a checkpoint exported as
;; (W1, b1, W2, b2) flat float32 arrays can now run in-browser alongside
;; the full simulation loop.
;;
;; Bindings (7 total): obs, W1, b1, W2, b2 (storage read, writeback false),
;; action-out (storage read_write), dims (uniform vec4<u32>: .x=obs_dim
;; .y=hidden_dim .z=action_dim -- packed from the trailing 3 scalar :js
;; args the same way two-link-arm-step-kernel packs link1/link2).

(def mlp-policy-forward-kernel
  (wgpu/wgpu-kernel
    {:js (fn [obs W1 b1 W2 b2 action-out obs-dim hidden-dim action-dim]
           (let [env    (wp/tid)
                 hidden (vec (for [h (range hidden-dim)]
                                (let [s (reduce (fn [acc o]
                                                   (+ acc (* (wp/wp-get W1 (+ (* h obs-dim) o))
                                                             (wp/wp-get obs (+ (* env obs-dim) o)))))
                                                 (wp/wp-get b1 h)
                                                 (range obs-dim))]
                                  (if (> s 0) s 0))))]
             (doseq [a (range action-dim)]
               (let [s (reduce (fn [acc h]
                                  (+ acc (* (wp/wp-get W2 (+ (* a hidden-dim) h))
                                            (nth hidden h))))
                                (wp/wp-get b2 a)
                                (range hidden-dim))]
                 (wp/wp-set action-out (+ (* env action-dim) a) (Math/tanh s))))))
     :wgsl "
@group(0) @binding(0) var<storage, read_write> obs:        array<f32>;
@group(0) @binding(1) var<storage, read_write> W1:         array<f32>;
@group(0) @binding(2) var<storage, read_write> b1:         array<f32>;
@group(0) @binding(3) var<storage, read_write> W2:         array<f32>;
@group(0) @binding(4) var<storage, read_write> b2:         array<f32>;
@group(0) @binding(5) var<storage, read_write> action_out: array<f32>;
@group(0) @binding(6) var<uniform>             dims:       vec4<u32>;
//                                                          .x = obs_dim
//                                                          .y = hidden_dim
//                                                          .z = action_dim

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let env = gid.x;
  let obs_dim = dims.x;
  let hidden_dim = dims.y;
  let action_dim = dims.z;
  let n_envs = arrayLength(&action_out) / action_dim;
  if (env >= n_envs) { return; }

  var hidden: array<f32, 128>;
  for (var h = 0u; h < 128u; h = h + 1u) {
    if (h >= hidden_dim) { break; }
    var s: f32 = b1[h];
    for (var o = 0u; o < 64u; o = o + 1u) {
      if (o >= obs_dim) { break; }
      s = s + W1[h * obs_dim + o] * obs[env * obs_dim + o];
    }
    hidden[h] = max(0.0, s);
  }
  for (var a = 0u; a < action_dim; a = a + 1u) {
    var s: f32 = b2[a];
    for (var h = 0u; h < 128u; h = h + 1u) {
      if (h >= hidden_dim) { break; }
      s = s + W2[a * hidden_dim + h] * hidden[h];
    }
    action_out[env * action_dim + a] = tanh(s);
  }
}
"
     :bindings [(assoc (wgpu/storage-binding 0 0) :writeback false)
                (assoc (wgpu/storage-binding 1 1) :writeback false)
                (assoc (wgpu/storage-binding 2 2) :writeback false)
                (assoc (wgpu/storage-binding 3 3) :writeback false)
                (assoc (wgpu/storage-binding 4 4) :writeback false)
                (wgpu/storage-binding 5 5)
                (wgpu/uniform-binding 6 6)]
     :workgroup-size 64}))

(defn mlp-policy-forward-inline
  "Reference 2-layer MLP forward (Linear -> ReLU -> Linear -> tanh) in pure
  Clojure. obs is a flat envs*obs-dim seq (row-major); W1 is hidden-dim *
  obs-dim (row-major, W1[h*obs-dim+o]), b1 is hidden-dim; W2 is action-dim *
  hidden-dim (row-major, W2[a*hidden-dim+h]), b2 is action-dim. Returns a
  flat envs*action-dim vector (row-major).

  A separate, deliberately-standalone implementation from
  kotoba.lang.kami-nv-compat.policies/run-mlp-policy (JVM-only; wraps the
  same algorithm behind a JSON policy-checkpoint spec loader) -- this fn
  instead mirrors mlp-policy-forward-kernel's own :js fallback, matching
  every other kernel/inline pair in this file's self-contained,
  standalone-WGSL-compilable design."
  [obs W1 b1 W2 b2 obs-dim hidden-dim action-dim]
  (let [n-envs (quot (count obs) obs-dim)]
    (vec
      (for [env (range n-envs)
            :let [hidden (vec (for [h (range hidden-dim)]
                                 (let [s (reduce (fn [acc o]
                                                    (+ acc (* (nth W1 (+ (* h obs-dim) o))
                                                              (nth obs (+ (* env obs-dim) o)))))
                                                  (nth b1 h)
                                                  (range obs-dim))]
                                   (if (> s 0) s 0))))]
            a (range action-dim)]
        (let [s (reduce (fn [acc h]
                           (+ acc (* (nth W2 (+ (* a hidden-dim) h))
                                     (nth hidden h))))
                         (nth b2 a)
                         (range hidden-dim))]
          (Math/tanh s))))))

;; ── Conditional per-env reset (env x dim parallel) ────────────────────────
;;
;; Closes the loop between TerminationManager (iter 105) and next-episode
;; initial state. Per-(env, dim) thread: if done[env] == 1, copy
;; reset-state[env*d + i] -> state[env*d + i]; else leave state untouched.
;;
;; One kernel handles any per-env array: joint state (d=N), velocity
;; buffer (d=N), step counter (d=1), arbitrary observation history etc.
;; Host invokes once per buffer with the appropriate d.
;;
;; Bindings (4 total): state (storage read_write), reset-state, done
;; (storage read, writeback false), d (uniform).

(def conditional-reset-kernel
  (wgpu/wgpu-kernel
    {:js (fn [state reset-state done d]
           (let [idx (wp/tid)
                 env (long (wp/floor (double (/ idx d))))]
             (when (>= (wp/wp-get done env) 0.5)
               (wp/wp-set state idx (wp/wp-get reset-state idx)))))
     :wgsl "
@group(0) @binding(0) var<storage, read_write> state:       array<f32>;
@group(0) @binding(1) var<storage, read_write> reset_state: array<f32>;
@group(0) @binding(2) var<storage, read_write> done:        array<f32>;
@group(0) @binding(3) var<uniform>             d_uniform:   vec4<u32>;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let idx = gid.x;
  let total = arrayLength(&state);
  if (idx >= total) { return; }
  let d = d_uniform.x;
  let env = idx / d;
  if (done[env] >= 0.5) {
    state[idx] = reset_state[idx];
  }
}
"
     :bindings [(wgpu/storage-binding 0 0)
                (assoc (wgpu/storage-binding 1 1) :writeback false)
                (assoc (wgpu/storage-binding 2 2) :writeback false)
                (wgpu/uniform-binding 3 3)]
     :workgroup-size 64}))

(defn conditional-reset-inline
  "Reference conditional per-env reset in pure Clojure: returns the new
  state vector (env-wise copy of reset-state into any index whose env has
  done[env] >= 0.5; every other index keeps its original state value). TS
  mutates `state` in place -- ported as a pure return value instead, since
  Clojure vectors are immutable (same return-instead-of-mutate treatment
  applied to every void/mutating 'Inline' fn in this file)."
  [state reset-state done d]
  (vec (map-indexed
         (fn [idx v]
           (let [env (long (wp/floor (double (/ idx d))))]
             (if (>= (nth done env) 0.5) (nth reset-state idx) v)))
         state)))

;; ── Ground-plane contact (env x foot parallel, frictionless) ─────────────
;;
;; Spring-damper normal-force model -- the minimal physical contact pattern
;; that lets legged demos (ANYmal walking, biped standing) push against a
;; ground plane. Per-foot:
;;
;;   penetration = ground_z - p_z
;;   if penetration > 0: F_z = max(0, Kp*penetration - Kd*v_z)
;;   else:               F_z = 0
;;   F_x = F_y = 0  (frictionless; iter 110 will add Coulomb tangent)
;;
;; One thread per (env, foot) pair. ground_z, Kp, Kd shared across all envs
;; as scalars; mu (friction coefficient) is unused in this revision --
;; reserved for a future Coulomb-tangent variant.
;;
;; Bridges from the foot-FK pipeline (iter 70, 88, 95 ANYmal) to a
;; physically-driven simulation step -- Fz can be summed into a base
;; reaction force or projected through J^T to per-joint contact torques.
;;
;; Bindings (4 total): p-world, v-world (storage read, writeback false),
;; f-out (storage read_write), params (uniform vec4<f32>: .x=ground_z
;; .y=Kp .z=Kd -- packed from the trailing 3 scalar :js args).

(def ground-contact-kernel
  (wgpu/wgpu-kernel
    {:js (fn [p-world v-world f-out ground-z kp kd]
           (let [idx         (wp/tid)
                 base        (* idx 3)
                 pz          (wp/wp-get p-world (+ base 2))
                 penetration (- ground-z pz)
                 fz          (if (> penetration 0)
                               (let [vz  (wp/wp-get v-world (+ base 2))
                                     raw (- (* kp penetration) (* kd vz))]
                                 (if (> raw 0) raw 0))
                               0)]
             (wp/wp-set f-out (+ base 0) 0)
             (wp/wp-set f-out (+ base 1) 0)
             (wp/wp-set f-out (+ base 2) fz)))
     :wgsl "
@group(0) @binding(0) var<storage, read_write> p_world: array<f32>;
@group(0) @binding(1) var<storage, read_write> v_world: array<f32>;
@group(0) @binding(2) var<storage, read_write> f_out:   array<f32>;
@group(0) @binding(3) var<uniform>             params:  vec4<f32>;
//                                                       .x = ground_z
//                                                       .y = Kp
//                                                       .z = Kd

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let idx = gid.x;
  let total = arrayLength(&f_out) / 3u;
  if (idx >= total) { return; }
  let base = idx * 3u;
  let pz = p_world[base + 2u];
  let penetration = params.x - pz;
  var fz: f32 = 0.0;
  if (penetration > 0.0) {
    let vz = v_world[base + 2u];
    fz = max(0.0, params.y * penetration - params.z * vz);
  }
  f_out[base + 0u] = 0.0;
  f_out[base + 1u] = 0.0;
  f_out[base + 2u] = fz;
}
"
     :bindings [(assoc (wgpu/storage-binding 0 0) :writeback false)
                (assoc (wgpu/storage-binding 1 1) :writeback false)
                (wgpu/storage-binding 2 2)
                (wgpu/uniform-binding 3 3)]
     :workgroup-size 64}))

(defn ground-contact-inline
  "Reference frictionless ground-plane contact per foot, pure Clojure.
  p-world/v-world are flat 3*n (x,y,z per foot); n is derived from their
  own length instead of from a caller-supplied output-array length (TS's
  fOut param exists only so its .length can be read as n -- Clojure
  returns the new f-out vector instead of mutating an output array in
  place, so that awkward read-only-for-length param is dropped). Returns a
  flat 3*n [fx fy fz ...] vector."
  [p-world v-world ground-z kp kd]
  (let [total (quot (count p-world) 3)]
    (vec (mapcat
           (fn [i]
             (let [base        (* i 3)
                   pz          (nth p-world (+ base 2))
                   penetration (- ground-z pz)
                   fz          (if (> penetration 0)
                                 (let [vz  (nth v-world (+ base 2))
                                       raw (- (* kp penetration) (* kd vz))]
                                   (if (> raw 0) raw 0))
                                 0)]
               [0 0 fz]))
           (range total)))))

;; ── Franka 7-DoF FK + linear Jacobian (env-parallel) ──────────────────────
;;
;; Extends franka-fk-kernel with the 3x7 linear Jacobian. Each thread runs
;; FK, stores all 7 joint poses (R, p) in memory, then derives per-joint
;; Jacobian columns via axis_world_i x (p_ee - p_i) -- the standard
;; revolute-joint linear-velocity Jacobian identity, where axis_world_i is
;; the joint's world-frame z-axis (the third column of R_world_i).
;;
;; Per-env input: q[7]. Per-env output: ee_pos[3] + J[3][7] = 24 floats,
;; struct-of-arrays layout [ee_x, ee_y, ee_z, J[0][0..6], J[1][0..6], J[2][0..6]].
;;
;; Bindings: q-in (storage read, N*7 floats, writeback false), out-buf
;; (storage read_write, N*24 floats).

(defn franka-fk-jacobian-inline
  "Reference Franka 7-DoF FK + 3x7 linear Jacobian in pure Clojure -- used by
  franka-fk-jacobian-kernel's :js fallback AND callable directly. Returns
  {:ee [x y z] :J [[..7] [..7] [..7]]} where ee is the world-frame EE
  position and J's rows are d(ee)/dq stacked per joint (row = xyz axis,
  col = joint index)."
  [q]
  (loop [i 0 r-world [[1 0 0] [0 1 0] [0 0 1]] p-world [0.0 0.0 0.0]
         poses-r [] poses-p []]
    (if (>= i 7)
      (let [ee   (poses-p 6)
            cols (for [k (range 7)]
                   (let [rk (poses-r k)
                         a  [(get-in rk [0 2]) (get-in rk [1 2]) (get-in rk [2 2])]
                         pk (poses-p k)
                         dp [(- (ee 0) (pk 0)) (- (ee 1) (pk 1)) (- (ee 2) (pk 2))]]
                     [(- (* (a 1) (dp 2)) (* (a 2) (dp 1)))
                      (- (* (a 2) (dp 0)) (* (a 0) (dp 2)))
                      (- (* (a 0) (dp 1)) (* (a 1) (dp 0)))]))]
        {:ee ee
         :J [(vec (map #(nth % 0) cols))
             (vec (map #(nth % 1) cols))
             (vec (map #(nth % 2) cols))]})
      (let [r-origin (rot-rpy (franka-fk-rpy-r i))
            r-q      (rot-z (nth q i))
            r-i-in-p (mat3-mul-small r-origin r-q)
            rotated  (matvec3-small r-world (franka-fk-xyz i))
            p-world' (vec (map + p-world rotated))
            r-world' (mat3-mul-small r-world r-i-in-p)]
        (recur (inc i) r-world' p-world' (conj poses-r r-world') (conj poses-p p-world'))))))

(def franka-fk-jacobian-kernel
  (wgpu/wgpu-kernel
    {:js (fn [q-in out-buf]
           (let [env  (wp/tid)
                 q    (vec (for [j (range 7)] (wp/wp-get q-in (+ (* env 7) j))))
                 {:keys [ee J]} (franka-fk-jacobian-inline q)
                 base (* env 24)]
             (wp/wp-set out-buf (+ base 0) (ee 0))
             (wp/wp-set out-buf (+ base 1) (ee 1))
             (wp/wp-set out-buf (+ base 2) (ee 2))
             (doseq [r (range 3) c (range 7)]
               (wp/wp-set out-buf (+ base 3 (* r 7) c) (get-in J [r c])))))
     :wgsl "
@group(0) @binding(0) var<storage, read_write> q_in:    array<f32>;
@group(0) @binding(1) var<storage, read_write> out_buf: array<f32>;

fn rot_rpy_x(r: f32) -> mat3x3<f32> {
  let cr = cos(r); let sr = sin(r);
  return mat3x3<f32>(
    vec3<f32>(1.0, 0.0, 0.0),
    vec3<f32>(0.0, cr, sr),
    vec3<f32>(0.0, -sr, cr),
  );
}

fn rot_z(angle: f32) -> mat3x3<f32> {
  let c = cos(angle); let s = sin(angle);
  return mat3x3<f32>(
    vec3<f32>(c, s, 0.0),
    vec3<f32>(-s, c, 0.0),
    vec3<f32>(0.0, 0.0, 1.0),
  );
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let env = gid.x;
  let n_envs = arrayLength(&out_buf) / 24u;
  if (env >= n_envs) { return; }

  let base_q = env * 7u;
  let q = array<f32, 7>(
    q_in[base_q + 0u], q_in[base_q + 1u], q_in[base_q + 2u], q_in[base_q + 3u],
    q_in[base_q + 4u], q_in[base_q + 5u], q_in[base_q + 6u],
  );

  let half_pi: f32 = 1.5707963267948966;
  let xyz = array<vec3<f32>, 7>(
    vec3<f32>(0.0,      0.0,     0.333),
    vec3<f32>(0.0,      0.0,     0.0),
    vec3<f32>(0.0,     -0.316,   0.0),
    vec3<f32>(0.0825,   0.0,     0.0),
    vec3<f32>(-0.0825,  0.384,   0.0),
    vec3<f32>(0.0,      0.0,     0.0),
    vec3<f32>(0.088,    0.0,     0.0),
  );
  let rpy_r = array<f32, 7>(0.0, -half_pi, half_pi, half_pi, -half_pi, half_pi, half_pi);

  // Pass 1: forward kinematics, store every joint's world-frame pose.
  var poses_R: array<mat3x3<f32>, 7>;
  var poses_p: array<vec3<f32>, 7>;
  var R_world = mat3x3<f32>(
    vec3<f32>(1.0, 0.0, 0.0),
    vec3<f32>(0.0, 1.0, 0.0),
    vec3<f32>(0.0, 0.0, 1.0),
  );
  var p_world = vec3<f32>(0.0, 0.0, 0.0);
  for (var i = 0u; i < 7u; i = i + 1u) {
    let R_origin = rot_rpy_x(rpy_r[i]);
    let R_q = rot_z(q[i]);
    let R_iInP = R_origin * R_q;
    let rotated = R_world * xyz[i];
    p_world = p_world + rotated;
    R_world = R_world * R_iInP;
    poses_R[i] = R_world;
    poses_p[i] = p_world;
  }

  let ee_pos = poses_p[6];
  let base_out = env * 24u;
  out_buf[base_out + 0u] = ee_pos.x;
  out_buf[base_out + 1u] = ee_pos.y;
  out_buf[base_out + 2u] = ee_pos.z;

  // Pass 2: Jacobian columns J[:,i] = axis_world_i x (p_ee - p_i)
  // axis_world_i = R_world_i . (0,0,1) = third column of R_world_i
  for (var i = 0u; i < 7u; i = i + 1u) {
    let Ri = poses_R[i];
    let a_world = vec3<f32>(Ri[2].x, Ri[2].y, Ri[2].z);
    let dp = ee_pos - poses_p[i];
    let col = vec3<f32>(
      a_world.y * dp.z - a_world.z * dp.y,
      a_world.z * dp.x - a_world.x * dp.z,
      a_world.x * dp.y - a_world.y * dp.x,
    );
    out_buf[base_out + 3u + 0u * 7u + i] = col.x;
    out_buf[base_out + 3u + 1u * 7u + i] = col.y;
    out_buf[base_out + 3u + 2u * 7u + i] = col.z;
  }
}
"
     :bindings [(assoc (wgpu/storage-binding 0 0) :writeback false)
                (wgpu/storage-binding 1 1)]
     :workgroup-size 64}))

;; ── Franka full DLS-IK reach step (env-parallel) ──────────────────────────
;;
;; All-in-one IK kernel -- combines FK + linear Jacobian + a 3x3 cofactor
;; DLS (damped least-squares) solve into one GPU-side step:
;;   1. FK -> per-joint poses (via franka-fk-jacobian-inline)
;;   2. err = target - p_ee
;;   3. A = J*J^T + lambda^2*I   (3x3, symmetric)
;;   4. A^-1 via closed-form cofactor expansion
;;   5. y = A^-1 * err
;;   6. dq = J^T * y             (7-vec)
;;   7. q_new = q + alpha*dq     (semi-implicit-equivalent step)
;;
;; Per-env input: q[7] + target[3] = 10 floats. Per-env output: q_new[7]
;; (written in-place over q-inout). Uniforms: lambda (DLS damping), alpha
;; (step gain).
;;
;; Bindings: q-inout (storage read_write, N*7 floats -- q is overwritten),
;; target-in (storage read, N*3 floats, writeback false), lambda (uniform),
;; alpha (uniform).

(defn franka-reach-step-inline
  "Reference Franka one-step DLS IK in pure Clojure -- used by
  franka-reach-kernel's :js fallback AND callable directly. Performs one
  damped-least-squares IK step (A = J*J^T + lambda^2*I, solved via a
  closed-form 3x3 cofactor inverse) and returns the new q[7]. Returns q
  unchanged when det(A) is (numerically) singular, matching the source's
  early-return guard."
  [q target lambda alpha]
  (let [{:keys [ee J]} (franka-fk-jacobian-inline q)
        [j0 j1 j2] J
        dot7 (fn [a b] (reduce + (map * a b)))
        err  [(- (target 0) (ee 0)) (- (target 1) (ee 1)) (- (target 2) (ee 2))]
        lam2 (* lambda lambda)
        A00  (+ lam2 (dot7 j0 j0))
        A01  (dot7 j0 j1)
        A02  (dot7 j0 j2)
        A11  (+ lam2 (dot7 j1 j1))
        A12  (dot7 j1 j2)
        A22  (+ lam2 (dot7 j2 j2))
        det  (+ (- (* A00 (- (* A11 A22) (* A12 A12)))
                    (* A01 (- (* A01 A22) (* A12 A02))))
                 (* A02 (- (* A01 A12) (* A11 A02))))]
    (if (< (Math/abs det) 1e-18)
      (vec q)
      (let [inv-det (/ 1.0 det)
            inv00 (* (- (* A11 A22) (* A12 A12)) inv-det)
            inv01 (* (- (* A02 A12) (* A01 A22)) inv-det)
            inv02 (* (- (* A01 A12) (* A02 A11)) inv-det)
            inv11 (* (- (* A00 A22) (* A02 A02)) inv-det)
            inv12 (* (- (* A02 A01) (* A00 A12)) inv-det)
            inv22 (* (- (* A00 A11) (* A01 A01)) inv-det)
            y0 (+ (* inv00 (err 0)) (* inv01 (err 1)) (* inv02 (err 2)))
            y1 (+ (* inv01 (err 0)) (* inv11 (err 1)) (* inv12 (err 2)))
            y2 (+ (* inv02 (err 0)) (* inv12 (err 1)) (* inv22 (err 2)))]
        (vec (for [i (range 7)]
               (+ (nth q i) (* alpha (+ (* (j0 i) y0) (* (j1 i) y1) (* (j2 i) y2))))))))))

(def franka-reach-kernel
  (wgpu/wgpu-kernel
    {:js (fn [q-inout target-in lambda alpha]
           (let [env    (wp/tid)
                 base   (* env 7)
                 q      (vec (for [j (range 7)] (wp/wp-get q-inout (+ base j))))
                 tbase  (* env 3)
                 target (vec (for [j (range 3)] (wp/wp-get target-in (+ tbase j))))
                 q-new  (franka-reach-step-inline q target lambda alpha)]
             (dotimes [i 7]
               (wp/wp-set q-inout (+ base i) (q-new i)))))
     :wgsl "
@group(0) @binding(0) var<storage, read_write> q_inout:   array<f32>;
@group(0) @binding(1) var<storage, read_write> target_in: array<f32>;
@group(0) @binding(2) var<uniform>             lambda_u:  vec4<f32>;
@group(0) @binding(3) var<uniform>             alpha_u:   vec4<f32>;

fn rot_rpy_x(r: f32) -> mat3x3<f32> {
  let cr = cos(r); let sr = sin(r);
  return mat3x3<f32>(
    vec3<f32>(1.0, 0.0, 0.0),
    vec3<f32>(0.0, cr, sr),
    vec3<f32>(0.0, -sr, cr),
  );
}

fn rot_z(angle: f32) -> mat3x3<f32> {
  let c = cos(angle); let s = sin(angle);
  return mat3x3<f32>(
    vec3<f32>(c, s, 0.0),
    vec3<f32>(-s, c, 0.0),
    vec3<f32>(0.0, 0.0, 1.0),
  );
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let env = gid.x;
  let n_envs = arrayLength(&q_inout) / 7u;
  if (env >= n_envs) { return; }

  let base_q = env * 7u;
  let base_t = env * 3u;
  var q = array<f32, 7>(
    q_inout[base_q + 0u], q_inout[base_q + 1u], q_inout[base_q + 2u], q_inout[base_q + 3u],
    q_inout[base_q + 4u], q_inout[base_q + 5u], q_inout[base_q + 6u],
  );
  let target = vec3<f32>(target_in[base_t + 0u], target_in[base_t + 1u], target_in[base_t + 2u]);

  let half_pi: f32 = 1.5707963267948966;
  let xyz = array<vec3<f32>, 7>(
    vec3<f32>(0.0,      0.0,     0.333),
    vec3<f32>(0.0,      0.0,     0.0),
    vec3<f32>(0.0,     -0.316,   0.0),
    vec3<f32>(0.0825,   0.0,     0.0),
    vec3<f32>(-0.0825,  0.384,   0.0),
    vec3<f32>(0.0,      0.0,     0.0),
    vec3<f32>(0.088,    0.0,     0.0),
  );
  let rpy_r = array<f32, 7>(0.0, -half_pi, half_pi, half_pi, -half_pi, half_pi, half_pi);

  // ── Pass 1: FK with stored joint poses ──
  var poses_R: array<mat3x3<f32>, 7>;
  var poses_p: array<vec3<f32>, 7>;
  var R_world = mat3x3<f32>(
    vec3<f32>(1.0, 0.0, 0.0),
    vec3<f32>(0.0, 1.0, 0.0),
    vec3<f32>(0.0, 0.0, 1.0),
  );
  var p_world = vec3<f32>(0.0, 0.0, 0.0);
  for (var i = 0u; i < 7u; i = i + 1u) {
    let R_origin = rot_rpy_x(rpy_r[i]);
    let R_q = rot_z(q[i]);
    let R_iInP = R_origin * R_q;
    let rotated = R_world * xyz[i];
    p_world = p_world + rotated;
    R_world = R_world * R_iInP;
    poses_R[i] = R_world;
    poses_p[i] = p_world;
  }
  let ee_pos = poses_p[6];

  // ── Pass 2: Linear Jacobian columns ──
  var J: array<vec3<f32>, 7>;   // 7 cols of (vx, vy, vz)
  for (var i = 0u; i < 7u; i = i + 1u) {
    let Ri = poses_R[i];
    let a_world = vec3<f32>(Ri[2].x, Ri[2].y, Ri[2].z);
    let dp = ee_pos - poses_p[i];
    J[i] = vec3<f32>(
      a_world.y * dp.z - a_world.z * dp.y,
      a_world.z * dp.x - a_world.x * dp.z,
      a_world.x * dp.y - a_world.y * dp.x,
    );
  }

  // ── Pass 3: error ──
  let err = target - ee_pos;

  // ── Pass 4: A = J.J^T + lambda^2.I (3x3) ──
  let lam = lambda_u.x;
  let lam2 = lam * lam;
  var A00 = lam2; var A01 = 0.0; var A02 = 0.0;
  var A11 = lam2; var A12 = 0.0;
  var A22 = lam2;
  for (var i = 0u; i < 7u; i = i + 1u) {
    A00 = A00 + J[i].x * J[i].x;
    A01 = A01 + J[i].x * J[i].y;
    A02 = A02 + J[i].x * J[i].z;
    A11 = A11 + J[i].y * J[i].y;
    A12 = A12 + J[i].y * J[i].z;
    A22 = A22 + J[i].z * J[i].z;
  }
  // A is symmetric (A10 = A01, A20 = A02, A21 = A12)

  // ── Pass 5: A^-1 via cofactor expansion (3x3 closed form) ──
  let det = A00 * (A11 * A22 - A12 * A12)
          - A01 * (A01 * A22 - A12 * A02)
          + A02 * (A01 * A12 - A11 * A02);
  if (abs(det) < 1e-18) { return; }
  let invDet = 1.0 / det;
  let inv00 = (A11 * A22 - A12 * A12) * invDet;
  let inv01 = (A02 * A12 - A01 * A22) * invDet;
  let inv02 = (A01 * A12 - A02 * A11) * invDet;
  let inv11 = (A00 * A22 - A02 * A02) * invDet;
  let inv12 = (A02 * A01 - A00 * A12) * invDet;
  let inv22 = (A00 * A11 - A01 * A01) * invDet;

  // ── Pass 6: y = A^-1 . err (3-vec) ──
  let y = vec3<f32>(
    inv00 * err.x + inv01 * err.y + inv02 * err.z,
    inv01 * err.x + inv11 * err.y + inv12 * err.z,
    inv02 * err.x + inv12 * err.y + inv22 * err.z,
  );

  // ── Pass 7+8: Delta q = J^T . y; q_new = q + alpha.Delta q ──
  let alpha = alpha_u.x;
  for (var i = 0u; i < 7u; i = i + 1u) {
    let dq_i = J[i].x * y.x + J[i].y * y.y + J[i].z * y.z;
    q_inout[base_q + i] = q[i] + alpha * dq_i;
  }
}
"
     :bindings [(wgpu/storage-binding 0 0)
                (assoc (wgpu/storage-binding 1 1) :writeback false)
                (wgpu/uniform-binding 2 2)
                (wgpu/uniform-binding 3 3)]
     :workgroup-size 64}))

;; ── Franka analytical gravity compensation (env-parallel) ─────────────────
;;
;; Computes tau_g(q) -- the joint torque vector that holds the Franka 7-DoF
;; arm against gravity at configuration q (closed-form, no Featherstone
;; needed):
;;   1. Forward kinematics -> per-joint world poses (R_i, p_i)
;;   2. Per-link COM in world: com_world_k = R_world_k * com_local_k + p_world_k
;;   3. For each joint i (revolute, axis world = R_world_i's z-column):
;;      tau_i = -(a_world_i . sum_{k>=i} [(com_world_k - p_world_i) x (m_k * g_world)])
;;
;; Real Franka link masses + COMs (franka_description URDF, Apache 2.0),
;; same source as franka-fk-*'s joint xyz/rpy.
;;
;; Per-env input: q[7]. Per-env output: tau[7]. Uniform: gravity vec
;; (typically (0, 0, -9.81)).
;;
;; NOTE (carried over from the TS source): the WGSL binding 2 uses a single
;; vec4<f32> uniform packing (gx, gy, gz, _), but the :js fallback path
;; below takes gx/gy/gz as three separate positional args and only binding
;; index 2 (gx) is wired into :bindings -- gy/gz reach the :js fallback
;; (and franka-grav-comp-inline) correctly, but a real WebGPU dispatch of
;; this kernel would need the caller to pack the full 3-vec into the
;; uniform buffer manually. The :js/CPU path is the canonical one for now.

(def ^:private franka-masses [2.74 2.74 2.38 2.38 2.74 1.55 0.54])

(def ^:private franka-com-local
  [[0.003875 0.002081 -0.04762]
   [-0.003141 -0.02872 0.003495]
   [0.02785 0.03094 -0.0961]
   [-0.05317 0.1046 0.02711]
   [-0.01121 0.04123 -0.03825]
   [0.065 -0.016 -0.020]
   [0.010 0.010 0.045]])

(defn franka-grav-comp-inline
  "Reference Franka analytical gravity-compensation torque in pure Clojure.
  gravity defaults to (0, 0, -9.81) like the TS source's default parameter.
  tau[i] = -(a_world_i . sum_{k>=i} (com_world_k - p_world_i) x (m_k * gravity))."
  ([q] (franka-grav-comp-inline q [0.0 0.0 -9.81]))
  ([q gravity]
   (loop [i 0 r-world [[1 0 0] [0 1 0] [0 0 1]] p-world [0.0 0.0 0.0]
          poses-r [] poses-p [] com-world []]
     (if (>= i 7)
       (vec (for [ji (range 7)]
              (let [ri (poses-r ji)
                    a  [(get-in ri [0 2]) (get-in ri [1 2]) (get-in ri [2 2])]
                    p-i (poses-p ji)
                    [tx ty tz]
                    (reduce (fn [[tx ty tz] k]
                              (let [ck (com-world k)
                                    r0 (- (ck 0) (p-i 0))
                                    r1 (- (ck 1) (p-i 1))
                                    r2 (- (ck 2) (p-i 2))
                                    mk (franka-masses k)
                                    fx (* (gravity 0) mk)
                                    fy (* (gravity 1) mk)
                                    fz (* (gravity 2) mk)]
                                [(+ tx (- (* r1 fz) (* r2 fy)))
                                 (+ ty (- (* r2 fx) (* r0 fz)))
                                 (+ tz (- (* r0 fy) (* r1 fx)))]))
                            [0.0 0.0 0.0] (range ji 7))]
                (- (+ (* (a 0) tx) (* (a 1) ty) (* (a 2) tz))))))
       (let [r-origin (rot-rpy (franka-fk-rpy-r i))
             r-q      (rot-z (nth q i))
             r-i-in-p (mat3-mul-small r-origin r-q)
             rotated  (matvec3-small r-world (franka-fk-xyz i))
             p-world' (vec (map + p-world rotated))
             r-world' (mat3-mul-small r-world r-i-in-p)
             c-rot    (matvec3-small r-world' (franka-com-local i))
             com-w    (vec (map + p-world' c-rot))]
         (recur (inc i) r-world' p-world'
                (conj poses-r r-world') (conj poses-p p-world') (conj com-world com-w)))))))

(def franka-grav-comp-kernel
  (wgpu/wgpu-kernel
    {:js (fn [q-in tau-out gx gy gz]
           (let [env (wp/tid)
                 q   (vec (for [i (range 7)] (wp/wp-get q-in (+ (* env 7) i))))
                 tau (franka-grav-comp-inline q [gx gy gz])]
             (dotimes [i 7]
               (wp/wp-set tau-out (+ (* env 7) i) (tau i)))))
     :wgsl "
@group(0) @binding(0) var<storage, read_write> q_in:    array<f32>;
@group(0) @binding(1) var<storage, read_write> tau_out: array<f32>;
@group(0) @binding(2) var<uniform>             g_u:     vec4<f32>;

fn rot_rpy_x(r: f32) -> mat3x3<f32> {
  let cr = cos(r); let sr = sin(r);
  return mat3x3<f32>(
    vec3<f32>(1.0, 0.0, 0.0),
    vec3<f32>(0.0, cr, sr),
    vec3<f32>(0.0, -sr, cr),
  );
}

fn rot_z(angle: f32) -> mat3x3<f32> {
  let c = cos(angle); let s = sin(angle);
  return mat3x3<f32>(
    vec3<f32>(c, s, 0.0),
    vec3<f32>(-s, c, 0.0),
    vec3<f32>(0.0, 0.0, 1.0),
  );
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let env = gid.x;
  let n_envs = arrayLength(&tau_out) / 7u;
  if (env >= n_envs) { return; }

  let base = env * 7u;
  let q = array<f32, 7>(
    q_in[base + 0u], q_in[base + 1u], q_in[base + 2u], q_in[base + 3u],
    q_in[base + 4u], q_in[base + 5u], q_in[base + 6u],
  );

  let half_pi: f32 = 1.5707963267948966;
  let xyz = array<vec3<f32>, 7>(
    vec3<f32>(0.0,      0.0,     0.333),
    vec3<f32>(0.0,      0.0,     0.0),
    vec3<f32>(0.0,     -0.316,   0.0),
    vec3<f32>(0.0825,   0.0,     0.0),
    vec3<f32>(-0.0825,  0.384,   0.0),
    vec3<f32>(0.0,      0.0,     0.0),
    vec3<f32>(0.088,    0.0,     0.0),
  );
  let rpy_r = array<f32, 7>(0.0, -half_pi, half_pi, half_pi, -half_pi, half_pi, half_pi);

  // Real Franka link masses + COMs (iter 87)
  let masses = array<f32, 7>(2.74, 2.74, 2.38, 2.38, 2.74, 1.55, 0.54);
  let com_local = array<vec3<f32>, 7>(
    vec3<f32>(0.003875,   0.002081,   -0.04762),
    vec3<f32>(-0.003141,  -0.02872,    0.003495),
    vec3<f32>(0.02785,    0.03094,    -0.0961),
    vec3<f32>(-0.05317,   0.1046,      0.02711),
    vec3<f32>(-0.01121,   0.04123,    -0.03825),
    vec3<f32>(0.065,     -0.016,      -0.020),
    vec3<f32>(0.010,      0.010,       0.045),
  );

  let g = vec3<f32>(g_u.x, g_u.y, g_u.z);

  // Pass 1: forward kinematics, store per-joint pose + per-link COM world
  var poses_R: array<mat3x3<f32>, 7>;
  var poses_p: array<vec3<f32>, 7>;
  var com_world: array<vec3<f32>, 7>;
  var R_world = mat3x3<f32>(
    vec3<f32>(1.0, 0.0, 0.0),
    vec3<f32>(0.0, 1.0, 0.0),
    vec3<f32>(0.0, 0.0, 1.0),
  );
  var p_world = vec3<f32>(0.0, 0.0, 0.0);
  for (var i = 0u; i < 7u; i = i + 1u) {
    let R_origin = rot_rpy_x(rpy_r[i]);
    let R_q = rot_z(q[i]);
    let R_iInP = R_origin * R_q;
    let rotated = R_world * xyz[i];
    p_world = p_world + rotated;
    R_world = R_world * R_iInP;
    poses_R[i] = R_world;
    poses_p[i] = p_world;
    com_world[i] = R_world * com_local[i] + p_world;
  }

  // Pass 2: per-joint gravity torque via cross-product accumulation
  // tau_i = a_world_i . sum_{k>=i} (com_world_k - p_world_i) x (m_k . g_world)
  for (var i = 0u; i < 7u; i = i + 1u) {
    let Ri = poses_R[i];
    let a_world = vec3<f32>(Ri[2].x, Ri[2].y, Ri[2].z);
    var torque_sum = vec3<f32>(0.0, 0.0, 0.0);
    for (var k = i; k < 7u; k = k + 1u) {
      let r_arm = com_world[k] - poses_p[i];
      let F = g * masses[k];
      // r_arm x F
      let cross_rF = vec3<f32>(
        r_arm.y * F.z - r_arm.z * F.y,
        r_arm.z * F.x - r_arm.x * F.z,
        r_arm.x * F.y - r_arm.y * F.x,
      );
      torque_sum = torque_sum + cross_rF;
    }
    // tau_i = a . torque_sum (dot product, scalar). Sign convention: tau_g compensates
    // gravity, so we negate (tau_g such that adding it cancels the gravity-induced motion).
    tau_out[base + i] = -(a_world.x * torque_sum.x + a_world.y * torque_sum.y + a_world.z * torque_sum.z);
  }
}
"
     :bindings [(assoc (wgpu/storage-binding 0 0) :writeback false)
                (wgpu/storage-binding 1 1)
                (wgpu/uniform-binding 2 2)]
     :workgroup-size 64}))

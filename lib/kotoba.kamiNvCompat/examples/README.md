# `@etzhayyim/kami-nv-compat` — examples

End-to-end demos that exercise the `nv-compat` substrate in real
browser / Node contexts.

## `cartpole-webgpu-demo.html` (iter 80)

Self-contained HTML demo of the cartpole WGSL kernel from iter 79
(canonical source: `../src/warp/examples.ts`).

**Open the file directly in any modern browser:**

- Chrome 113+ / Edge / Safari TP / Firefox (`about:config` →
  `dom.webgpu.enabled = true`): runs N=256 cartpole envs in parallel
  via WGSL on the GPU.
- Older browsers without `navigator.gpu`: falls back transparently to
  sequential JS (the same algorithm, same numerics — verified by the
  iter 79 cross-validation suite).

**Controls:**

- `←` / `→` — apply ±10 N to the foreground (env 0) cart.
- `R` — reset all envs to small randomized initial tilts.
- `C` — force CPU (JS) fallback even if WebGPU is available, useful
  for measuring the GPU vs CPU step-rate difference.

**What you'll see:**

- A green cart on a ground line with an orange pole-bob.
- 255 faint ghost-poles representing the other envs running in
  parallel (alpha tracks |θ| so balanced poles fade out).
- Live readout: mode (WebGPU / JS), env count, step number, steps/sec,
  current foreground θ.

**Zero build step.** All code (cartpole step kernel JS + WGSL,
state buffers, WebGPU init, canvas renderer, input loop) is inlined
in the single HTML file. The inlined cartpole kernel is byte-for-byte
the canonical SDK version at
`../src/warp/examples.ts` (`cartpoleStepKernel`, iter 79).

## `anymal-walk-demo.html` (iter 95)

ANYmal C quadruped walking with 4 selectable gaits (stand / trot /
pace / bound). Real ANYbotics joint origins (iter 94). Dual side + top
views show how the 4 legs phase relative to each other in each gait.

**Open the file directly** — zero build step.

**Controls:**

- `1` — stand (all 4 legs static)
- `2` — trot (LF+RH ↔ LH+RF diagonal)
- `3` — pace (LF+LH ↔ RF+RH same-side)
- `4` — bound (LF+RF ↔ LH+RH front/hind)
- `Space` — pause / resume
- `R` — reset phase to 0

**What you'll see:**

- Side view (xz): legs go up and down as they lift / plant
- Top view (xy): rectangle of 4 HAA hip points + 4 legs reaching outward
- Foot markers turn orange when in contact (z < -0.55) and green when
  lifted — gait pattern becomes visible from the color phasing
- Live readouts: current gait, phase ∈ [0, 1), feet-in-contact count,
  min/max foot z, step count
- 12 joint angles bar (q₁..q₁₂) updating per frame

ADR-2605261800 §D6 nv-compat namespace localization. Joint origins from
publicly-distributed anymal_c_simple_description URDF (BSD-3).

## `franka-batch-webgpu-demo.html` (iter 91)

N=64 Frankas reaching 64 different randomly-generated targets in
parallel via the iter 90 `frankaReachKernel` WGSL kernel. One
`wgpuLaunch` dispatch per frame steps all 64 envs simultaneously.

**Open the file directly** — runs on any modern browser; falls back
transparently to sequential JS when `navigator.gpu` is unavailable.

**Controls:**

- `R` — reset (generate new random target distribution)
- `Space` — pause / resume
- `C` — force JS fallback (useful for benchmarking GPU vs CPU)

**What you'll see:**

- 63 ghost Franka arms (faint green) plus foreground env-0 (full green)
  in side view (yz plane).
- 64 target crosses (orange, with env-0's highlighted).
- Mode indicator: WebGPU (green) or JS fallback (orange).
- Live stats: converged count (N within 5mm), best/mean/worst error.
- Steps/sec: GPU mode typically 100x faster than JS for N=64.

**WGSL kernel inlined** — byte-identical to the canonical
`frankaReachKernel` at `../src/warp/examples.ts` (iter 90).

ADR-2605261800 §D6 nv-compat namespace localization.

## `franka-reach-demo.html` (iter 86)

Capstone 7-DoF Franka Emika Panda reaching demo. Real FCI joint
origins (per iter 85); click on canvas to set a 3D target; arm
reaches via DLS IK each frame.

**Open the file directly** — zero build step, no WebGPU required.

**Controls:**

- **Click front view (xz)** — set x and z target (y stays current)
- **Click side view (yz)** — set y and z target (x stays current)
- `R` — reset to home pose + default target
- `H` — go home (q = [0, -π/4, 0, -3π/4, 0, π/2, π/4])
- `Space` — pause / resume

**What you'll see:**

- Two synchronized canvas views (front xz plane + side yz plane).
- Green 7-link Franka arm anchored at origin (base shown as bar).
- Orange target crosshair + circle (set by clicking either view).
- Live stats: EE x/y/z, |error|, target x/y/z, step count.
- All 7 joint angles q₁..q₇ shown in real-time bar.
- Workspace circle (~0.855m radius — Franka public spec).

**Math (all inlined):**

- Joint origins from iter 85 (real Franka FCI per public franka_description URDF)
- Forward kinematics: recursive joint frame composition with RPY rotations
- Geometric Jacobian (linear-only, 3×7) at the EE
- Damped least squares IK: Δq = Jᵀ (J Jᵀ + λ²I)⁻¹ · err, λ=0.05
- Per-frame: 1 IK step at α=0.3 gain; typically converges to sub-mm
  error in ~30-50 frames for reachable targets.

Convergence note: targets outside the 0.855m workspace, or in
unreachable orientations, will stall the arm at the workspace
boundary rather than diverge — DLS damping handles singular
configurations gracefully.

ADR-2605261800 §D6 nv-compat namespace localization.

## `pendulum-energy-demo.html` (iter 83)

Pendulum swinging via the iter 78 `pendulumStepKernel` JS impl, with
real-time energy diagnostics. Visual companion to iter 78 PASS 12
(the 50,000-step passive sim, energy bound 1%).

**Open the file directly** — zero build step.

**Controls:**

- `↑` / `↓` — apply ±5 N·m impulsive torque
- `R` — reset to θ=π/4, ω=0
- `Space` — pause / resume
- `D` — toggle viscous damping (-0.3·ω)

**What you'll see:**

- Left panel: the pendulum swinging (green rope, orange bob).
- Right panel: real-time energy traces — T kinetic (red), V potential
  (blue), E = T + V (orange overlay).
- Live readout: θ, ω, T, V, E, energy drift %, sim time.
- The orange E line stays flat in the absence of applied torque /
  damping, visibly demonstrating semi-implicit Euler's O(dt²)
  energy preservation. Tap `↑` / `↓` to inject energy; toggle `D` to
  drain it back out via viscous damping.

ADR-2605261800 §D6 nv-compat namespace localization.

## `two-link-ik-demo.html` (iter 82)

Interactive 2-link arm reaching demo. Click on canvas to set an EE
target; the arm reaches toward it via damped-least-squares (DLS) IK
over the closed-form 2×2 Jacobian.

**Open the file directly** — zero build step, no WebGPU required.

**Controls:**

- **Click anywhere** — set EE target (orange crosshair).
- `R` — reset arm to default pose + target.
- `Space` — pause / resume the IK loop.

**What you'll see:**

- Green 2-link arm with shoulder fixed at canvas centre.
- Target marker (orange crosshair + circle).
- Live readout of θ₁ / θ₂ / |error| / EE position / det J (singularity
  indicator) / target position / step count.
- Orange velocity arrow from EE → target showing the residual error
  direction.

**Math:** Damped least squares  Δq = Jᵀ (J Jᵀ + λ²I)⁻¹ · err

Algorithm identical to the SDK at
`../src/controllers/differential-ik.ts` +
`../src/dynamics/articulated-dynamics.ts`. The 2-link
specialisation lets the math be hand-written compactly while remaining
byte-identical to the general DLS solver in the SDK.

Singularity at θ₂ = 0 (arm fully extended or folded) → det J → 0;
DLS damping keeps the solver stable through it.

ADR-2605261800 §D6 nv-compat namespace localization.

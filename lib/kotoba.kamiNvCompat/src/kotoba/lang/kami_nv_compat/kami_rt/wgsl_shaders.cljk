(ns kotoba.lang.kami-nv-compat.kami-rt.wgsl-shaders
  "kami-rt WGSL compute-shader source — portable .cljc port of
  src/kami-rt/raytrace-wgsl.ts + src/kami-rt/pathtrace-wgsl.ts. Wave 22.

  Pure data: these are GPU shader programs as string constants, dispatched by
  a host-side WebGPU capability (see warp.wgpu-backend). The node encoding,
  intersection math and stack semantics mirror bvh.cljc line-for-line so the
  GPU framebuffer matches the CPU reference within f32 rounding.")

(def raytrace-wgsl
  "GPU reproduction of an OptiX launch: one thread per pixel, pinhole raygen,
  stack-based BVH traversal, Moller-Trumbore closest-hit, Lambert shade / sky
  miss. ADR-2605261800 SD6 / D10.4 kami-rt."
  "
struct Params {
  origin     : vec4<f32>,  // xyz origin,      w = width
  lowerLeft  : vec4<f32>,  // xyz,             w = height
  horizontal : vec4<f32>,  // xyz,             w = numTris (unused)
  vertical   : vec4<f32>,  // xyz,             w unused
  light      : vec4<f32>,  // xyz lightDir,    w = ambient
  albedo     : vec4<f32>,  // xyz albedo
  bgTop      : vec4<f32>,  // xyz
  bgBottom   : vec4<f32>,  // xyz
};

@group(0) @binding(0) var<storage, read>        tris   : array<f32>;
@group(0) @binding(1) var<storage, read>        nodes  : array<f32>;
@group(0) @binding(2) var<storage, read>        triIdx : array<u32>;
@group(0) @binding(3) var<storage, read_write>  fb     : array<f32>;
@group(0) @binding(4) var<uniform>              P      : Params;

const EPS : f32 = 1e-7;
const NODE_STRIDE : u32 = 8u;

struct Hit { t: f32, tri: i32, u: f32, v: f32 };

fn triVert(tri: u32, k: u32) -> vec3<f32> {
  let b = tri * 9u + k * 3u;
  return vec3<f32>(tris[b], tris[b + 1u], tris[b + 2u]);
}

fn intersectTri(tri: u32, ro: vec3<f32>, rd: vec3<f32>, tMax: f32) -> Hit {
  var h : Hit;
  h.t = -1.0;
  let v0 = triVert(tri, 0u);
  let v1 = triVert(tri, 1u);
  let v2 = triVert(tri, 2u);
  let e1 = v1 - v0;
  let e2 = v2 - v0;
  let p = cross(rd, e2);
  let det = dot(e1, p);
  if (det > -EPS && det < EPS) { return h; }
  let inv = 1.0 / det;
  let tvec = ro - v0;
  let u = dot(tvec, p) * inv;
  if (u < 0.0 || u > 1.0) { return h; }
  let q = cross(tvec, e1);
  let vv = dot(rd, q) * inv;
  if (vv < 0.0 || u + vv > 1.0) { return h; }
  let t = dot(e2, q) * inv;
  if (t < EPS || t > tMax) { return h; }
  h.t = t; h.tri = i32(tri); h.u = u; h.v = vv;
  return h;
}

fn slabHit(ni: u32, ro: vec3<f32>, invD: vec3<f32>, tMax: f32) -> bool {
  let base = ni * NODE_STRIDE;
  let mn = vec3<f32>(nodes[base], nodes[base + 1u], nodes[base + 2u]);
  let mx = vec3<f32>(nodes[base + 4u], nodes[base + 5u], nodes[base + 6u]);
  let t0 = (mn - ro) * invD;
  let t1 = (mx - ro) * invD;
  let lo = min(t0, t1);
  let hi = max(t0, t1);
  let tmin = max(max(lo.x, lo.y), max(lo.z, 0.0));
  let tmax = min(min(hi.x, hi.y), min(hi.z, tMax));
  return tmax >= tmin;
}

fn traceClosest(ro: vec3<f32>, rd: vec3<f32>) -> Hit {
  var best : Hit;
  best.t = -1.0;
  var bestT = 1e30;
  let invD = vec3<f32>(1.0 / rd.x, 1.0 / rd.y, 1.0 / rd.z);

  var stack : array<i32, 64>;
  var sp : i32 = 0;
  stack[sp] = 0; sp = sp + 1;

  loop {
    if (sp <= 0) { break; }
    sp = sp - 1;
    let ni = u32(stack[sp]);
    if (!slabHit(ni, ro, invD, bestT)) { continue; }
    let base = ni * NODE_STRIDE;
    let count = nodes[base + 7u];
    if (count > 0.0) {
      let first = u32(nodes[base + 3u]);
      let n = u32(count);
      for (var i: u32 = 0u; i < n; i = i + 1u) {
        let tri = triIdx[first + i];
        let h = intersectTri(tri, ro, rd, bestT);
        if (h.t > 0.0 && h.t < bestT) {
          best = h;
          bestT = h.t;
        }
      }
    } else {
      let left = i32(nodes[base + 3u]);
      let right = -i32(count);
      if (sp < 62) {
        stack[sp] = left;  sp = sp + 1;
        stack[sp] = right; sp = sp + 1;
      }
    }
  }
  return best;
}

fn triNormal(tri: u32) -> vec3<f32> {
  let v0 = triVert(tri, 0u);
  let v1 = triVert(tri, 1u);
  let v2 = triVert(tri, 2u);
  return normalize(cross(v1 - v0, v2 - v0));
}

@compute @workgroup_size(8, 8, 1)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let width  = u32(P.origin.w);
  let height = u32(P.lowerLeft.w);
  if (gid.x >= width || gid.y >= height) { return; }

  let s = (f32(gid.x) + 0.5) / f32(width);
  let tp = (f32(gid.y) + 0.5) / f32(height);
  let ro = P.origin.xyz;
  let target = P.lowerLeft.xyz + s * P.horizontal.xyz + tp * P.vertical.xyz;
  let rd = normalize(target - ro);

  let hit = traceClosest(ro, rd);

  var col : vec3<f32>;
  if (hit.t > 0.0) {
    var nrm = triNormal(u32(hit.tri));
    if (dot(nrm, rd) > 0.0) { nrm = -nrm; }
    let ambient = P.light.w;
    let diff = max(0.0, dot(nrm, -P.light.xyz));
    let lit = ambient + (1.0 - ambient) * diff;
    col = P.albedo.xyz * lit;
  } else {
    col = mix(P.bgBottom.xyz, P.bgTop.xyz, tp);
  }

  let o = (gid.y * width + gid.x) * 4u;
  fb[o] = col.x;
  fb[o + 1u] = col.y;
  fb[o + 2u] = col.z;
  fb[o + 3u] = 1.0;
}
")

(def pathtrace-wgsl
  "GPU reproduction of the CPU Monte-Carlo path tracer in pathtrace.cljc: one
  thread per pixel, `spp` cosine-importance-sampled paths, Lambertian +
  emissive materials, traversing the shared kami-rt BVH. The xorshift32 RNG,
  seed hash, Duff orthonormal basis and bounce loop are written to match the
  CPU reference draw-for-draw. ADR-2605261800 SD6 / D10.4 kami-rtx."
  "
struct Params {
  origin     : vec4<f32>,  // xyz origin,  w = width
  lowerLeft  : vec4<f32>,  // xyz,         w = height
  horizontal : vec4<f32>,  // xyz,         w = spp
  vertical   : vec4<f32>,  // xyz,         w = maxBounces
  background : vec4<f32>,  // xyz background radiance
};

@group(0) @binding(0) var<storage, read>       tris   : array<f32>;
@group(0) @binding(1) var<storage, read>       nodes  : array<f32>;
@group(0) @binding(2) var<storage, read>       triIdx : array<u32>;
@group(0) @binding(3) var<storage, read>       alb    : array<f32>;
@group(0) @binding(4) var<storage, read>       emi    : array<f32>;
@group(0) @binding(5) var<storage, read_write> fb     : array<f32>;
@group(0) @binding(6) var<uniform>             P      : Params;

const EPS : f32 = 1e-7;
const NS  : u32 = 8u;
const PI  : f32 = 3.14159265358979;

struct Hit { t: f32, tri: i32 };

fn triVert(tri: u32, k: u32) -> vec3<f32> {
  let b = tri * 9u + k * 3u;
  return vec3<f32>(tris[b], tris[b + 1u], tris[b + 2u]);
}
fn triAlbedo(tri: u32) -> vec3<f32> { let b = tri * 3u; return vec3<f32>(alb[b], alb[b+1u], alb[b+2u]); }
fn triEmiss(tri: u32) -> vec3<f32>  { let b = tri * 3u; return vec3<f32>(emi[b], emi[b+1u], emi[b+2u]); }

fn triNormal(tri: u32) -> vec3<f32> {
  let v0 = triVert(tri, 0u); let v1 = triVert(tri, 1u); let v2 = triVert(tri, 2u);
  return normalize(cross(v1 - v0, v2 - v0));
}

fn intersectTri(tri: u32, ro: vec3<f32>, rd: vec3<f32>, tMax: f32) -> f32 {
  let v0 = triVert(tri, 0u); let v1 = triVert(tri, 1u); let v2 = triVert(tri, 2u);
  let e1 = v1 - v0; let e2 = v2 - v0;
  let p = cross(rd, e2); let det = dot(e1, p);
  if (det > -EPS && det < EPS) { return -1.0; }
  let inv = 1.0 / det; let tv = ro - v0;
  let u = dot(tv, p) * inv;
  if (u < 0.0 || u > 1.0) { return -1.0; }
  let q = cross(tv, e1); let v = dot(rd, q) * inv;
  if (v < 0.0 || u + v > 1.0) { return -1.0; }
  let t = dot(e2, q) * inv;
  if (t < EPS || t > tMax) { return -1.0; }
  return t;
}

fn slabHit(ni: u32, ro: vec3<f32>, invD: vec3<f32>, tMax: f32) -> bool {
  let base = ni * NS;
  let mn = vec3<f32>(nodes[base], nodes[base + 1u], nodes[base + 2u]);
  let mx = vec3<f32>(nodes[base + 4u], nodes[base + 5u], nodes[base + 6u]);
  let t0 = (mn - ro) * invD; let t1 = (mx - ro) * invD;
  let lo = min(t0, t1); let hi = max(t0, t1);
  let tmin = max(max(lo.x, lo.y), max(lo.z, 0.0));
  let tmax = min(min(hi.x, hi.y), min(hi.z, tMax));
  return tmax >= tmin;
}

fn traceClosest(ro: vec3<f32>, rd: vec3<f32>) -> Hit {
  var best : Hit; best.t = -1.0; best.tri = -1;
  var bestT = 1e30;
  let invD = vec3<f32>(1.0 / rd.x, 1.0 / rd.y, 1.0 / rd.z);
  var stack : array<i32, 64>; var sp : i32 = 0;
  stack[sp] = 0; sp = sp + 1;
  loop {
    if (sp <= 0) { break; }
    sp = sp - 1;
    let ni = u32(stack[sp]);
    if (!slabHit(ni, ro, invD, bestT)) { continue; }
    let base = ni * NS;
    let count = nodes[base + 7u];
    if (count > 0.0) {
      let first = u32(nodes[base + 3u]); let n = u32(count);
      for (var i: u32 = 0u; i < n; i = i + 1u) {
        let tri = triIdx[first + i];
        let t = intersectTri(tri, ro, rd, bestT);
        if (t > 0.0 && t < bestT) { bestT = t; best.t = t; best.tri = i32(tri); }
      }
    } else {
      let left = i32(nodes[base + 3u]); let right = -i32(count);
      if (sp < 62) { stack[sp] = left; sp = sp + 1; stack[sp] = right; sp = sp + 1; }
    }
  }
  return best;
}

// -- RNG (xorshift32) + seed hash -- identical to pathtrace.cljc -----------
fn seedHash(px: u32, py: u32, sample: u32) -> u32 {
  var h : u32 = px * 1973u + py * 9277u + sample * 26699u + 1u;
  h = (h ^ (h >> 15u)) * 0x2c1b3c6du;
  h = (h ^ (h >> 12u)) * 0x297a2d39u;
  h = h ^ (h >> 15u);
  if (h == 0u) { return 1u; }
  return h;
}
fn nextFloat(state: ptr<function, u32>) -> f32 {
  var x = *state;
  x = x ^ (x << 13u);
  x = x ^ (x >> 17u);
  x = x ^ (x << 5u);
  *state = x;
  return f32(x) / 4294967296.0;
}

fn onb(n: vec3<f32>) -> mat3x3<f32> {
  let sgn = select(-1.0, 1.0, n.z >= 0.0);
  let a = -1.0 / (sgn + n.z);
  let b = n.x * n.y * a;
  let t  = vec3<f32>(1.0 + sgn * n.x * n.x * a, sgn * b, -sgn * n.x);
  let bt = vec3<f32>(b, sgn + n.y * n.y * a, -n.y);
  return mat3x3<f32>(t, bt, n);
}

fn cosineSample(n: vec3<f32>, state: ptr<function, u32>) -> vec3<f32> {
  let r1 = nextFloat(state); let r2 = nextFloat(state);
  let phi = 2.0 * PI * r1;
  let sinT = sqrt(r2); let cosT = sqrt(1.0 - r2);
  let basis = onb(n);
  let x = cos(phi) * sinT; let y = sin(phi) * sinT;
  return normalize(basis * vec3<f32>(x, y, cosT));
}

fn radiance(ro_in: vec3<f32>, rd_in: vec3<f32>, maxB: u32, state: ptr<function, u32>) -> vec3<f32> {
  var thr = vec3<f32>(1.0, 1.0, 1.0);
  var acc = vec3<f32>(0.0, 0.0, 0.0);
  var o = ro_in; var d = rd_in;
  for (var bounce: u32 = 0u; bounce <= maxB; bounce = bounce + 1u) {
    let hit = traceClosest(o, d);
    if (hit.tri < 0) { acc = acc + thr * P.background.xyz; break; }
    let tri = u32(hit.tri);
    acc = acc + thr * triEmiss(tri);
    if (bounce == maxB) { break; }
    var nrm = triNormal(tri);
    if (dot(nrm, d) > 0.0) { nrm = -nrm; }
    thr = thr * triAlbedo(tri);
    let hitP = o + d * hit.t;
    d = cosineSample(nrm, state);
    o = hitP + nrm * 1e-4;
  }
  return acc;
}

@compute @workgroup_size(8, 8, 1)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let width  = u32(P.origin.w);
  let height = u32(P.lowerLeft.w);
  if (gid.x >= width || gid.y >= height) { return; }
  let spp  = u32(P.horizontal.w);
  let maxB = u32(P.vertical.w);

  var col = vec3<f32>(0.0, 0.0, 0.0);
  for (var s: u32 = 0u; s < spp; s = s + 1u) {
    var state = seedHash(gid.x, gid.y, s);
    let u = (f32(gid.x) + nextFloat(&state)) / f32(width);
    let v = (f32(gid.y) + nextFloat(&state)) / f32(height);
    let ro = P.origin.xyz;
    let target = P.lowerLeft.xyz + u * P.horizontal.xyz + v * P.vertical.xyz;
    let rd = normalize(target - ro);
    col = col + radiance(ro, rd, maxB, &state);
  }
  let inv = 1.0 / f32(max(spp, 1u));
  let o = (gid.y * width + gid.x) * 4u;
  fb[o] = col.x * inv; fb[o + 1u] = col.y * inv; fb[o + 2u] = col.z * inv; fb[o + 3u] = 1.0;
}
")

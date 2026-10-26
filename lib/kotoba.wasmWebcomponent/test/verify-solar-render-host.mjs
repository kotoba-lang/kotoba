// Dependency-free unit test for src/solar-render-host.js's pure mat4/vec3/
// mesh logic (ADR-2607078000 Track B Phase 1) -- everything short of
// actually touching a GPU. Run: `node test/verify-solar-render-host.mjs`
import {
  mat4Multiply,
  mat4Perspective,
  mat4LookAt,
  mat4TranslationScale,
  vec3Normalize,
  vec3Sub,
  vec3Cross,
  vec3Dot,
  buildSphereMesh,
  wrapNowDays,
} from '../src/solar-render-host.js';

let failed = false;
function check(cond, message) {
  if (!cond) {
    failed = true;
    console.error(`FAIL: ${message}`);
  } else {
    console.log(`OK: ${message}`);
  }
}

function close(a, b, tol = 1e-6) {
  return Math.abs(a - b) <= tol;
}

function closeMat(a, b, tol = 1e-6) {
  const av = [...a];
  const bv = [...b];
  return av.length === bv.length && av.every((v, i) => close(v, bv[i], tol));
}

const IDENTITY = new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);
const M = new Float32Array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]);

check(closeMat(mat4Multiply(IDENTITY, M), M), 'mat4Multiply(I, M) == M (left identity)');
check(closeMat(mat4Multiply(M, IDENTITY), M), 'mat4Multiply(M, I) == M (right identity)');

// vec3 helpers, checked against hand-worked values.
check(closeMat(vec3Normalize([3, 4, 0]), [0.6, 0.8, 0]), 'vec3Normalize([3,4,0]) -> [0.6,0.8,0] (3-4-5 triangle)');
check(closeMat(vec3Normalize([0, 0, 0]), [0, 0, 0]), 'vec3Normalize of the zero vector -> [0,0,0], not NaN/Infinity from a div-by-zero');
check(closeMat(vec3Sub([5, 5, 5], [1, 2, 3]), [4, 3, 2]), 'vec3Sub([5,5,5],[1,2,3]) -> [4,3,2]');
check(closeMat(vec3Cross([1, 0, 0], [0, 1, 0]), [0, 0, 1]), 'vec3Cross(x-hat, y-hat) -> z-hat (right-handed)');
check(vec3Dot([1, 2, 3], [4, 5, 6]) === 32, 'vec3Dot([1,2,3],[4,5,6]) == 32');

// mat4LookAt: camera at [0,0,5] looking at the origin with a standard
// up-vector should produce the identity rotation (already axis-aligned)
// with only the eye-position translation baked in.
{
  const view = mat4LookAt([0, 0, 5], [0, 0, 0], [0, 1, 0]);
  check(
    closeMat(view, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, -5, 1]),
    'mat4LookAt([0,0,5],[0,0,0],[0,1,0]) -> identity rotation + [0,0,-5] translation'
  );
}

// mat4Perspective: WebGPU depth range is [0,1], not OpenGL's [-1,1] -- the
// defining difference is row [2][3] = -1 (perspective divide sets up w=-z)
// and the z-mapping coefficients, checked against the closed-form formula
// directly (not just re-deriving the same code).
{
  const fovy = Math.PI / 3;
  const aspect = 1.5;
  const near = 0.1;
  const far = 100;
  const proj = mat4Perspective(fovy, aspect, near, far);
  const f = 1 / Math.tan(fovy / 2);
  const rangeInv = 1 / (near - far);
  const expected = [
    f / aspect, 0, 0, 0,
    0, f, 0, 0,
    0, 0, far * rangeInv, -1,
    0, 0, far * near * rangeInv, 0,
  ];
  check(closeMat(proj, expected), 'mat4Perspective matches the closed-form WebGPU [0,1]-depth-range formula');
}

check(
  closeMat(mat4TranslationScale(1, 2, 3, 2), [2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 2, 0, 1, 2, 3, 1]),
  'mat4TranslationScale(1,2,3,scale=2) -> uniform 2x scale + [1,2,3] translation, no rotation'
);

// buildSphereMesh: lat-bands=2, lon-bands=4 -> (lat+1)*(lon+1) = 3*5 = 15
// ring vertices, each emitting 6 floats (position xyz + normal xyz, a unit
// sphere so normal == position) = 90 floats; lat-bands*lon-bands = 8 quads
// * 2 triangles * 3 indices = 48 indices.
{
  const mesh = buildSphereMesh(2, 4);
  check(mesh.vertices.length === 90, `buildSphereMesh(2,4) vertices.length === 90 (got ${mesh.vertices.length})`);
  check(mesh.indices.length === 48, `buildSphereMesh(2,4) indices.length === 48 (got ${mesh.indices.length})`);
  check(mesh.vertices instanceof Float32Array, 'buildSphereMesh vertices is a Float32Array (WebGPU writeBuffer-ready)');
  check(mesh.indices instanceof Uint16Array, 'buildSphereMesh indices is a Uint16Array (WebGPU writeBuffer-ready)');

  // Every position on a unit sphere has length 1 (it's built directly from
  // sin/cos of the lat/lon angles) -- and since normal == position for a
  // unit sphere centered at the origin, this also proves the normals.
  let allUnitLength = true;
  for (let i = 0; i < mesh.vertices.length; i += 6) {
    const x = mesh.vertices[i];
    const y = mesh.vertices[i + 1];
    const z = mesh.vertices[i + 2];
    const len = Math.sqrt(x * x + y * y + z * z);
    if (!close(len, 1, 1e-5)) allUnitLength = false;
  }
  check(allUnitLength, 'every buildSphereMesh vertex position lies on the unit sphere (length 1)');

  // Every index must be in range -- an off-by-one in the (lat, lon) -> flat
  // index arithmetic would silently emit an out-of-bounds index instead of
  // throwing (WebGPU would just read garbage/zero past the buffer).
  const vertexCount = mesh.vertices.length / 6;
  let allIndicesInRange = true;
  for (let i = 0; i < mesh.indices.length; i++) {
    if (mesh.indices[i] < 0 || mesh.indices[i] >= vertexCount) allIndicesInRange = false;
  }
  check(allIndicesInRange, `every index is within [0, ${vertexCount}) -- no out-of-bounds triangle references`);
}

// wrapNowDays(elapsed-s) = (elapsed-s * days-per-second) mod wrap-days --
// pulled out of the now_days host-import closure specifically so this
// wall-clock -> bounded-simulated-day mapping is testable without a fake
// clock. Constants baked into solar_render_host.cljs: days-per-second=8.0,
// wrap-days=80.0 (a 10-real-second wrap cycle at these defaults).
check(wrapNowDays(0) === 0, 'wrapNowDays(0) === 0 (no time elapsed yet)');
check(close(wrapNowDays(5), 40), 'wrapNowDays(5) === 40 (5s * 8 days/s, well inside one wrap cycle)');
check(close(wrapNowDays(10), 0), 'wrapNowDays(10) === 0 -- exactly one full wrap cycle (10s * 8 days/s = 80 = wrap-days), wraps back to 0 rather than reporting 80');
check(close(wrapNowDays(12.5), 20), 'wrapNowDays(12.5) === 20 -- past one full cycle, wraps correctly (12.5s * 8 = 100, 100 mod 80 = 20)');
{
  // Sweep a wide range of elapsed-s (well past many wrap cycles, as a
  // long-running page would eventually reach) and confirm the result
  // never leaves [0, wrap-days) and is never NaN/negative -- this is
  // exactly the invariant demo_solar_helix.kotoba's galactic-frame
  // forward-drift math depends on to never grow unbounded.
  const WRAP_DAYS = 80;
  let allInRange = true;
  for (let s = 0; s <= 1000; s += 0.37) {
    const d = wrapNowDays(s);
    if (!(Number.isFinite(d) && d >= 0 && d < WRAP_DAYS)) allInRange = false;
  }
  check(allInRange, `wrapNowDays stays within [0, ${WRAP_DAYS}) for elapsed-s swept from 0 to 1000 (many wrap cycles), never NaN/negative/out-of-range`);
}

if (failed) process.exit(1);
console.log('OK: solar-render-host.js\'s mat4/vec3/sphere-mesh/wrap-clock pure logic all matches hand-worked expected values, with no GPU involved');

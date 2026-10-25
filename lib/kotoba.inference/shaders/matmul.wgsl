struct Meta {
  M: u32,
  N: u32,
  K: u32,
  has_bias: u32,
}

@group(0) @binding(0) var<uniform> params: Meta;
@group(0) @binding(1) var<storage, read> A: array<f32>;
@group(0) @binding(2) var<storage, read> B: array<f32>;
@group(0) @binding(3) var<storage, read_write> C: array<f32>;
@group(0) @binding(4) var<storage, read> bias: array<f32>;

const TILE: u32 = 16u;

var<workgroup> tileA: array<f32, 256>;
var<workgroup> tileB: array<f32, 256>;

@compute @workgroup_size(16, 16)
fn main(
  @builtin(global_invocation_id) gid: vec3<u32>,
  @builtin(local_invocation_id) lid: vec3<u32>,
  @builtin(workgroup_id) wid: vec3<u32>,
) {
  let row = wid.y * TILE + lid.y;
  let col = wid.x * TILE + lid.x;

  var acc: f32 = 0.0;
  let numTiles = (params.K + TILE - 1u) / TILE;

  for (var t: u32 = 0u; t < numTiles; t++) {
    let aCol = t * TILE + lid.x;
    let bRow = t * TILE + lid.y;

    if (row < params.M && aCol < params.K) {
      tileA[lid.y * TILE + lid.x] = A[row * params.K + aCol];
    } else {
      tileA[lid.y * TILE + lid.x] = 0.0;
    }
    if (bRow < params.K && col < params.N) {
      tileB[lid.y * TILE + lid.x] = B[bRow * params.N + col];
    } else {
      tileB[lid.y * TILE + lid.x] = 0.0;
    }

    workgroupBarrier();

    for (var k: u32 = 0u; k < TILE; k++) {
      acc += tileA[lid.y * TILE + k] * tileB[k * TILE + lid.x];
    }

    workgroupBarrier();
  }

  if (row < params.M && col < params.N) {
    var result = acc;
    if (params.has_bias != 0u) {
      result += bias[col];
    }
    C[row * params.N + col] = result;
  }
}

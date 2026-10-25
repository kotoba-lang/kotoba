struct G { vp: mat4x4<f32>, sun_dir: vec4<f32>, sun_col: vec4<f32>, sky: vec4<f32>, light_vp: mat4x4<f32>, light_a: vec4<f32>, light_b: vec4<f32>, light_c: vec4<f32>, light_d: vec4<f32> };
@group(0) @binding(0) var<uniform> g: G;
@group(0) @binding(1) var shadowMap: texture_depth_2d;
@group(0) @binding(2) var shadowSamp: sampler_comparison;
fn shadow(wpos: vec3<f32>, ndl: f32) -> f32 {
  let lc = (g.light_vp * vec4<f32>(wpos, 1.0));
  let ndc = (lc.xyz / lc.w);
  let uv = vec2<f32>(((ndc.x * 0.5) + 0.5), (0.5 - (ndc.y * 0.5)));
  if (((uv.x < 0.0) || (uv.x > 1.0) || (uv.y < 0.0) || (uv.y > 1.0) || (ndc.z > 1.0))) {
    return 1.0;
  }
  let bias = max((g.light_d.y * (1.0 - ndl)), g.light_d.z);
  let texel = g.light_d.w;
  var lit = 0.0;
  for (var dx = -1; (dx <= 1); dx++) {
    for (var dy = -1; (dy <= 1); dy++) {
      lit += textureSampleCompareLevel(shadowMap, shadowSamp, (uv + (vec2<f32>(f32(dx), f32(dy)) * texel)), (ndc.z - bias));
    }
  }
  return (lit / 9.0);
}
struct VO { @builtin(position) clip: vec4<f32>, @location(0) n: vec3<f32>, @location(1) col: vec3<f32>, @location(2) wpos: vec3<f32>, @location(3) mat: vec3<f32> };
@vertex
fn vs(@location(0) pos: vec3<f32>, @location(1) normal: vec3<f32>, @location(2) m0: vec4<f32>, @location(3) m1: vec4<f32>, @location(4) m2: vec4<f32>, @location(5) m3: vec4<f32>, @location(6) color: vec4<f32>, @location(7) material: vec4<f32>) -> VO {
  let model = mat4x4<f32>(m0, m1, m2, m3);
  let world = (model * vec4<f32>(pos, 1.0));
  var o: VO;
  o.clip = (g.vp * world);
  o.n = normalize(((model * vec4<f32>(normal, 0.0))).xyz);
  o.col = color.rgb;
  o.wpos = world.xyz;
  o.mat = material.xyz;
  return o;
}
@fragment
fn fs(i: VO) -> @location(0) vec4<f32> {
  let N = normalize(i.n);
  let L = normalize((-g.sun_dir.xyz));
  let eye = vec3<f32>(g.sun_dir.w, g.sun_col.w, g.sky.w);
  let V = normalize((eye - i.wpos));
  let H = normalize((L + V));
  let ndl = max(dot(N, L), 0.0);
  let metallic = clamp(i.mat.x, 0.0, 1.0);
  let rough = clamp(i.mat.y, 0.04, 1.0);
  let emissive = i.mat.z;
  let amb = mix(g.light_a.rgb, (g.sky.rgb * g.light_a.w), ((N.y * 0.5) + 0.5));
  let shininess = mix(g.light_c.x, g.light_c.y, (1.0 - rough));
  let specStr = mix(g.light_b.x, g.light_b.y, metallic);
  let specTint = mix(vec3<f32>(1.0), i.col, metallic);
  let spec = (pow(max(dot(N, H), 0.0), shininess) * specStr);
  let rim = (pow((1.0 - max(dot(N, V), 0.0)), g.light_b.w) * g.light_b.z);
  let sh = shadow(i.wpos, ndl);
  var c = ((i.col * (amb + (ndl * g.sun_col.rgb * g.light_c.z * (1.0 - (metallic * g.light_c.w)) * sh))) + (specTint * g.sun_col.rgb * spec * sh) + (g.sky.rgb * rim) + (i.col * emissive));
  c = (c / (c + vec3<f32>(1.0)));
  c = pow(c, vec3<f32>((1.0 / g.light_d.x)));
  return vec4<f32>(c, 1.0);
}

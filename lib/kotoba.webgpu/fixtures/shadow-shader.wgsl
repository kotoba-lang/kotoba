struct G { vp: mat4x4<f32>, sun_dir: vec4<f32>, sun_col: vec4<f32>, sky: vec4<f32>, light_vp: mat4x4<f32> };
@group(0) @binding(0) var<uniform> g: G;
@vertex
fn vs(@location(0) pos: vec3<f32>, @location(1) normal: vec3<f32>, @location(2) m0: vec4<f32>, @location(3) m1: vec4<f32>, @location(4) m2: vec4<f32>, @location(5) m3: vec4<f32>, @location(6) color: vec4<f32>, @location(7) material: vec4<f32>) -> @builtin(position) vec4<f32> {
  let model = mat4x4<f32>(m0, m1, m2, m3);
  return (g.light_vp * model * vec4<f32>(pos, 1.0));
}

(ns kotoba.raytrace.wgsl
  "WGSL ray-query compute-shader codegen. 1:1 port of the generator half of
   kami-rt's `lib.rs` (`fnum` + `wgsl_ray_query`) — pure string generation,
   no GPU involved (the doc comment on the Rust source is explicit: this is
   \"the host-side counterpart of clj `kami.rt/emit-wgsl`\", generating text
   the host later compiles/binds; that compile+bind step needs a
   `wgpu::Device` and was never part of kami-rt, so it's out of scope for
   this port the same way it was out of scope for the crate it's ported
   from)."
  (:require [kotoba.raytrace.mathx :as mathx]
            [kotoba.raytrace.config :as config]))

(defn default-config
  "RtConfig::default() — {:max-bounces 4 :spp 8 :clamp 10.0 :seed 0}."
  []
  (:rt/default-config config/config))

(defn- fnum
  "Format a number as a WGSL f32 literal (integers gain a trailing `.0`)."
  [x]
  (let [fx (double x)]
    (if (== fx (mathx/floor fx))
      (str (mathx/trunc fx) ".0")
      (str fx))))

(defn ray-query-source
  "Generate the WGSL ray-query compute shader for `cfg` (a kami-rt RtConfig
   map: :max-bounces :spp :clamp :seed). Integrator parameters are baked as
   `override` constants so one IR recompiles per quality preset."
  [name cfg]
  (let [{:keys [max-bounces spp clamp seed]} cfg]
    (str
     "// kami-rt — generated WGSL ray-query trace for recipe \"" name "\"\n"
     "enable chromium_experimental_ray_query;\n\n"
     "struct RtGlobals {\n"
     "  inv_view_proj: mat4x4<f32>,\n"
     "  cam_pos: vec3<f32>,\n"
     "  frame: u32,\n"
     "  width: u32,\n"
     "  height: u32,\n"
     "};\n\n"
     "override RT_MAX_BOUNCES: u32 = " max-bounces "u;\n"
     "override RT_SPP: u32 = " spp "u;\n"
     "override RT_CLAMP: f32 = " (fnum clamp) ";\n"
     "override RT_SEED: u32 = " seed "u;\n\n"
     "@group(0) @binding(0) var tlas: acceleration_structure;\n"
     "@group(0) @binding(1) var<uniform> u: RtGlobals;\n"
     "@group(0) @binding(2) var<storage, read_write> out_color: array<vec4<f32>>;\n\n"
     "@compute @workgroup_size(8, 8, 1)\n"
     "fn trace(@builtin(global_invocation_id) gid: vec3<u32>) {\n"
     "  if (gid.x >= u.width || gid.y >= u.height) { return; }\n"
     "  let idx = gid.y * u.width + gid.x;\n"
     "  var radiance = vec3<f32>(0.0);\n"
     "  for (var s: u32 = 0u; s < RT_SPP; s = s + 1u) {\n"
     "    var ray = primary_ray(gid.xy, s);\n"
     "    var throughput = vec3<f32>(1.0);\n"
     "    for (var b: u32 = 0u; b <= RT_MAX_BOUNCES; b = b + 1u) {\n"
     "      var rq: ray_query;\n"
     "      rayQueryInitialize(&rq, tlas, ray);\n"
     "      rayQueryProceed(&rq);\n"
     "      let hit = rayQueryGetCommittedIntersection(&rq);\n"
     "      if (hit.kind == RAY_QUERY_INTERSECTION_NONE) {\n"
     "        radiance = radiance + throughput * sky(ray.dir);\n"
     "        break;\n"
     "      }\n"
     "      radiance = radiance + throughput * emission(hit);\n"
     "      throughput = throughput * bsdf_sample(hit, &ray, s, b);\n"
     "    }\n"
     "  }\n"
     "  radiance = min(radiance / f32(RT_SPP), vec3<f32>(RT_CLAMP));\n"
     "  out_color[idx] = vec4<f32>(radiance, 1.0);\n"
     "}\n")))

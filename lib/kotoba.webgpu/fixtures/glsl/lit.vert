#version 300 es

precision highp float;
precision highp int;

struct G {
    mat4x4 vp;
    vec4 sun_dir;
    vec4 sun_col;
    vec4 sky;
    mat4x4 light_vp;
    vec4 light_a;
    vec4 light_b;
    vec4 light_c;
    vec4 light_d;
};
struct VO {
    vec4 clip;
    vec3 n;
    vec3 col;
    vec3 wpos;
    vec3 mat;
};
layout(std140) uniform G_block_0Vertex { G _group_0_binding_0_vs; };

layout(location = 0) in vec3 _p2vs_location0;
layout(location = 1) in vec3 _p2vs_location1;
layout(location = 2) in vec4 _p2vs_location2;
layout(location = 3) in vec4 _p2vs_location3;
layout(location = 4) in vec4 _p2vs_location4;
layout(location = 5) in vec4 _p2vs_location5;
layout(location = 6) in vec4 _p2vs_location6;
layout(location = 7) in vec4 _p2vs_location7;
smooth out vec3 _vs2fs_location0;
smooth out vec3 _vs2fs_location1;
smooth out vec3 _vs2fs_location2;
smooth out vec3 _vs2fs_location3;

void main() {
    vec3 pos = _p2vs_location0;
    vec3 normal = _p2vs_location1;
    vec4 m0_ = _p2vs_location2;
    vec4 m1_ = _p2vs_location3;
    vec4 m2_ = _p2vs_location4;
    vec4 m3_ = _p2vs_location5;
    vec4 color = _p2vs_location6;
    vec4 material = _p2vs_location7;
    VO o = VO(vec4(0.0), vec3(0.0), vec3(0.0), vec3(0.0), vec3(0.0));
    mat4x4 model = mat4x4(m0_, m1_, m2_, m3_);
    vec4 world = (model * vec4(pos, 1.0));
    mat4x4 _e16 = _group_0_binding_0_vs.vp;
    o.clip = (_e16 * world);
    o.n = normalize((model * vec4(normal, 0.0)).xyz);
    o.col = color.xyz;
    o.wpos = world.xyz;
    o.mat = material.xyz;
    VO _e30 = o;
    gl_Position = _e30.clip;
    _vs2fs_location0 = _e30.n;
    _vs2fs_location1 = _e30.col;
    _vs2fs_location2 = _e30.wpos;
    _vs2fs_location3 = _e30.mat;
    gl_Position.yz = vec2(-gl_Position.y, gl_Position.z * 2.0 - gl_Position.w);
    return;
}


#version 300 es

precision highp float;
precision highp int;

struct G {
    mat4x4 vp;
    vec4 sun_dir;
    vec4 sun_col;
    vec4 sky;
    mat4x4 light_vp;
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

void main() {
    vec3 pos = _p2vs_location0;
    vec3 normal = _p2vs_location1;
    vec4 m0_ = _p2vs_location2;
    vec4 m1_ = _p2vs_location3;
    vec4 m2_ = _p2vs_location4;
    vec4 m3_ = _p2vs_location5;
    vec4 color = _p2vs_location6;
    vec4 material = _p2vs_location7;
    mat4x4 model = mat4x4(m0_, m1_, m2_, m3_);
    mat4x4 _e11 = _group_0_binding_0_vs.light_vp;
    gl_Position = ((_e11 * model) * vec4(pos, 1.0));
    gl_Position.yz = vec2(-gl_Position.y, gl_Position.z * 2.0 - gl_Position.w);
    return;
}


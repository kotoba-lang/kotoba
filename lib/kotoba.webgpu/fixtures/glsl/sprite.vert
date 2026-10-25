#version 300 es

precision highp float;
precision highp int;

struct U {
    vec2 viewport;
    vec2 _p0_;
};
struct VO {
    vec4 clip;
    vec2 uv;
    float shape;
    vec4 color;
};
layout(std140) uniform U_block_0Vertex { U _group_0_binding_0_vs; };

layout(location = 0) in vec2 _p2vs_location0;
layout(location = 1) in vec2 _p2vs_location1;
layout(location = 2) in float _p2vs_location2;
layout(location = 3) in float _p2vs_location3;
layout(location = 4) in vec4 _p2vs_location4;
smooth out vec2 _vs2fs_location0;
smooth out float _vs2fs_location1;
smooth out vec4 _vs2fs_location2;

void main() {
    uint vid = uint(gl_VertexID);
    vec2 ipos = _p2vs_location0;
    vec2 isize = _p2vs_location1;
    float irot = _p2vs_location2;
    float ishape = _p2vs_location3;
    vec4 icolor = _p2vs_location4;
    vec2 corners[6] = vec2[6](vec2(-1.0, -1.0), vec2(1.0, -1.0), vec2(-1.0, 1.0), vec2(-1.0, 1.0), vec2(1.0, -1.0), vec2(1.0, 1.0));
    VO o = VO(vec4(0.0), vec2(0.0), 0.0, vec4(0.0));
    vec2 q = corners[vid];
    float c = cos(irot);
    float s = sin(irot);
    vec2 scaled = (q * isize);
    vec2 rotated = vec2(((scaled.x * c) - (scaled.y * s)), ((scaled.x * s) + (scaled.y * c)));
    vec2 px = (ipos + rotated);
    vec2 _e45 = _group_0_binding_0_vs.viewport;
    vec2 ndc = (((px / _e45) * 2.0) - vec2(1.0));
    o.clip = vec4(ndc.x, -(ndc.y), 0.0, 1.0);
    o.uv = q;
    o.shape = ishape;
    o.color = icolor;
    VO _e63 = o;
    gl_Position = _e63.clip;
    _vs2fs_location0 = _e63.uv;
    _vs2fs_location1 = _e63.shape;
    _vs2fs_location2 = _e63.color;
    gl_Position.yz = vec2(-gl_Position.y, gl_Position.z * 2.0 - gl_Position.w);
    return;
}


#version 300 es

precision highp float;
precision highp int;

struct SU {
    vec4 zenith;
    vec4 ground;
};
struct VO {
    vec4 clip;
    vec2 uv;
};
smooth out vec2 _vs2fs_location0;

void main() {
    uint vid = uint(gl_VertexID);
    vec2 p[3] = vec2[3](vec2(-1.0, -3.0), vec2(-1.0, 1.0), vec2(3.0, 1.0));
    VO o = VO(vec4(0.0), vec2(0.0));
    vec2 q = p[vid];
    o.clip = vec4(q.x, q.y, 0.0, 1.0);
    o.uv = ((q + vec2(1.0)) * 0.5);
    VO _e27 = o;
    gl_Position = _e27.clip;
    _vs2fs_location0 = _e27.uv;
    gl_Position.yz = vec2(-gl_Position.y, gl_Position.z * 2.0 - gl_Position.w);
    return;
}

